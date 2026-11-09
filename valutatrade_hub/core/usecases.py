import hashlib
import time
from datetime import datetime

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.core.models import User, Wallet
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader

settings = SettingsLoader()
db = DatabaseManager()

# USERS_FILE = "data/users.json"
# PORTFOLIOS_FILE = "data/portfolios.json"
# RATES_FILE = "data/rates.json"

users_file = settings.get("users_file")
portfolios_file = settings.get("portfolios_file")
rates_file = settings.get("rates_file")


@log_action("REGISTER")
def register_user(username: str, password: str):
    users = db.load(users_file)
    portfolios = db.load(portfolios_file)

    if not username.strip():
        raise ValueError("Имя пользователя не может быть пустым")

    if len(password) < 4:
        raise ValueError("Пароль должен быть не короче 4 символов")

    for user in users:
        if user["username"] == username:
            raise ValueError(f"Имя пользователя '{username}' уже занято")

    user_id = max((user["user_id"] for user in users), default=0) + 1

    salt = hashlib.sha256(str(time.time_ns()).encode()).hexdigest()[:16]

    user = User(user_id, username, "", salt, datetime.now())

    user.change_password(password)

    users.append(
        {
            "user_id": user.user_id,
            "username": user.username,
            "hashed_password": user.hashed_password,
            "salt": user.salt,
            "registration_date": user.registration_date.isoformat(),
        }
    )

    portfolios.append({"user_id": user_id, "wallets": {}})

    db.save(users_file, users)
    db.save(portfolios_file, portfolios)

    return (
        f"Пользователь '{username}' зарегистрирован "
        f"(id={user_id}). Войдите: login --username {username} "
        "--password ****"
    )


@log_action("LOGIN")
def login_user(username: str, password: str):
    users = db.load(users_file)

    user_data = None

    for user in users:
        if user["username"] == username:
            user_data = user
            break

    if user_data is None:
        raise ValueError(f"Пользователь '{username}' не найден")

    user = User(
        user_data["user_id"],
        user_data["username"],
        user_data["hashed_password"],
        user_data["salt"],
        datetime.fromisoformat(user_data["registration_date"]),
    )

    if not user.verify_password(password):
        raise ValueError("Неверный пароль")

    return user


def show_portfolio(user: User, base_currency=None):
    if user is None:
        raise ValueError("Сначала выполните login")

    if base_currency is None:
        base_currency = settings.get("default_base_currency", "USD")

    portfolios = db.load(portfolios_file)
    rates_data = db.load(rates_file)

    rates = rates_data["rates"]

    get_currency(base_currency)

    if base_currency not in rates:
        raise ApiRequestError(f"Курс базовой валюты {base_currency} отсутствует")

    portfolio_data = None

    for portfolio in portfolios:
        if portfolio["user_id"] == user.user_id:
            portfolio_data = portfolio
            break

    if portfolio_data is None:
        raise ValueError("Портфель пользователя не найден")

    wallets = portfolio_data["wallets"]

    if not wallets:
        return f"Портфель пользователя '{user.username}' пуст"

    total = 0.0
    result = [(f"Портфель пользователя '{user.username}' (база: {base_currency}):")]

    for currency_code, wallet_data in wallets.items():
        get_currency(currency_code)

        if currency_code not in rates:
            raise ApiRequestError(f"Курс валюты {currency_code} отсутствует")

        balance = wallet_data["balance"]
        value = balance * rates[currency_code] / rates[base_currency]

        total += value

        result.append(f"- {currency_code}: {balance:.4f} → {value:.2f} {base_currency}")

    result.append("---------------------------------")
    result.append(f"ИТОГО: {total:,.2f} {base_currency}")

    return "\n".join(result)


