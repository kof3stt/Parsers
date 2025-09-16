import requests
from bs4 import BeautifulSoup
from fake_useragent import FakeUserAgent
import lxml
from itertools import cycle
import time
import json
from typing import Optional
from JSONSaver import JSONSaver


class Parser:
    def __init__(
        self,
        companies_pages: list[str],
        categories_pages: list[str],
        max_retries: int = 25,
        request_timeout: int = 6,
        output_file: str = "reviews.json",
    ):
        self._companies_pages = companies_pages
        self._categories_pages = categories_pages
        self._ua = FakeUserAgent()
        self._session = requests.Session()
        self._proxy_list = cycle(self.set_proxy())
        self._max_retries = max_retries
        self._request_timeout = request_timeout
        self._output_file = output_file
        self._saver = JSONSaver(output_file)
        self._processed_reviews = self.load_reviews_from_saver()

    def load_reviews_from_saver(self) -> set:
        processed = set()
        for review in self._saver.data.get("reviews", []):
            processed.add(review["Ссылка на отзыв"])
        return processed

    def make_request(self, url: str) -> Optional[requests.Response]:
        """Выполняет HTTP-запрос с использованием прокси"""
        headers = {"User-Agent": self._ua.random}
        for _ in range(self._max_retries):
            proxy = next(self._proxy_list)
            proxies = {"http": proxy, "https": proxy}
            try:
                response = requests.get(
                    url,
                    headers=headers,
                    proxies=proxies,
                    timeout=self._request_timeout,
                )
                print(
                    f"Requested with {proxy}, URL: {url}, status_code: {response.status_code}"
                )
                if response.status_code == 200:
                    return response
            except requests.exceptions.RequestException as e:
                print("\033[91m" + f"Request Error: {url} {e}" + "\033[0m")
        return None

    @classmethod
    def set_proxy(cls):
        proxy_list = []
        with open("proxies.txt", encoding="utf-8") as file:
            for line in file:
                proxy = line.rstrip().split(":")
                if len(proxy) == 4:
                    ip, port, login, password = proxy
                    proxy_list.append(f"http://{login}:{password}@{ip}:{port}")
                elif len(proxy) == 2:
                    ip, port = proxy
                    proxy_list.append(f"http://{ip}:{port}")
                else:
                    print("\033[91m" + f"Proxy Error: {proxy}" + "\033[0m")
        return proxy_list

    def get_all_services(self):
        services_urls = list()
        for base_url in self._companies_pages:
            response = self.make_request(base_url)
            soup = BeautifulSoup(response.text, "lxml")

            pager = soup.find("div", class_="pager")
            pages = [base_url]
            if pager is not None:
                last_page = (
                    "https://otzovik.com"
                    + pager.find_all("a", {"href": True}, recursive=False)[-1]["href"]
                )
                num_page = 2
                tmp_page = base_url + f"&page={num_page}"
                while (
                    tmp_page[tmp_page.find("&page=") :]
                    != last_page[last_page.find("&page=") :]
                ):
                    pages.append(tmp_page)
                    num_page += 1
                    tmp_page = tmp_page.rstrip(str(num_page - 1)) + str(num_page)
                pages.append(tmp_page)

            for page in pages:
                response = self.make_request(page)
                soup = BeautifulSoup(response.text, "lxml")
                services = soup.find("div", {"class": "product-list decor-n"})
                services_urls.extend(
                    [
                        "https://otzovik.com/" + service["href"]
                        for service in services.select("div div.product-photo a")
                    ]
                )
        services_urls.extend(self._categories_pages)
        return services_urls

    def get_reviews_by_service(self):
        services_url = self.get_all_services()
        for service_url in services_url:
            print("\033[92m" + f"Category: {service_url}" + "\033[0m")
            response = self.make_request(service_url)
            if response is None:
                print(
                    "\033[91m"
                    + f"Failed to get service page: {service_url}"
                    + "\033[0m"
                )
                continue

            soup = BeautifulSoup(response.text, "lxml")
            pager = soup.find("div", class_="pager")

            if pager is not None:
                last_page = (
                    "https://otzovik.com/"
                    + pager.find_all("a", {"href": True}, recursive=False)[-1]["href"]
                )
                last_page_num = int(last_page.removeprefix(service_url).rstrip("/"))
                pages = [service_url] + [
                    f"{service_url}{i}/" for i in range(2, last_page_num + 1)
                ]
            else:
                pages = [service_url]

            total_votes = int(soup.select_one("span.votes").get_text())
            vote_num = 1

            for page in pages:
                print("\033[92m" + f"Processing page: {page}" + "\033[0m")
                review_urls = self.get_all_reviews_by_page(page)
                for review_url in review_urls:
                    if review_url in self._processed_reviews:
                        print(
                            "\033[92m" + f"Already processed: {review_url}" + "\033[0m"
                        )
                        continue
                    review_result = self.parse_review(review_url)
                    self._saver.save_review(service_url, review_result)
                    self._processed_reviews.add(review_url)
                    print(
                        "\033[92m"
                        + f"Saved review: {review_url}, {vote_num}/{total_votes}"
                        + "\033[0m"
                    )
                    vote_num += 1

    def get_all_reviews_by_page(self, page_url):
        review_urls = []
        response = self.make_request(page_url)
        soup = BeautifulSoup(response.text, "lxml")
        reviews = soup.find_all("div", {"itemprop": "review"})
        for review in reviews:
            review_urls.append(
                review.find("meta", {"itemprop": "url", "content": True})["content"]
            )
        return review_urls

    def parse_review(self, review_url):
        result_dict = {}
        try:
            response = self.make_request(review_url)
            soup = BeautifulSoup(response.text, "lxml")

            service_name = soup.find(
                "span", {"class": "fn", "itemprop": "name"}
            ).get_text()
            result_dict["Сервис"] = service_name

            result_dict["Ссылка на отзыв"] = review_url

            review_container = soup.select_one("div.item.review-wrap")
            user_info = review_container.select_one("div.user-info")

            login = (
                user_info.select_one("a.user-login.fit-with-ava.url.fn")
                .find("span", {"itemprop": "name"})
                .get_text()
            )
            result_dict["Логин"] = login

            rep = user_info.select_one("div.karma").get_text()
            result_dict["Репутация пользователя"] = int(rep)

            location = user_info.select_one("div.user-location").get_text()
            result_dict["Локация пользователя"] = location

            total_reviews = user_info.select_one(".reviews-counter").get_text()
            result_dict["Все отзывы пользователя"] = int(total_reviews)

            date = review_container.select_one("span.review-postdate.dtreviewed").find(
                "abbr", {"class": "value", "title": True}
            )["title"]
            result_dict["Дата"] = date

            review_liked = review_container.select_one(
                "span.review-btn.review-yes.tooltip-top"
            ).get_text()
            result_dict["Лайки"] = int(review_liked)

            review_coms = review_container.select_one(
                "a.review-btn.review-comments.tooltip-top"
            ).get_text()
            result_dict["Комментарии к отзыву"] = int(review_coms)

            advantages = (
                review_container.select_one("div.item-right")
                .select_one("div.review-plus")
                .get_text()
            )
            result_dict["Достоинства"] = advantages.removeprefix("Достоинства:").strip()

            disadvantages = (
                review_container.select_one("div.item-right")
                .select_one("div.review-minus")
                .get_text()
            )
            result_dict["Недостатки"] = disadvantages.removeprefix(
                "Недостатки:"
            ).strip()

            review_text = (
                review_container.select_one("div.item-right")
                .select_one("div.review-body.description")
                .get_text()
            )
            result_dict["Отзыв"] = review_text

            general_impression = review_container.find(
                "span", {"class": "summary", "itemprop": "name"}
            ).get_text()
            result_dict["Общее впечатление"] = general_impression

            score = review_container.select_one(
                "div.rating-score.tooltip-right"
            ).get_text()
            result_dict["Оценка"] = int(score)

            recomendation = review_container.select_one("td.recommend-ratio").get_text()
            result_dict["Рекомендую друзьям"] = recomendation

            return result_dict

        except Exception as e:
            print("\033[91m" + f"Error parsing review {review_url}: {e}" + "\033[0m")
            return None


companies_pages = [
    # "https://otzovik.com/?official_products=%D0%93%D0%B0%D0%B7%D0%BF%D1%80%D0%BE%D0%BC%D0%B1%D0%B0%D0%BD%D0%BA",
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
parser.get_reviews_by_service()
# print(parser.parse_review("https://otzovik.com/review_13787815.html"))
