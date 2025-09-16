import asyncio
import aiohttp
from bs4 import BeautifulSoup
from fake_useragent import FakeUserAgent
from itertools import cycle
from typing import List, Optional
from JSONSaver import JSONSaver


class Parser:
    def __init__(
        self,
        companies_pages: List[str],
        categories_pages: List[str],
        max_retries: int = 25,
        request_timeout: int = 6,
        output_file: str = "reviews.json",
    ):
        self._companies_pages = companies_pages
        self._categories_pages = categories_pages
        self._ua = FakeUserAgent()
        self._session = None 
        self._proxy_list = cycle(self.set_proxy())
        self._max_retries = max_retries
        self._request_timeout = request_timeout
        self._saver = JSONSaver(output_file)
        self._processed_reviews = set()

    @classmethod
    def set_proxy(cls):
        proxy_list = []
        with open("proxies.txt", encoding="utf-8") as file:
            for line in file:
                proxy = line.strip().split(":")
                if len(proxy) == 4:
                    ip, port, login, password = proxy
                    proxy_url = f"http://{ip}:{port}"
                    proxy_auth = aiohttp.BasicAuth(login, password)
                    proxy_list.append((proxy_url, proxy_auth))
                elif len(proxy) == 2:
                    ip, port = proxy
                    proxy_url = f"http://{ip}:{port}"
                    proxy_list.append((proxy_url, None))
                else:
                    print("\033[91m" + f"Proxy Error: {proxy}" + "\033[0m")
        return proxy_list

    async def make_request(self, url: str) -> Optional[str]:
        """Асинхронный HTTP GET с ротацией прокси."""
        headers = {"User-Agent": self._ua.random}
        for attempt in range(self._max_retries):
            proxy_url, proxy_auth = next(self._proxy_list)
            try:
                async with self._session.get(
                    url,
                    headers=headers,
                    proxy=proxy_url,
                    proxy_auth=proxy_auth,
                    timeout=self._request_timeout,
                ) as response:
                    status = response.status
                    print(
                        f"Requested with {proxy_url}, URL: {url}, status_code: {status}"
                    )
                    if status == 200:
                        return await response.text()
            except Exception as e:
                print("\033[91m" + f"Request Error: {url} {e}" + "\033[0m")
        return None

    async def get_all_services(self) -> List[str]:
        services_urls = []
        for base_url in self._companies_pages:
            base_text = await self.make_request(base_url)
            if base_text is None:
                print(
                    "\033[91m" + f"Failed to get company page: {base_url}" + "\033[0m"
                )
                continue
            soup = BeautifulSoup(base_text, "lxml")
            pager = soup.find("div", class_="pager")
            pages = [base_url]
            if pager is not None:
                # Получаем ссылку последней страницы
                last_link_href = pager.find_all("a", href=True, recursive=False)[-1][
                    "href"
                ]
                last_link = (
                    "https://otzovik.com" + last_link_href
                    if last_link_href.startswith("/")
                    else last_link_href
                )
                last_page_num = int(last_link.rstrip("/").split("/")[-1])
                for num in range(2, last_page_num + 1):
                    pages.append(f"{base_url}&page={num}")
            # Проходим по всем страницам списка услуг
            for page in pages:
                page_text = await self.make_request(page)
                if page_text is None:
                    print("\033[91m" + f"Failed to get page: {page}" + "\033[0m")
                    continue
                soup_page = BeautifulSoup(page_text, "lxml")
                services = soup_page.find("div", {"class": "product-list decor-n"})
                if services:
                    services_urls.extend(
                        [
                            "https://otzovik.com/" + service["href"]
                            for service in services.select("div div.product-photo a")
                        ]
                    )
        services_urls.extend(self._categories_pages)
        return services_urls

    async def get_all_reviews_by_page(self, page_text: str) -> List[str]:
        """Извлекает URL-ы отзывов из HTML-страницы."""
        review_urls = []
        soup = BeautifulSoup(page_text, "lxml")
        reviews = soup.find_all("div", {"itemprop": "review"})
        for review in reviews:
            meta = review.find("meta", {"itemprop": "url", "content": True})
            if meta:
                review_urls.append(meta["content"])
        return review_urls

    async def parse_review(self, review_url: str) -> Optional[dict]:
        """Получает и парсит страницу отзыва."""
        try:
            text = await self.make_request(review_url)
            if text is None:
                print("\033[91m" + f"Failed to fetch review: {review_url}" + "\033[0m")
                return None
            soup = BeautifulSoup(text, "lxml")
            result_dict = {}
            service_name_tag = soup.find("span", {"class": "fn", "itemprop": "name"})
            result_dict["Сервис"] = (
                service_name_tag.get_text() if service_name_tag else ""
            )
            result_dict["Ссылка на отзыв"] = review_url

            review_container = soup.select_one("div.item.review-wrap")
            if review_container:
                user_info = review_container.select_one("div.user-info")
                if user_info:
                    login_tag = user_info.select_one("a.user-login.fit-with-ava.url.fn")
                    if login_tag:
                        name_span = login_tag.find("span", {"itemprop": "name"})
                        result_dict["Логин"] = name_span.get_text() if name_span else ""
                    rep_tag = user_info.select_one("div.karma")
                    result_dict["Репутация пользователя"] = (
                        int(rep_tag.get_text()) if rep_tag else 0
                    )
                    loc_tag = user_info.select_one("div.user-location")
                    result_dict["Локация пользователя"] = (
                        loc_tag.get_text() if loc_tag else ""
                    )
                    total_tag = user_info.select_one(".reviews-counter")
                    result_dict["Все отзывы пользователя"] = (
                        int(total_tag.get_text()) if total_tag else 0
                    )

                date_tag = review_container.select_one(
                    "span.review-postdate.dtreviewed abbr.value"
                )
                result_dict["Дата"] = date_tag["title"] if date_tag else ""
                liked_tag = review_container.select_one(
                    "span.review-btn.review-yes.tooltip-top"
                )
                result_dict["Лайки"] = int(liked_tag.get_text()) if liked_tag else 0
                comments_tag = review_container.select_one(
                    "a.review-btn.review-comments.tooltip-top"
                )
                result_dict["Комментарии к отзыву"] = (
                    int(comments_tag.get_text()) if comments_tag else 0
                )

                advantages_tag = review_container.select_one("div.review-plus")
                if advantages_tag:
                    result_dict["Достоинства"] = (
                        advantages_tag.get_text().removeprefix("Достоинства:").strip()
                    )
                disadvantages_tag = review_container.select_one("div.review-minus")
                if disadvantages_tag:
                    result_dict["Недостатки"] = (
                        disadvantages_tag.get_text().removeprefix("Недостатки:").strip()
                    )

                body_tag = review_container.select_one("div.review-body.description")
                result_dict["Отзыв"] = body_tag.get_text() if body_tag else ""
                summary_tag = review_container.find(
                    "span", {"class": "summary", "itemprop": "name"}
                )
                result_dict["Общее впечатление"] = (
                    summary_tag.get_text() if summary_tag else ""
                )
                score_tag = review_container.select_one(
                    "div.rating-score.tooltip-right"
                )
                result_dict["Оценка"] = int(score_tag.get_text()) if score_tag else 0
                rec_tag = review_container.select_one("td.recommend-ratio")
                result_dict["Рекомендую друзьям"] = (
                    rec_tag.get_text() if rec_tag else ""
                )

            return result_dict
        except Exception as e:
            print("\033[91m" + f"Error parsing review {review_url}: {e}" + "\033[0m")
            return None

    async def get_reviews_by_service(self):
        """Оркестровка получения всех отзывов по списку сервисов."""
        connector = aiohttp.TCPConnector(limit=10)
        async with aiohttp.ClientSession(connector=connector) as session:
            self._session = session
            services_urls = await self.get_all_services()
            for service_url in services_urls:
                print("\033[92m" + f"Category: {service_url}" + "\033[0m")
                first_page_text = await self.make_request(service_url)
                if first_page_text is None:
                    print(
                        "\033[91m"
                        + f"Failed to get service page: {service_url}"
                        + "\033[0m"
                    )
                    continue
                soup = BeautifulSoup(first_page_text, "lxml")
                pager = soup.find("div", class_="pager")
                if pager is not None:
                    last_link_href = pager.find_all("a", href=True, recursive=False)[
                        -1
                    ]["href"]
                    last_link = (
                        ("https://otzovik.com" + last_link_href)
                        if last_link_href.startswith("/")
                        else last_link_href
                    )
                    last_page_num = int(last_link.rstrip("/").split("/")[-1])
                    pages = [service_url] + [
                        f"{service_url}{i}/" for i in range(2, last_page_num + 1)
                    ]
                else:
                    pages = [service_url]

                total_votes_tag = soup.select_one("span.votes")
                total_votes = int(total_votes_tag.get_text()) if total_votes_tag else 0
                vote_num = 1

                # Загрузка HTML всех страниц сервиса
                page_tasks = [self.make_request(page) for page in pages]
                page_texts = await asyncio.gather(*page_tasks)
                for page_text in page_texts:
                    if not page_text:
                        continue
                    review_urls = await self.get_all_reviews_by_page(page_text)
                    for review_url in review_urls:
                        if review_url in self._processed_reviews:
                            print(
                                "\033[92m"
                                + f"Already processed: {review_url}"
                                + "\033[0m"
                            )
                            continue
                        review_result = await self.parse_review(review_url)
                        if review_result:
                            self._saver.save_review(service_url, review_result)
                            self._processed_reviews.add(review_url)
                            print(
                                "\033[92m"
                                + f"Saved review: {review_url}, {vote_num}/{total_votes}"
                                + "\033[0m"
                            )
                            vote_num += 1