@log_action("BUY", verbose=True)
def buy_currency(user: User, currency: str, amount: float):
    if user is None:
        raise ValueError("Сначала выполните login")

    if not isinstance(amount, (int, float)) or isinstance(amount, bool) or amount <= 0:
        raise ValueError("'amount' должен быть положительным числом")

    if not isinstance(currency, str) or not currency.isalpha():
        raise ValueError("Некорректный код валюты")

    currency = currency.upper()
    get_currency(currency)

    if currency == "USD":
        raise ValueError("Нельзя купить USD за USD")

    portfolios = db.load(portfolios_file)
    rates_data = db.load(rates_file)
    rates = rates_data["rates"]

    if currency not in rates:
        raise ApiRequestError(f"Курс валюты {currency} недоступен")

    portfolio = None

    for item in portfolios:
        if item["user_id"] == user.user_id:
            portfolio = item
            break

    if portfolio is None:
        raise ValueError("Портфель пользователя не найден")

    wallets = portfolio["wallets"]

    usd_data = wallets.get("USD", {"balance": 0.0})
    usd_wallet = Wallet("USD", usd_data["balance"])

    currency_data = wallets.get(currency, {"balance": 0.0})
    currency_wallet = Wallet(currency, currency_data["balance"])

    cost = amount * rates[currency]
    old_balance = currency_wallet.balance

    # Списываем стоимость покупки в USD.
    usd_wallet.withdraw(cost)

    # Зачисляем приобретённую валюту.
    currency_wallet.deposit(amount)

    wallets["USD"] = {"balance": usd_wallet.balance}
    wallets[currency] = {"balance": currency_wallet.balance}

    db.save(portfolios_file, portfolios)

    return (
        f"Покупка выполнена: {amount:.4f} {currency} "
        f"по курсу {rates[currency]:.2f} USD/{currency}\n"
        f"Изменения в портфеле:\n"
        f"- {currency}: было {old_balance:.4f} "
        f"→ стало {currency_wallet.balance:.4f}\n"
        f"- USD: осталось {usd_wallet.balance:.2f}\n"
        f"Стоимость покупки: {cost:,.2f} USD"
    )


@log_action("SELL", verbose=True)
def sell_currency(user: User, currency: str, amount: float):
    if user is None:
        raise ValueError("Сначала выполните login")

    if not isinstance(amount, (int, float)) or isinstance(amount, bool) or amount <= 0:
        raise ValueError("'amount' должен быть положительным числом")

    if not isinstance(currency, str) or not currency.isalpha():
        raise ValueError("Некорректный код валюты")

    currency = currency.upper()
    get_currency(currency)

    portfolios = db.load(portfolios_file)
    rates_data = db.load(rates_file)
    rates = rates_data["rates"]

    if currency not in rates:
        raise ValueError(f"Курс валюты {currency} недоступен")

    portfolio = None

    for item in portfolios:
        if item["user_id"] == user.user_id:
            portfolio = item
            break

    if portfolio is None:
        raise ValueError("Портфель пользователя не найден")

    wallets = portfolio["wallets"]

    if currency not in wallets:
        raise ValueError(f"У вас нет кошелька '{currency}'")

    old_balance = wallets[currency]["balance"]
    wallet = Wallet(currency, old_balance)

    wallet.withdraw(amount)
    new_balance = wallet.balance

    wallets[currency] = {"balance": new_balance}

    revenue = amount * rates[currency]

    if currency != "USD":
        usd_data = wallets.get("USD", {"balance": 0.0})
        usd_wallet = Wallet("USD", usd_data["balance"])

        usd_wallet.deposit(revenue)

        wallets["USD"] = {"balance": usd_wallet.balance}

    db.save(portfolios_file, portfolios)

    return (
        f"Продажа выполнена: {amount:.4f} {currency} "
        f"по курсу {rates[currency]:.2f} USD/{currency}\n"
        f"Изменения в портфеле:\n"
        f"- {currency}: было {old_balance:.4f} "
        f"→ стало {new_balance:.4f}\n"
        f"Оценочная выручка: {revenue:,.2f} USD"
    )


def get_rate(from_currency: str, to_currency: str):
    if (
        not isinstance(from_currency, str)
        or not isinstance(to_currency, str)
        or not from_currency
        or not to_currency
        or not from_currency.isalpha()
        or not to_currency.isalpha()
    ):
        raise ValueError("Некорректный код валюты")

    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    get_currency(from_currency)
    get_currency(to_currency)

    rates_data = db.load(rates_file)

    updated_at = datetime.fromisoformat(rates_data["updated_at"])
    current_time = datetime.now()

    ttl = settings.get("rates_ttl_seconds", 300)

    if (current_time - updated_at).total_seconds() >= ttl:
        raise ApiRequestError("Кеш курсов устарел, обновление пока недоступно")

    rates = rates_data["rates"]

    if from_currency not in rates or to_currency not in rates:
        raise ApiRequestError(f"Курс {from_currency}→{to_currency} отсутствует в кеше")

    rate = rates[from_currency] / rates[to_currency]
    reverse_rate = 1 / rate

    return (
        f"Курс {from_currency}→{to_currency}: "
        f"{rate:.8f}\n"
        f"Обратный курс {to_currency}→{from_currency}: "
        f"{reverse_rate:.8f}\n"
        f"Обновлено: {updated_at.isoformat()}"
    )
