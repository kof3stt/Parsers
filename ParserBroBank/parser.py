from JSONSaver import JSONSaver
from typing import Optional
import requests
from itertools import cycle
from fake_useragent import FakeUserAgent
import lxml
from bs4 import BeautifulSoup


class Parser:
    def __init__(self, base_url, output_file, max_retries=10, request_timeout=7):
        self.base_url = base_url
        self.output_file = output_file
        self._saver = JSONSaver(output_file)
        self._max_retries = max_retries
        self._request_timeout = request_timeout
        self._processed_reviews = self.load_reviews_from_saver()
        self._proxy_list = cycle(self.set_proxy())
        self._ua = FakeUserAgent()

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

    def get_reviews(self):
        response = self.make_request(self.base_url)
        soup = BeautifulSoup(response.text, "lxml")
        next_page = soup.select_one("div.navigation__list").select_one(
            "a.next.page-numbers"
        )

        result_dict = {}
        reviews = soup.select("li.depth-1 > article.comment:not(.bro-author)")

        for review in reviews:
            review_url = review.find("a", {"href": True})["href"]

            if review_url in self._processed_reviews:
                print("\033[92m" + f"Already processed: {review_url}" + "\033[0m")
                continue

            login = review.select_one("header > cite > b").get_text()
            result_dict["Логин"] = login

            date = review.select_one("header > a > time")["datetime"]
            result_dict["Дата"] = date

            general_impression = review.select_one(
                "div.after-header > div.title_review"
            )
            if general_impression is not None:
                result_dict["Общее впечатление"] = general_impression.get_text().strip()
            else:
                result_dict["Общее впечатление"] = None

            score = review.select_one(
                "div.new-card__rating > span.new-card__rating_num"
            )
            if score is not None:
                result_dict["Оценка"] = int(score["data-count"])
            else:
                result_dict["Оценка"] = None

            review_text = review.select_one(
                "section.comment-content.comment > p"
            ).get_text()
            result_dict["Отзыв"] = review_text

            review_liked = int(
                review.select_one("div.score-comment > span.score-num").get_text()
            )
            result_dict["Лайки"] = review_liked

            result_dict["Ссылка на отзыв"] = review_url

            self._saver.save_review("Газпромбанк", result_dict)
            self._processed_reviews.add(review_url)
            print("\033[92m" + f"Saved review: {review_url}" + "\033[0m")
            result_dict = {}

        result_dict = {}
        while next_page != None:
            next_page_url = next_page["href"]
            response = self.make_request(next_page_url)
            soup = BeautifulSoup(response.text, "lxml")

            reviews = soup.select("li.depth-1 > article.comment:not(.bro-author)")

            for review in reviews:
                review_url = review.find("a", {"href": True})["href"]

                if review_url in self._processed_reviews:
                    print("\033[92m" + f"Already processed: {review_url}" + "\033[0m")
                    continue

                login = review.select_one("header > cite > b").get_text()
                result_dict["Логин"] = login

                date = review.select_one("header > a > time")["datetime"]
                result_dict["Дата"] = date

                general_impression = review.select_one(
                    "div.after-header > div.title_review"
                )
                if general_impression is not None:
                    result_dict["Общее впечатление"] = (
                        general_impression.get_text().strip()
                    )
                else:
                    result_dict["Общее впечатление"] = None

                score = review.select_one(
                    "div.new-card__rating > span.new-card__rating_num"
                )
                if score is not None:
                    result_dict["Оценка"] = int(score["data-count"])
                else:
                    result_dict["Оценка"] = None

                review_text = review.select_one(
                    "section.comment-content.comment > p"
                ).get_text()
                result_dict["Отзыв"] = review_text

                review_liked = int(
                    review.select_one("div.score-comment > span.score-num").get_text()
                )
                result_dict["Лайки"] = review_liked

                result_dict["Ссылка на отзыв"] = review_url

                self._saver.save_review("Газпромбанк", result_dict)
                self._processed_reviews.add(review_url)
                print("\033[92m" + f"Saved review: {review_url}" + "\033[0m")
                result_dict = {}

            next_page = soup.select_one("div.navigation__list").select_one(
                "a.next.page-numbers"
            )
        return next_page


parser = Parser("https://brobank.ru/banki/gazprombank/comments/", "reviews.json")
parser.get_reviews()
