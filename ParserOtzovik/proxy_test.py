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