companies_pages = [
    "https://otzovik.com/?official_products=Альфа-Банк",
    "https://otzovik.com/?official_products=Россельхозбанк",
    "https://otzovik.com/?official_products=Т-Банк",
    "https://otzovik.com/?official_products=Совкомбанк",
]

sberbank_categories = [
    "https://otzovik.com/reviews/sberbank_rossii/",
    "https://otzovik.com/reviews/lotereya_sberbank/",
    "https://otzovik.com/reviews/avtokredit_v_sberbanke/",
    "https://otzovik.com/reviews/akkreditiv_ot_sberbanka/",
    "https://otzovik.com/reviews/refinansirovanie_v_sberbanke/",
    "https://otzovik.com/reviews/inkassaciya_sberbank_rossii/",
    "https://otzovik.com/reviews/platezhnie_terminali_sberbanka/",
    "https://otzovik.com/reviews/ekvayring_ot_sberbank_rossii/",
    "https://otzovik.com/reviews/vklad_sberbank_popolnyay/",
    "https://otzovik.com/reviews/molodezhnaya_karta_sberbanka/",
    "https://otzovik.com/reviews/vkladi_sberbank_onlayn/",
    "https://otzovik.com/reviews/vklad_sberbank_upravlyay/",
    "https://otzovik.com/reviews/vklad_sberbank_sohranyay/",
    "https://otzovik.com/reviews/plastikovaya_karta_sberbanka_rossii_sberkart/",
    "https://otzovik.com/reviews/sistema_denezhnih_perevodov_blic_sberbank/",
    "https://otzovik.com/reviews/plastikovaya_karta_sberbank_visa_electron/",
    "https://otzovik.com/reviews/sberbank_rossii_ipoteka/",
    "https://otzovik.com/reviews/kreditnaya_karta_sberbanka_rossii_visa/",
    "https://otzovik.com/reviews/potrebitelskiy_kredit_sberbanka_rossii/",
    "https://otzovik.com/reviews/kreditnaya_karta_sberbank-maestro_momentum/",
    "https://otzovik.com/reviews/plastikovaya_karta_sberbanka_rossii_maestro/",
    "https://otzovik.com/reviews/keshbek_sberbank/",
    "https://otzovik.com/reviews/ipotechniy_kredit_sberbanka_rossii/",
    "https://otzovik.com/reviews/lizing_v_sberbanke/",
    "https://otzovik.com/reviews/sberbank_onlayn-internet-bank/",
    "https://otzovik.com/reviews/usluga_sberbanka_mobilniy_bank/",
    "https://otzovik.com/reviews/negosudarstvenniy_pensionniy_fond_sberbanka_russia_moscow/",
    "https://otzovik.com/reviews/bonusi_sberbanka/",
    "https://otzovik.com/reviews/kreditnaya_karta_sberbanka_mastercard/",
    "https://otzovik.com/reviews/debetovaya_karta_visa_sberbanka_rossii/",
    "https://otzovik.com/reviews/usluga_avtoplatezh_sberbank_rossii/",
    "https://otzovik.com/reviews/kreditnaya_karta_sberbank_rossii_mastercard_gold/",
    "https://otzovik.com/reviews/perevod_po_nomeru_telefona_poluchatelya_sberbank/",
    "https://otzovik.com/reviews/kreditnaya_karta_sberbank_rossii_visa_gold/",
    "https://otzovik.com/reviews/plastikovaya_karta_sberbank_maestro_socialnaya/",
    "https://otzovik.com/reviews/plastikovaya_karta_sberbank_maestro_studencheskaya/",
    "https://otzovik.com/reviews/plastikovaya_karta_sberbanka_mastercard/",
    "https://otzovik.com/reviews/denezhnie_perevodi_sberbank_rossii_kolibri/",
    "https://otzovik.com/reviews/bankomati_sberbanka_rossii/",
    "https://otzovik.com/reviews/plastikovaya_karta_sberbank_visa_electron_momentum_r/",
    "https://otzovik.com/reviews/sberbank_onlayn-prilozhenie_dlya_ios/",
    "https://otzovik.com/reviews/kontaktniy_centr_sberbanka_rossii_russia_moscow/",
    "https://otzovik.com/reviews/sberbank_onlayn-prilozhenie_dlya_android/",
    "https://otzovik.com/reviews/strahovanie_zhizni_sberbanka_rossii_sberegatelnoe_strahovanie/",
    "https://otzovik.com/reviews/vivod_deneg_s_koshelka_webmoney_na_kartu_sberbanka_rossii/",
    "https://otzovik.com/reviews/kreditnaya_karta_sberbanka_visa_classic_credit_momentum/",
    "https://otzovik.com/reviews/sberbank_onlayn-prilozhenie_dlya_windows_phone/",
    "https://otzovik.com/reviews/denezhnie_perevodi_moneygram_sberbank_rf/",
    "https://otzovik.com/reviews/personalnoe_bankovskoe_obsluzhivanie_sberbank_premer/",
    "https://otzovik.com/reviews/debetovaya_karta_sberbank_rossii_visa_gold/",
    "https://otzovik.com/reviews/usluga_nakopleniya_sberbank_rossii_kopilka/",
    "https://otzovik.com/reviews/programma_zaschita_doma_v_ooo_sk_sberbank_strahovanie/",
    "https://otzovik.com/reviews/sberbank_biznes_onlayn/",
    "https://otzovik.com/reviews/strahovaya_kompaniya_sberbank_strahovanie/",
    "https://otzovik.com/reviews/paevie_fondi_sberbanka_rf/",
    "https://otzovik.com/reviews/platezhnaya_karta_mir_sberbank/",
    "https://otzovik.com/reviews/momentalnaya_debetovaya_karta_sberbanka_momentum_visa_classic/",
    "https://otzovik.com/reviews/pensionnaya_karta_mir_sberbank/",
    "https://otzovik.com/reviews/individualniy_investicionniy_schet_sberbank/",
    "https://otzovik.com/reviews/igra_sberbanka_spasibomaniya/",
    "https://otzovik.com/reviews/servis_domklik_ot_sberbanka/",
    "https://otzovik.com/reviews/zarplatnaya_karta_sberbanka_rossii_visa_gold/",
    "https://otzovik.com/reviews/sotoviy_operator_pogovorim_ot_sberbanka/",
    "https://otzovik.com/reviews/prilozhenie_spasibo_ot_sberbanka/",
    "https://otzovik.com/reviews/vklad_sberbank_do_vostrebovaniya/",
    "https://otzovik.com/reviews/rabota_v_sberbanke_russia/",
]

