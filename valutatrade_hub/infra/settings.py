import json


class SettingsLoader:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)

        return cls._instance

    def __init__(self):
        if not hasattr(self, "_config"):
            self._config = {}
            self.reload()

    def get(self, key: str, default=None):
        return self._config.get(key, default)

    def reload(self):
        with open("config.json", "r", encoding="utf-8") as file:
            self._config = json.load(file)
