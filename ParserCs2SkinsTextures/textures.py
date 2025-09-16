import time
import base64
import os
import shutil
import certifi
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException, TimeoutException


WEAPONS = ['Zeus-x27', 'CZ75-Auto', 'Desert-Eagle', 'Dual-Berettas', 'Five-SeveN', 'Glock-18', 'P2000', 'P250', 'R8-Revolver', 'Tec-9', 'USP-S',
           'MAC-10', 'MP5-SD', 'MP7', 'MP9', 'PP-Bizon', 'P90', 'UMP-45',
           'MAG-7', 'Nova', 'Sawed-Off', 'XM1014',
           'M249', 'Negev',
           'AK-47', 'AUG', 'AWP', 'FAMAS', 'G3SG1', 'Galil-AR', 'M4A1-S', 'M4A4', 'SCAR-20', 'SG-553', 'SSG-08',
           'Karambit']


class ParserTextures:
    def __init__(self, base_url, texture_dir):
        self.chrome_options = webdriver.ChromeOptions()
        self.chrome_options.add_argument('--ignore-certificate-errors')
        self.chrome_options.add_argument('--ignore-ssl-errors')
        self.chrome_options.add_argument(f"--ssl-certificates-path={certifi.where()}")
        # self.chrome_options.add_argument("--autoplay-policy=no-user-gesture-required")
        self.chrome_options.add_argument('--disable-cache')
        # self.chrome_options.add_argument('--headless')
        # self.chrome_options.add_argument('--disable-gpu')
        # self.chrome_options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2,
        #                                                           "profile.managed_default_content_settings.stylesheet": 2,})
        self.chrome_options.add_experimental_option(
            "excludeSwitches", ['enable-automation', 'enable-logging'])
        self.base_url = base_url
        self.texture_dir = texture_dir
        self.browser = webdriver.Chrome(options=self.chrome_options)

    def __enter__(self):
        self.browser.maximize_window()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self.browser.service.process:
                self.browser.quit()
        except Exception as e:
            print(f"Error during shutdown: {e}")
        finally:
            if hasattr(self.browser, 'service'):
                self.browser.service.stop()

    def create_directory(self):
        if os.path.exists(self.texture_dir):
            shutil.rmtree(self.texture_dir)
        os.makedirs(self.texture_dir, exist_ok=True)

    def get_all_weapons(self):
        self.create_directory()
        for weapon in WEAPONS:
            self.browser.get(f'{self.base_url}/weapon/{weapon}')
            skin_links = [el.get_attribute('href') for el in self.browser.find_elements(By.CSS_SELECTOR, '.well.result-box.nomargin > a:not(.nounderline)')]
            for skin_link in skin_links:
                self.parse_item_page(skin_link)
                time.sleep(0.5)

    def parse_item_page(self, skin_link):
        self.browser.get(skin_link)
        try:
            WebDriverWait(self.browser, 3).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'h1'))
            )
        except TimeoutException:
            print("\033[91m" + f"ERROR, msg=time out error, page={skin_link}" + "\033[0m")
            return
        try:
            texture_button = self.browser.find_element(By.CSS_SELECTOR, 'a[href="#preview-texture"] > span.hidden-xs')
        except NoSuchElementException:
            print("\033[91m" + f"ERROR, msg=texture not found, page={skin_link}" + "\033[0m")
            return
        texture_button.click()
        texture_locator = (By.CSS_SELECTOR, 'div.active .skin-details-previews a')
        WebDriverWait(self.browser, 2).until(EC.presence_of_all_elements_located(texture_locator))

        image_url = self.browser.find_element(*texture_locator).get_attribute('href')
        
        js_script = f"""
            const done = arguments[0];
            fetch("{image_url}")
                .then(resp => resp.blob())
                .then(blob => {{
                    const reader = new FileReader();
                    reader.onloadend = () => done(reader.result);
                    reader.readAsDataURL(blob);
                }})
                .catch(err => done(null));
        """
        try:
            base64_data = self.browser.execute_async_script(js_script)
        except Exception as e:
            print(f"\033[91m + JS execution error: {e}" + "\033[0m")
            return

        if base64_data is None:
            print(f"\033[91m" + "JS fetch failed or blocked: {image_url}" + "\033[0m")
            return

        try:
            _, encoded = base64_data.split(",", 1)
            data = base64.b64decode(encoded)
            filename = os.path.basename(image_url.split('?')[0])
            filepath = os.path.join(self.texture_dir, filename)
            with open(filepath, 'wb') as f:
                f.write(data)
            print("\033[92m" + f"OK, texture saved: {skin_link}" + "\033[0m")
        except Exception as e:
            print(f"\033[91m" + "Error saving file: {e}, url={image_url}" + "\033[0m")

        print("\033[92m" + f"OK, page={skin_link}" + "\033[0m")


if __name__ == "__main__":
    start = time.perf_counter()
    with ParserTextures('https://stash.clash.gg', texture_dir='textures') as parser:
        parser.get_all_weapons()
    print(f'Время выполнения скрипта: {time.perf_counter() - start} секунд')
