import pandas as pd
import json


class Json2Pandas:
    def __init__(self, filename):
        self.filename = filename

    def load_dataframe(self):
        with open(self.filename, encoding="utf-8") as file:
            raw_data = json.load(file)
            reviews = raw_data["reviews"]
            dataframe = pd.DataFrame(reviews)
            return dataframe


converter = Json2Pandas("reviews.json")
dataframe = converter.load_dataframe()

dataframe["Дата"] = dataframe["Дата"].astype("datetime64[ns]")

dataframe.info()
print(
    f"Общее число отзывов: {len(dataframe)}\nОтзывы о Альфа-Банке: {len(dataframe.query("Сервис == 'Альфа-Банк'"))}"
)

df = dataframe.query("Сервис != 'Альфа-Банк'")
df.drop(columns=["service_url", "collected_at"], inplace=True)
df["Рекомендую друзьям"] = (
    df["Рекомендую друзьям"]
    .where(df["Рекомендую друзьям"] != "ДА", True)
    .where(df["Рекомендую друзьям"] != "НЕТ", False)
)
отзывы_после_01_01_2024 = df.query("Дата >= '2024-01-01'")
print(отзывы_после_01_01_2024)
