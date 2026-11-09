from abc import ABC, abstractmethod

import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.config import ParserConfig


class BaseApiClient(ABC):
    def __init__(self, config: ParserConfig):
        self.config = config

    @abstractmethod
    def fetch_rates(self) -> dict[str, float]:
        pass


class CoinGeckoClient(BaseApiClient):
    def fetch_rates(self) -> dict[str, float]:
        crypto_ids = [
            self.config.CRYPTO_ID_MAP[code]
            for code in self.config.CRYPTO_CURRENCIES
            if code in self.config.CRYPTO_ID_MAP
        ]

        params = {
            "ids": ",".join(crypto_ids),
            "vs_currencies": "usd",
        }

        try:
            response = requests.get(
                self.config.COINGECKO_URL,
                params=params,
                timeout=self.config.REQUEST_TIMEOUT,
            )

            if response.status_code != 200:
                raise ApiRequestError(f"CoinGecko вернул HTTP {response.status_code}")

            data = response.json()

        except requests.exceptions.RequestException as error:
            raise ApiRequestError(f"Ошибка соединения с CoinGecko: {error}") from error
        except ValueError as error:
            raise ApiRequestError("CoinGecko вернул некорректный JSON") from error

        rates = {}

        for code in self.config.CRYPTO_CURRENCIES:
            coin_id = self.config.CRYPTO_ID_MAP.get(code)

            if coin_id not in data or "usd" not in data[coin_id]:
                raise ApiRequestError(f"Курс {code} отсутствует в ответе CoinGecko")

            rate = data[coin_id]["usd"]

            if (
                not isinstance(rate, (int, float))
                or isinstance(rate, bool)
                or rate <= 0
            ):
                raise ApiRequestError(f"Некорректный курс {code} от CoinGecko")

            rates[f"{code}_USD"] = float(rate)

        return rates


class ExchangeRateApiClient(BaseApiClient):
    def fetch_rates(self) -> dict[str, float]:
        api_key = self.config.EXCHANGERATE_API_KEY

        if not api_key:
            raise ApiRequestError("Не задан EXCHANGERATE_API_KEY")

        url = (
            f"{self.config.EXCHANGERATE_API_URL}/"
            f"{api_key}/latest/{self.config.BASE_FIAT_CURRENCY}"
        )

        try:
            response = requests.get(
                url,
                timeout=self.config.REQUEST_TIMEOUT,
            )

            if response.status_code != 200:
                raise ApiRequestError(
                    f"ExchangeRate-API вернул HTTP {response.status_code}"
                )

            data = response.json()

        except requests.exceptions.RequestException as error:
            raise ApiRequestError(
                f"Ошибка соединения с ExchangeRate-API: {error}"
            ) from error
        except ValueError as error:
            raise ApiRequestError(
                "ExchangeRate-API вернул некорректный JSON"
            ) from error

        if data.get("result") != "success":
            reason = data.get("error-type", "неизвестная ошибка")
            raise ApiRequestError(f"ExchangeRate-API: {reason}")

        source_currency = self.config.BASE_FIAT_CURRENCY
        source_rates = data.get("conversion_rates", data.get("rates", {}))

        rates = {}

        for code in self.config.FIAT_CURRENCIES:
            if code not in source_rates:
                raise ApiRequestError(
                    f"Курс {code} отсутствует в ответе ExchangeRate-API"
                )

            rate = source_rates[code]

            if (
                not isinstance(rate, (int, float))
                or isinstance(rate, bool)
                or rate <= 0
            ):
                raise ApiRequestError(f"Некорректный курс {code} от ExchangeRate-API")

            rates[f"{code}_{source_currency}"] = 1 / rate

        return rates
