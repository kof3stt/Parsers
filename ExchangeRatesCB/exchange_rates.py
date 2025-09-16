import requests
from fake_useragent import UserAgent
from pandas import DataFrame
from datetime import date
from enum import Enum


headers = {
    'user-agent': UserAgent().random,
    'X-Requested-With': 'XMLHttpRequest'
}

url = 'https://cbr.ru/cursonweek'


class Currencies(str, Enum):
    CNY = 'R01375'
    USD = 'R01235'
    EUR = 'R01239'


def get_exchange_rate(currency: Currencies) -> float:
    """
    Получает текущий курс валюты с сайта Центробанка РФ
    
    :param currency: Валюта из перечисления Currencies
    :return: Текущий курс валюты
    """
    url = 'https://cbr.ru/cursonweek'
    params = {'DT': '', 'val_id': currency.value}
    response = requests.get(url, headers=headers, params=params).json()[0]
    return float(response['curs'])


print(get_exchange_rate(Currencies.CNY))


currencies = [
    {'name': 'CNY, 1¥', 'val_id': 'R01375'},
    {'name': 'USD, 1$', 'val_id': 'R01235'},
    {'name': 'EUR, 1€', 'val_id': 'R01239'}
]

responses = []
for currency in currencies:
    params = {'DT': '', 'val_id': currency['val_id']}
    response = requests.get(url, headers=headers, params=params).json()[0]
    responses.append({
        'name': currency['name'],
        'curs': float(response['curs']),
        'diff': float(response['diff']),
        'prev_date': date.fromisoformat(response['prevDate'][:10]),
        'curr_date': date.fromisoformat(response['data'][:10])
    })

data = {
    'Курсы валют': [response['name'] for response in responses],
    date.strftime(responses[0]['prev_date'], '%d.%m.%Y'): [
        response['curs'] - response['diff'] for response in responses
    ],
    date.strftime(responses[0]['curr_date'], '%d.%m.%Y'): [
        response['curs'] for response in responses
    ]
}

df = DataFrame(data)
print(df)
