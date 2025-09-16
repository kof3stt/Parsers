import requests


def test_proxy(proxy_url):
    try:
        response = requests.get(
            "https://httpbin.org/ip",
            proxies={"http": proxy_url, "https": proxy_url},
            timeout=10,
        )
        return response.status_code == 200
    except:
        return False


with open("proxies.txt", encoding="utf-8") as file:
    for line in file:
        proxy = line.rstrip().split(":")
        if len(proxy) == 4:
            ip, port, login, password = proxy
            proxy_url = f"http://{login}:{password}@{ip}:{port}"
        else:
            ip, port = proxy
            proxy_url = f"http://{ip}:{port}"
        if test_proxy(proxy_url):
            print(f"Working proxy: {proxy_url}")
        else:
            print(f"Not working: {proxy_url}")


# import requests
# from fake_useragent import FakeUserAgent

# ua = FakeUserAgent(min_percentage=0.5)
# headers = {
#     "User-Agent": ua.random,
#     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
#     "Accept-Language": "ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3",
#     "Accept-Encoding": "gzip, deflate, br",
#     "Connection": "keep-alive",
#     "Upgrade-Insecure-Requests": "1",
# }

# proxy = "http://XbjK0H:ZrEH9C@212.81.39.92:9514"
# proxies = {
#     "http": proxy,
#     "https": proxy.replace('http://', 'https://'),
# }

# url = "https://otzovik.com/"

# response = requests.get(url, headers=headers, timeout=10)
# print(response.status_code)
# print(response.text[:500])

# print("\033[91m" + f"Category: {1}" + "\033[0m")
# from datetime import datetime

# print(datetime.fromisoformat("2021-05-21"))
# print('https://otzovik.com//?official_products=%D0%90%D0%BB%D1%8C%D1%84%D0%B0-%D0%91%D0%B0%D0%BD%D0%BA&page=3'.removeprefix('https://otzovik.com/?official_products=%D0%90%D0%BB%D1%8C%D1%84%D0%B0-%D0%91%D0%B0%D0%BD%D0%BA'
# ))