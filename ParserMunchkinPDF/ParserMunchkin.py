import os
import re
import fitz
import json
import pandas as pd
from PIL import Image


class PDFParser:
    def __init__(self, file_path, directory_name, zoom = 1, crop_margins = None):
        '''
        Инициализирует объект PDFParser.
        
        Параметры:
            file_path (str): Путь к PDF-файлу, в котором сохранены карточки манчкина.
            directory_name (str): Имя директории для сохранения изображений карточек.
            zoom (int, optional): Коэффициент увеличения разрешения. По умолчанию 1.
            crop_margins (tuple, optional): Отступы для обрезки (верх, право, низ, лево). По умолчанию None.
        '''
        self.file_path = file_path
        self.directory_name = directory_name
        self.zoom = zoom
        self.crop_margins = crop_margins

    def download_images(self):
        '''
        Обрабатывает PDF-файл, сохраняет каждую страницу как изображение в формате PNG, обрезает изображения при необходимости.

        Возвращает:
            tuple: Два списка словарей с данными карт:
                - door_cards: Список карт типа "Дверь".
                - treasure_cards: Список карт типа "Сокровище".
        '''
        os.makedirs(self.directory_name, exist_ok=True)

        pdf_document = fitz.open(self.file_path)

        door_cards = []
        treasure_cards = []

        for page_number in range(len(pdf_document)):
            page = pdf_document.load_page(page_number)
    
            text = page.get_text().strip()

            matrix = fitz.Matrix(self.zoom, self.zoom)
            pix = page.get_pixmap(matrix=matrix)

            image_path = os.path.join(self.directory_name, f"page_{page_number + 1}.png")
            pix.save(image_path)

            if self.crop_margins is not None:
                self.crop_image(image_path)

            card_description = self.parse_description(text, page_number)
            card_description['Путь к изображению'] = image_path

            if card_description['Тип карты'] == 'Сокровище':
                treasure_cards.append(card_description)
            else:
                door_cards.append(card_description)

        return door_cards, treasure_cards

    def crop_image(self, image_path):
        '''
        Обрезает белые полосы вокруг изображения.

        Параметры:
            image_path (str): Путь к изображению для обрезки.
        '''
        image = Image.open(image_path)
        width, height = image.size

        left = self.crop_margins[3]  # Левый отступ
        top = self.crop_margins[0]  # Верхний отступ
        right = width - self.crop_margins[1]  # Правый отступ
        bottom = height - self.crop_margins[2]  # Нижний отступ

        cropped_image = image.crop((left, top, right, bottom))
        cropped_image.save(image_path)

    @staticmethod
    def parse_description(text, card_number):
        '''
        Парсит текст карты и извлекает информацию о ней.

        Параметры:
            text (str): Текст карты, извлечённый из PDF.
            card_number (int): Номер страницы карты (номер страницы в PDF файле).

        Возвращает:
            dict: Словарь с данными карты, включая тип, название, цену, бонусы и другие атрибуты.
        '''
        if card_number < 37 or 83 < card_number < 120:
            text = text.replace('“', '').replace('”', '')

            card_description = {'Тип карты' : 'Сокровище', 'Название карты' : None, 'Цена' : None, 'Бонус' : None, 'Ограничение' : None, 'Особенности' : None, 'Описание' : None}

            price = re.search(r'(\d+ голдов)|(без цены)', text)
            if price is not None:
                card_description['Цена'] = price.group()
                text = text.replace(price.group(), '').strip()

            bonus = re.search(r'(бонус \+\d+(\s*\(\+3 ДЛЯ ЭЛЬФОВ\))?)|(без бонуса)', text, flags=re.IGNORECASE)
            if bonus is not None:
                card_description['Бонус'] = bonus.group().capitalize().replace('\n', ' ').replace('  ', ' ')
                text = text.replace(bonus.group(), '').strip()

            restrictions = re.search(
                r'(Только для игроков\-женщин\s*\(или мужчин под «Сменой пола»\))|'
                r'(Только для игроков\-мужчин\s*\(или женщин под «Сменой пола»\))|'
                r'(Только для \w+)|'
                r'(Не для \w+)',
                text, flags=re.DOTALL
            )
            if restrictions is not None:
                card_description['Ограничение'] = restrictions.group().replace('\n', '').replace('  ', ' ').strip()
                text = text.replace(restrictions.group(), '').strip()

            features = re.search(r'(в 2 руки(?:\s+|\n)Большая)|(в 1 руку(?:\s+|\n)Большой)|(в 2 руки)|(в 1 руку)|(Обувка)|(ПОЛУЧИ УРОВЕНЬ)|(Броник(?:\s+|\n)Большой)|(Броник)|(Головняк)', text, flags=re.S)
            if features is not None:
                card_description['Особенности'] = features.group().replace('\n', ' ').strip()
                text = text.replace(features.group(), '').strip()

            name = re.search(r'(ЗАПОЗДАЛОЕ\s*ПРОЗРЕНИЕ\s*\(сандвич с селёдкой и\s*лимбургским сыром\))|(\b[“1А-ЯЁ”][“А-ЯЁ0-9\-!,\s”]{3,}\b)', text)
            if name is not None:
                card_description['Название карты'] = name.group().replace('\n', ' ').replace('- ', '-').replace('  ', ' ').removesuffix('В ').strip()
                text = text.replace(name.group().removesuffix('В '), '').strip()

            card_description['Описание'] = text.replace('\n', ' ').replace('  ', ' ').strip() if text else None

        elif 36 < card_number < 72 or card_number in (83, 82):
            card_description = {'Тип карты': 'Дверь', 'Название карты' : None, 'Уровень монстра' : None, 'Уровни за победу' : None, 'Непотребство' : None, 'Сокровища за победу' : None, 'Особенности' : None, 'Действие' : None}

            if card_number < 67 or card_number in (83, 82):
                obscenity = re.search(r'Непотребство:\s*(.*?)(?=\d+\s*сокровищ)', text, flags=re.DOTALL)
                if obscenity is not None:
                    card_description['Непотребство'] = obscenity.group().replace('\n', ' ').removeprefix('Непотребство:').strip()
                    card_description['Непотребство'] = card_description['Непотребство'][0].upper() + card_description['Непотребство'][1:]
                    text = text.replace(obscenity.group(), '').strip()
                
                treasure = re.search(r'^\d сокровищ[ае]', text)
                if treasure is not None:
                    card_description['Сокровища за победу'] = treasure.group().strip()
                    text = text.replace(treasure.group(), '').strip()
                
                monster_level = re.search(r'^УРОВЕНЬ \d{1,2}', text)
                if monster_level is not None:
                    card_description['Уровень монстра'] = monster_level.group().strip()
                    text = text.replace(monster_level.group(), '').strip()

                features = re.search(r'^Андеды?', text)
                if features is not None:
                    card_description['Особенности'] = features.group().strip()
                    text = text.replace(features.group(), '').strip()

                name = re.search(r'(БЛУЖДАЮЩИЙ НОС\s*\(он же Сопливый Нос. Выздоровел\))|(ТРАВА В ГОРШКЕ)|(\b[\dA-ZА-ЯЁ-]{2,}(?:\s[A-ZА-ЯЁ]{2,})*\b)', text)
                if name is not None:
                    card_description['Название карты'] = name.group().replace('\n', ' ').strip()
                    text = text.replace(name.group(), '').strip()

                levels_for_win = re.search(r'\d уровня$', text)
                if levels_for_win is not None:
                    card_description['Уровни за победу'] = levels_for_win.group()
                    if text.count(levels_for_win.group()) > 1:
                        text = text.removesuffix(levels_for_win.group())
                    else:
                        text = text.replace(levels_for_win.group(), '').strip()

                card_description['Действие'] = text.replace('\n', ' ').strip() if text else None

            else:
                monster_level = re.search(r'^УРОВЕНЬ \d{1,2}', text)
                if monster_level is not None:
                    card_description['Уровень монстра'] = monster_level.group().strip()
                    text = text.replace(monster_level.group(), '').strip()

                features = re.search(r'^Андеды?', text)
                if features is not None:
                    card_description['Особенности'] = features.group().strip()
                    text = text.replace(features.group(), '').strip()

                text = text.replace('\n', ' ')
                name = re.search(r'\b[\dA-ZА-ЯЁ-]{2,}(?:\s[A-ZА-ЯЁ]{2,})*\b', text)
                if name is not None:
                    card_description['Название карты'] = name.group().strip()
                    text = text.replace(name.group(), '').strip()

                treasure = re.search(r'\d сокровищ[ае]?$', text)
                if treasure is not None:
                    card_description['Сокровища за победу'] = treasure.group().strip()
                    text = text.replace(treasure.group(), '').strip()

                levels_for_win = re.search(r'\d уровн(я|ей)$', text)
                if levels_for_win is not None:
                    card_description['Уровни за победу'] = levels_for_win.group()
                    if text.count(levels_for_win.group()) > 1:
                        text = text.removesuffix(levels_for_win.group())
                    else:
                        text = text.replace(levels_for_win.group(), '').strip()

                obscenity = re.search(r'Непотребство: .+$', text)
                if obscenity is not None:
                    card_description['Непотребство'] = obscenity.group().removeprefix('Непотребство:').strip()
                    card_description['Непотребство'] = card_description['Непотребство'][0].upper() + card_description['Непотребство'][1:]
                    text = text.replace(obscenity.group(), '').strip()
                
                card_description['Действие'] = text.replace('\n', ' ').replace('  ', ' ').strip() if text else None
        else:
            card_description = {'Тип карты': 'Дверь', 'Название карты' : None, 'Уровень монстра' : None, 'Уровни за победу' : None, 'Непотребство' : None, 'Сокровища за победу' : None, 'Особенности' : None, 'Действие' : None}

            text = text.replace('\n', ' ')
            name = re.search(r'(ГАДКАЯ ПАРОЧКА)|(ПСИХ)|(МОЗГ)|(ВОР)|(ВОИН)|(ВОЛШЕБНИК)|(СТАРИКАН)|(АМБАЛ)|(ДЕТЁНЫШ)|(БРОДЯЧАЯ ТВАРЬ)|(ПОИСТИНЕ ГНУСНОЕ ПРОКЛЯТИЕ!)|(ПРОКЛЯТИЕ! ПОДОХОДНЫЙ НАЛОГ)|(ПРОКЛЯТИЕ! НЕВЕЛИКА ПОТЕРЯ)|(ПРОКЛЯТИЕ! БОЛЬШАЯ ПОТЕРЯ)|(ПРОКЛЯТИЕ! УТРАТА КЛАССА)|(ПРОКЛЯТИЕ! ПОТЕРЯ РАСЫ)|(ПРОКЛЯТИЕ! КУРИЦА НА БАШНЕ)|(ПРОКЛЯТИЕ! СМЕНА ПОЛА)|(ПРОКЛЯТИЕ! СМЕНА РАСЫ)|(ПРОКЛЯТИЕ! СМЕНА КЛАССА)|(ПРОКЛЯТИЕ! УТКА ОБРЕЧЁННОСТИ)|(ПРОКЛЯТИЕ! ЗЕРКАЛО ЗЛОСЧАСТЬЯ)|(ПРОКЛЯТИЕ! ПОТЕРЯ ДВУХ КАРТ)|(ПРОКЛЯТИЕ!)|(БОЖЕСТВЕННОЕ ВМЕШАТЕЛЬСТВО)|(УШЁЛ НА БАЗУ)|(ИЛЛЮЗИЯ)|(ЧИТ!)|(ПОМОГИ, ЧЕМ МОЖЕШЬ!)|(СУПЕРМАНЧКИН)|(ПОЛУКРОВКА\s\(ранее Расовый коктейль\))|(ПОЛУКРОВКА)|(ЭЛЬФ)|(ДВАРФ)|(ХАФЛИНГ)|(КЛИРИК)', text)
            if name is not None:
                card_description['Название карты'] = name.group().strip()
                text = text.replace(name.group(), '').strip()
            features = re.search(r'(^[+\-]\d{1,2} (К|ОТ) УРОВН[ЮЯ] МОНСТР[АУ] ?(\(минимум 1-й уровень\))?)|(Класс$)|(Раса$)', text)
            if features is not None:
                card_description['Особенности'] = features.group().strip()
                text = text.replace(features.group(), '').strip()

            card_description['Действие'] = text.strip() if text else None

        return card_description

    @staticmethod
    def load_cards(json_name, door_cards, treasure_cards):
        '''
        Сохраняет данные карт в JSON-файл.

        Параметры:
            json_name (str): Имя JSON-файла для сохранения.
            door_cards (list): Список карт типа "Дверь".
            treasure_cards (list): Список карт типа "Сокровище".
        '''
        with open(json_name, 'w', encoding = 'utf-8') as file:
            json.dump(treasure_cards + door_cards, file, ensure_ascii=False, indent = 4)


if __name__ == '__main__':
    file_path = 'munchkin_cards.pdf'
    directory_name = 'cards'

    parser = PDFParser(file_path, directory_name, zoom = 10, crop_margins = (10, 10, 0, 0))
    door_cards, treasure_cards = parser.download_images()
    print(f"Сохранено изображений: {len(door_cards) + len(treasure_cards)}")

    df_treasure_cards = pd.DataFrame(treasure_cards)
    df_treasure_cards.drop(columns=["Описание"], inplace=True)
    print('\033[92mКарты сокровищ:\033[0m')
    print(df_treasure_cards.to_markdown(), end = '\n\n\n')

    df_door_cards = pd.DataFrame(door_cards)
    df_door_cards.drop(columns=["Непотребство", "Действие"], inplace=True)
    print('\033[92mКарты дверей:\033[0m')
    print(df_door_cards.to_markdown())

    parser.load_cards('muchkin_1.json', door_cards, treasure_cards)
