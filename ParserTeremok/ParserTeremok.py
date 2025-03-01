import time
import json
import certifi
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class ParserTeremok:
    def __init__(self):
        self.chrome_options = webdriver.ChromeOptions()
        self.chrome_options.add_argument('--ignore-certificate-errors')
        self.chrome_options.add_argument('--ignore-ssl-errors')
        self.chrome_options.add_argument(f"--ssl-certificates-path={certifi.where()}")
        self.chrome_options.add_argument('--disable-cache')
        self.chrome_options.add_argument('--headless')
        self.chrome_options.add_argument('--disable-gpu')
        self.chrome_options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2,
                                                                  "profile.managed_default_content_settings.stylesheet": 2,})
        self.chrome_options.add_experimental_option(
            "excludeSwitches", ['enable-automation', 'enable-logging'])
        self.browser = webdriver.Chrome(options=self.chrome_options)
        self.products_links = {}
        self.products_info = {}

    def __enter__(self):
        self.browser.maximize_window()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.browser.quit()

    def get_products_urls_from_category(self, category):
        locator = (By.CLASS_NAME, 'b-slider-menu__slide-item')
        WebDriverWait(self.browser, 10).until(EC.presence_of_all_elements_located(locator))
        products = self.browser.find_elements(*locator)
        for product in products:
            link = product.find_element(By.CLASS_NAME, 'b-slider-menu__slide-item-inner').get_attribute('href')
            self.products_links.setdefault(category.text.strip(), []).append(link)

    def get_products_urls(self, url):
        self.browser.get(url)
        time.sleep(2)
        categories_elem = self.browser.find_elements(By.CLASS_NAME, 'b-catalog__nav-item')
        for category in categories_elem:
            category.find_element(By.TAG_NAME, 'a').click()
            self.get_products_urls_from_category(category)
            self.browser.back()

    def parse_products(self):
        for category in self.products_links:
            self.products_info[category] = []
            for url in self.products_links[category]:
                info_dict = dict.fromkeys(['Название продукта', 'Описание', 'Мера'])
                self.browser.get(url)
                WebDriverWait(self.browser, 10).until(EC.presence_of_element_located((By.CLASS_NAME, 'b-detail-product__info-body')))

                product_name = self.browser.find_element(By.CSS_SELECTOR, '.b-detail-product__title > h1').text
                info_dict['Название продукта'] = product_name

                product_description = self.browser.find_element(By.CSS_SELECTOR, '.b-detail-product__title > p').text
                info_dict['Описание'] = product_description if product_description else None

                weight = self.browser.find_element(By.CSS_SELECTOR, '.b-detail-product__info-row--header > .b-detail-product__info-cell:nth-child(2)').text
                info_dict['Мера'] = weight

                rows = self.browser.find_elements(By.CSS_SELECTOR, 'div.b-detail-product__info-row:not(.b-detail-product__info-row--header)')
                for row in rows:
                    key = row.find_element(By.CLASS_NAME, 'b-detail-product__info-cell').text
                    value = row.find_element(By.CSS_SELECTOR, '.b-detail-product__info-cell:nth-child(3)').text
                    info_dict[key] = value

                self.products_info[category].append(info_dict)

    def print_products_links(self):
        for key in self.products_links:
            for link in self.products_links[key]:
                print(f'Категория товара: \033[92m{key}\033[0m, ссылки на страницу товара: \033[92m{link}\033[0m')
        print(f'Количество категорий: {len(self.products_links)}')
        print(self.products_links)

    def print_products_info(self):
        print(self.products_info)

    def save_to_json(self, json_name):
        with open(json_name, 'w', encoding = 'utf-8') as file:
            json.dump(self.products_info, file, ensure_ascii=False, indent = 4)


if __name__ == "__main__":
    start = time.perf_counter()
    with ParserTeremok() as parser:
        parser.get_products_urls('https://teremok.ru/menu/category/novinki/')
        parser.parse_products()
        parser.print_products_links()
        parser.print_products_info()
        parser.save_to_json('teremok.json')
    print(f'Время выполнения скрипта: {time.perf_counter() - start} секунд')
