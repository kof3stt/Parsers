import requests
from fake_useragent import UserAgent
from pandas import DataFrame
from datetime import date


headers = {
    'user-agent': UserAgent().random,
    'X-Requested-With': 'XMLHttpRequest'
}

url = 'https://cbr.ru/cursonweek'

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