vtb_categories = [
    "https://otzovik.com/reviews/bank_vtb_24/",
    "https://otzovik.com/reviews/vtb_strahovanie/",
    "https://otzovik.com/reviews/avtokredit_v_vtb/",
    "https://otzovik.com/reviews/vtb-onlayn/",
    "https://otzovik.com/reviews/ipoteka_v_banke_vtb/",
    "https://otzovik.com/reviews/vtb_bank_ukraina_cherkassi/",
    "https://otzovik.com/reviews/bank_vtb_gruziya/",
    "https://otzovik.com/reviews/multikarta_vtb_24/",
    "https://otzovik.com/reviews/bankomati_vtb_24/",
    "https://otzovik.com/reviews/avtokarta_vtb_24/",
    "https://otzovik.com/reviews/multikarta_banka_vtb/",
    "https://otzovik.com/reviews/debetovaya_multikarta_vtb/",
    "https://otzovik.com/reviews/prilozhenie_multibonus_vtb/",
    "https://otzovik.com/reviews/vtb_kassa/",
    "https://otzovik.com/reviews/plastikovaya_karta_banka_vtb24/",
    "https://otzovik.com/reviews/zarplatnaya_karta_visa_vtb24/",
    "https://otzovik.com/reviews/multivalyutnaya_plastikovaya_karta_visa_banka_vtb_24/",
    "https://otzovik.com/reviews/ipoteka_v_banke_vtb_24/",
    "https://otzovik.com/reviews/kreditnaya_karta_banka_vtb_24_classic/",
    "https://otzovik.com/reviews/sistema_telebank-vtb-24/",
    "https://otzovik.com/reviews/ipotechniy_kredit_banka_vtb24/",
    "https://otzovik.com/reviews/bonusnaya_programma_vtb-24_kollekciya/",
    "https://otzovik.com/reviews/kreditnaya_karta_banka_vtb-24/",
    "https://otzovik.com/reviews/negosudarstvenniy_pensionniy_fond_vtb_russia_saratov/",
    "https://otzovik.com/reviews/vtb24_internet_bank/",
    "https://otzovik.com/reviews/potrebitelskiy_kredit_bistriy_vtb-24/",
    "https://otzovik.com/reviews/brokerskoe_obsluzhivanie_vtb_24/",
    "https://otzovik.com/reviews/paket_uslug_vtb_privilegiya/",
    "https://otzovik.com/reviews/vklad_nakopitelniy_v_banke_vtb_24_russia/",
    "https://otzovik.com/reviews/refinansirovanie_ipoteki_v_vtb_24/",
    "https://otzovik.com/reviews/zarplatnaya_karta_banka_vtb_24_mir/",
    "https://otzovik.com/reviews/kredit_nalichnimi_vtb_24/",
    "https://otzovik.com/reviews/vklad_vigodniy_vtb_24_russia/",
    "https://otzovik.com/reviews/zarplatnaya_karta_mastercard_vtb24/",
    "https://otzovik.com/reviews/npf_vtb_pensionniy_fond_vtb_russia_sankt-peterburg/",
    "https://otzovik.com/reviews/refinansirovanie_potrebitelskogo_kredita_v_vtb/",
    "https://otzovik.com/reviews/kreditnie_kanikuli_bank_vtb_24/",
    "https://otzovik.com/reviews/vtb-onlayn-prilozhenie_dlya_android/",
    "https://otzovik.com/reviews/individualniy_investicionniy_schet_vtb/",
    "https://otzovik.com/reviews/kreditnaya_karta_banka_vtb_multikarta/",
    "https://otzovik.com/reviews/servis_vtb_moi_investicii/",
    "https://otzovik.com/reviews/kopilka_vtb24/",
    "https://otzovik.com/reviews/debetovaya_karta_mir_vtb/",
    "https://otzovik.com/reviews/raschetniy_schet_vtb/",
    "https://otzovik.com/reviews/kreditnaya_karta_vtb_karta_vozmozhnostey/",
    "https://otzovik.com/reviews/debetovaya_karta_vtb_magnit/",
]

