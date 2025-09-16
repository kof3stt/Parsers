import json
import os
from datetime import datetime
from typing import Dict, Any


class JSONSaver:
    def __init__(self, filename: str = "reviews.json"):
        self.filename = filename
        self.data = self.load_existing_data()

    def load_existing_data(self) -> Dict[str, Any]:
        """Загружает существующие данные из файла, если он существует"""
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r", encoding="utf-8") as file:
                    return json.load(file)
            except (json.JSONDecodeError, FileNotFoundError):
                return {
                    "metadata": {
                        "created": datetime.now().isoformat(),
                        "updated": datetime.now().isoformat(),
                        "total_reviews": 0,
                    },
                    "reviews": [],
                }
        else:
            return {
                "metadata": {
                    "created": datetime.now().isoformat(),
                    "updated": datetime.now().isoformat(),
                    "total_reviews": 0,
                },
                "reviews": [],
            }

    def save_review(self, service_url: str, review_data: Dict):
        """Сохраняет отзыв"""
        self.data["metadata"]["updated"] = datetime.now().isoformat()

        review_data["service_url"] = service_url

        review_data["collected_at"] = datetime.now().isoformat()

        self.data["reviews"].append(review_data)
        self.data["metadata"]["total_reviews"] = len(self.data["reviews"])

        self.save_to_file()

    def save_to_file(self):
        """Сохраняет данные в файл"""
        with open(self.filename, "w", encoding="utf-8") as file:
            json.dump(self.data, file, ensure_ascii=False, indent=2)

    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику по сохраненным данным"""
        return {
            "total_reviews": self.data["metadata"]["total_reviews"],
            "last_update": self.data["metadata"]["updated"],
        }
