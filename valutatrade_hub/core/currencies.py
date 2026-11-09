from abc import ABC, abstractmethod

from valutatrade_hub.core.exceptions import CurrencyNotFoundError


class Currency(ABC):
    def __init__(self, name: str, code: str):
        if not name.strip():
            raise ValueError("Currency name cannot be empty")

        if (
            not code.isalpha()
            or not code.isupper()
            or not 2 <= len(code) <= 5
        ):
            raise ValueError("Invalid currency code")

        self.name = name
        self.code = code

    @abstractmethod
    def get_display_info(self) -> str:
        pass


class FiatCurrency(Currency):
    def __init__(self, name: str, code: str, issuing_country: str):
        super().__init__(name, code)

        if not issuing_country.strip():
            raise ValueError("Issuing country cannot be empty")

        self.issuing_country = issuing_country

    def get_display_info(self) -> str:
        return (
            f"[FIAT] {self.code} — {self.name} "
            f"(Issuing: {self.issuing_country})"
        )


class CryptoCurrency(Currency):
    def __init__(
        self,
        name: str,
        code: str,
        algorithm: str,
        market_cap: float
    ):
        super().__init__(name, code)

        if not algorithm.strip():
            raise ValueError("Algorithm cannot be empty")

        if not isinstance(market_cap, (int, float)) or market_cap < 0:
            raise ValueError("Market cap must be a positive number")

        self.algorithm = algorithm
        self.market_cap = float(market_cap)

    def get_display_info(self) -> str:
        return (
            f"[CRYPTO] {self.code} — {self.name} "
            f"(Algo: {self.algorithm}, MCAP: {self.market_cap:.2e})"
        )


CURRENCIES = {
    "USD": FiatCurrency("US Dollar", "USD", "United States"),
    "EUR": FiatCurrency("Euro", "EUR", "Eurozone"),
    "BTC": CryptoCurrency("Bitcoin", "BTC", "SHA-256", 1.12e12),
    "ETH": CryptoCurrency("Ethereum", "ETH", "Ethash", 3.5e11)
}


def get_currency(code: str) -> Currency:
    if code not in CURRENCIES:
        raise CurrencyNotFoundError(code)

    return CURRENCIES[code]