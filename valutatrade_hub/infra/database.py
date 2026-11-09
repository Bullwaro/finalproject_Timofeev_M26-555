import json
import os


class DatabaseManager:
    def load(self, file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            return json.load(file)

    def save(self, file_path, data):
        temp_path = file_path + ".tmp"

        try:
            with open(temp_path, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=4, ensure_ascii=False)

            os.replace(temp_path, file_path)

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