mkb_categories = [
    "https://otzovik.com/reviews/moskovskiy_kreditniy_bank_mkb/",
    "https://otzovik.com/reviews/debetovaya_karta_oao_moskovskiy_kreditniy_bank/",
    "https://otzovik.com/reviews/platezhnie_terminali_moskovskiy_kreditniy_bank/",
    "https://otzovik.com/reviews/bank_moskovskiy_kreditniy_bank/",
    "https://otzovik.com/reviews/nakopitelniy_schet_moskovskiy_kreditniy_bank_russia_moscow/",
]

dom_rf_categories = [
    "https://otzovik.com/reviews/bank_rossiyskiy_kapital_russia/",
    "https://otzovik.com/reviews/vklad_nadezhniy_bank_dom_rf/",
    "https://otzovik.com/reviews/debetovaya_karta_dom_rf_bank/",
]

categories_pages = sberbank_categories + vtb_categories + mkb_categories

assert len(sberbank_categories) == len(set(sberbank_categories))
assert len(vtb_categories) == len(set(vtb_categories))
assert len(mkb_categories) == len(set(mkb_categories))
assert len(dom_rf_categories) == len(set(dom_rf_categories))

assert len(categories_pages) == len(set(categories_pages))

assert len(companies_pages) == len(set(companies_pages))

parser = Parser(companies_pages, categories_pages)
asyncio.run(parser.get_reviews_by_service())
