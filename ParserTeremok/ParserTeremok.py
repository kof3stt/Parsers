from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import time
import certifi


class ParserTeremok:
    def __init__(self):
        self.chrome_options = webdriver.ChromeOptions()
        self.chrome_options.add_argument('--ignore-certificate-errors')
        self.chrome_options.add_argument('--ignore-ssl-errors')
        self.chrome_options.add_argument(f"--ssl-certificates-path={certifi.where()}")
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
        time.sleep(5)
        categories_elem = self.browser.find_elements(By.CLASS_NAME, 'b-catalog__nav-item')
        for category in categories_elem:
            category.find_element(By.TAG_NAME, 'a').click()
            self.get_products_urls_from_category(category)
            self.browser.back()

    def parse_products(self):
        for url in self.products_links:
            self.browser.get(url)

    def print_products_links(self):
        for key in self.products_links:
            for link in self.products_links[key]:
                print(f'Категория товара: \033[92m{key}\033[0m, ссылки на страницу товара: \033[92m{link}\033[0m')
        print(f'Количество категорий: {len(self.products_links)}')


if __name__ == "__main__":
    with ParserTeremok() as parser:
        parser.get_products_urls('https://teremok.ru/menu/category/novinki/')
        parser.print_products_links()
