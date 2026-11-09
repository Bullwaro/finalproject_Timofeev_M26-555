import os
from datetime import UTC, datetime

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.parser_service.config import ParserConfig


class RatesStorage:
    def __init__(self, config: ParserConfig):
        self.config = config
        self.db = DatabaseManager()

    def load_rates(self):
        try:
            data = self.db.load(self.config.RATES_FILE_PATH)
        except FileNotFoundError:
            return None

        if not isinstance(data, dict) or not isinstance(data.get("rates"), dict):
            raise ApiRequestError("Некорректный формат rates.json")

        return data

    def save_rates(self, update_data: dict):
        new_rates = update_data.get("rates")

        if not isinstance(new_rates, dict):
            raise ApiRequestError("Некорректные данные курсов")

        current_data = self.load_rates() or {}

        rates = dict(current_data.get("rates", {}))
        rates.update(new_rates)

        sources = dict(current_data.get("sources", {}))
        sources.update(update_data.get("sources", {}))

        pairs = dict(current_data.get("pairs", {}))

        updated_at = update_data["updated_at"]
        base_currency = self.config.BASE_FIAT_CURRENCY

        for code, rate in new_rates.items():
            if code == base_currency:
                continue

            pair = f"{code}_{base_currency}"
            source = sources.get(pair, "unknown")

            pairs[pair] = {
                "rate": rate,
                "updated_at": updated_at,
                "source": source,
            }

        cache_data = {
            **current_data,
            "rates": rates,
            "pairs": pairs,
            "sources": sources,
            "updated_at": updated_at,
            "last_refresh": update_data.get("last_refresh", updated_at),
            "source": update_data.get("source", ""),
        }

        history = self._load_history()
        history_ids = {record.get("id") for record in history}

        timestamp = (
            datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
        )

        for code, rate in new_rates.items():
            if code == base_currency:
                continue

            pair = f"{code}_{base_currency}"
            source = sources.get(pair, "unknown")

            record_id = f"{pair}_{timestamp}"

            if record_id in history_ids:
                continue

            history.append(
                {
                    "id": record_id,
                    "from_currency": code,
                    "to_currency": base_currency,
                    "rate": rate,
                    "timestamp": timestamp,
                    "source": source,
                    "meta": {},
                }
            )

        self._ensure_directory(self.config.HISTORY_FILE_PATH)
        self._ensure_directory(self.config.RATES_FILE_PATH)

        self.db.save(self.config.HISTORY_FILE_PATH, history)
        self.db.save(self.config.RATES_FILE_PATH, cache_data)

    def _load_history(self):
        try:
            history = self.db.load(self.config.HISTORY_FILE_PATH)
        except FileNotFoundError:
            return []

        if not isinstance(history, list):
            raise ApiRequestError("Некорректный формат exchange_rates.json")

        return history

    @staticmethod
    def _ensure_directory(file_path: str):
        directory = os.path.dirname(file_path)

        if directory:
            os.makedirs(directory, exist_ok=True)
