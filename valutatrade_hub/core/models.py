import hashlib
from datetime import datetime
from valutatrade_hub.core.exceptions import InsufficientFundsError


class User:
    def __init__(
        self,
        user_id: int,
        username: str,
        hashed_password: str,
        salt: str,
        registration_date: datetime
    ):
        self._user_id = user_id
        self._username = username
        self._hashed_password = hashed_password
        self._salt = salt
        self._registration_date = registration_date

    @property
    def user_id(self):
        return self._user_id

    @property
    def username(self):
        return self._username

    @username.setter
    def username(self, value: str):
        if not value.strip():
            raise ValueError("Username cannot be empty")
        self._username = value

    @property
    def hashed_password(self):
        return self._hashed_password

    @property
    def salt(self):
        return self._salt

    @property
    def registration_date(self):
        return self._registration_date

    def get_user_info(self):
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date.isoformat()
        }

    def change_password(self, new_password: str):
        if len(new_password) < 4:
            raise ValueError("Password must contain at least 4 characters")

        self._hashed_password = hashlib.sha256(
            (new_password + self._salt).encode()
        ).hexdigest()

    def verify_password(self, password: str):
        hashed_password = hashlib.sha256(
            (password + self._salt).encode()
        ).hexdigest()

        return hashed_password == self._hashed_password


class Wallet:
    def __init__(self, currency_code: str, balance: float = 0.0):
        self.currency_code = currency_code
        self._balance = balance

    @property
    def balance(self):
        return self._balance

    @balance.setter
    def balance(self, value: float):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError("Balance must be a number")

        if value < 0:
            raise ValueError("Balance cannot be negative")

        self._balance = float(value)

    def deposit(self, amount: float):
        if not isinstance(amount, (int, float)) or isinstance(amount, bool):
            raise TypeError("Amount must be a number")

        if amount <= 0:
            raise ValueError("Amount must be positive")

        self.balance += amount

    def withdraw(self, amount: float):
        if not isinstance(amount, (int, float)) or isinstance(amount, bool):
            raise TypeError("Amount must be a number")

        if amount <= 0:
            raise ValueError("Amount must be positive")

        if amount > self.balance:
            raise InsufficientFundsError(
                self.balance,
                amount,
                self.currency_code
            )

        self.balance -= amount

    def get_balance_info(self):
        return {
            "currency_code": self.currency_code,
            "balance": self.balance
        }


class Portfolio:
    exchange_rates = {
        "USD": 1.0,
        "EUR": 1.08,
        "BTC": 65000.0
    }

    def __init__(self, user: User, wallets: dict = None):
        self._user = user
        self._wallets = wallets.copy() if wallets else {}

    @property
    def user(self):
        return self._user

    @property
    def wallets(self):
        return self._wallets.copy()

    def add_currency(self, currency_code: str):
        if currency_code in self._wallets:
            raise ValueError("Wallet already exists")

        self._wallets[currency_code] = Wallet(currency_code)

    def get_wallet(self, currency_code: str):
        if currency_code not in self._wallets:
            raise ValueError("Wallet not found")

        return self._wallets[currency_code]

    def get_total_value(self, base_currency="USD"):
        if base_currency not in self.exchange_rates:
            raise ValueError("Unknown base currency")

        total_usd = 0.0

        for wallet in self._wallets.values():
            currency = wallet.currency_code

            if currency not in self.exchange_rates:
                raise ValueError(f"Unknown currency: {currency}")

            total_usd += wallet.balance * self.exchange_rates[currency]

        return total_usd / self.exchange_rates[base_currency]
