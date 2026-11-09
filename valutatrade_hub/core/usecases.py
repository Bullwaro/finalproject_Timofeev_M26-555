import hashlib
import time
from datetime import datetime

from valutatrade_hub.core.models import User
from valutatrade_hub.core.utils import load_json, save_json


USERS_FILE = "data/users.json"
PORTFOLIOS_FILE = "data/portfolios.json"
RATES_FILE = "data/rates.json"

def register_user(username: str, password: str):
    users = load_json(USERS_FILE)
    portfolios = load_json(PORTFOLIOS_FILE)

    if not username.strip():
        raise ValueError("Имя пользователя не может быть пустым")

    if len(password) < 4:
        raise ValueError("Пароль должен быть не короче 4 символов")

    for user in users:
        if user["username"] == username:
            raise ValueError(f"Имя пользователя '{username}' уже занято")

    user_id = max(
        (user["user_id"] for user in users),
        default=0
    ) + 1

    salt = hashlib.sha256(str(time.time_ns()).encode()).hexdigest()[:16]

    user = User(
        user_id,
        username,
        "",
        salt,
        datetime.now()
    )

    user.change_password(password)

    users.append({
        "user_id": user.user_id,
        "username": user.username,
        "hashed_password": user.hashed_password,
        "salt": user.salt,
        "registration_date": user.registration_date.isoformat()
    })

    portfolios.append({
        "user_id": user_id,
        "wallets": {}
    })

    save_json(USERS_FILE, users)
    save_json(PORTFOLIOS_FILE, portfolios)

    return (
        f"Пользователь '{username}' зарегистрирован "
        f"(id={user_id}). Войдите: login --username {username} "
        "--password ****"
    )

def login_user(username: str, password: str):
    users = load_json(USERS_FILE)

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
        datetime.fromisoformat(user_data["registration_date"])
    )

    if not user.verify_password(password):
        raise ValueError("Неверный пароль")

    return user

def show_portfolio(user: User, base_currency="USD"):
    if user is None:
        raise ValueError("Сначала выполните login")

    portfolios = load_json(PORTFOLIOS_FILE)
    rates_data = load_json(RATES_FILE)

    rates = rates_data["rates"]

    if base_currency not in rates:
        raise ValueError(
            f"Неизвестная базовая валюта '{base_currency}'"
        )

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
    result = [
        f"Портфель пользователя '{user.username}' "
        f"(база: {base_currency}):"
    ]

    for currency_code, wallet_data in wallets.items():
        if currency_code not in rates:
            raise ValueError(f"Неизвестная валюта '{currency_code}'")

        balance = wallet_data["balance"]
        value = balance * rates[currency_code] / rates[base_currency]

        total += value

        result.append(
            f"- {currency_code}: {balance:.4f} "
            f"→ {value:.2f} {base_currency}"
        )

    result.append("---------------------------------")
    result.append(f"ИТОГО: {total:,.2f} {base_currency}")

    return "\n".join(result)

def buy_currency(user: User, currency: str, amount: float):
    if user is None:
        raise ValueError("Сначала выполните login")

    if not isinstance(amount, (int, float)) or isinstance(amount, bool) or amount <= 0:
        raise ValueError("'amount' должен быть положительным числом")

    if not isinstance(currency, str) or not currency.isalpha():
        raise ValueError("Некорректный код валюты")

    currency = currency.upper()

    portfolios = load_json(PORTFOLIOS_FILE)
    rates_data = load_json(RATES_FILE)

    rates = rates_data["rates"]

    if currency not in rates:
        raise ValueError(
            f"Не удалось получить курс для {currency}→USD"
        )

    portfolio = None

    for item in portfolios:
        if item["user_id"] == user.user_id:
            portfolio = item
            break

    if portfolio is None:
        raise ValueError("Портфель пользователя не найден")

    wallets = portfolio["wallets"]

    if currency not in wallets:
        wallets[currency] = {"balance": 0.0}

    old_balance = wallets[currency]["balance"]
    new_balance = old_balance + amount

    wallets[currency]["balance"] = new_balance

    cost = amount * rates[currency]

    save_json(PORTFOLIOS_FILE, portfolios)

    return (
        f"Покупка выполнена: {amount:.4f} {currency} "
        f"по курсу {rates[currency]:.2f} USD/{currency}\n"
        f"Изменения в портфеле:\n"
        f"- {currency}: было {old_balance:.4f} "
        f"→ стало {new_balance:.4f}\n"
        f"Оценочная стоимость покупки: {cost:,.2f} USD"
    )

def sell_currency(user: User, currency: str, amount: float):
    if user is None:
        raise ValueError("Сначала выполните login")

    if (
        not isinstance(amount, (int, float))
        or isinstance(amount, bool)
        or amount <= 0
    ):
        raise ValueError("'amount' должен быть положительным числом")

    if not isinstance(currency, str) or not currency.isalpha():
        raise ValueError("Некорректный код валюты")

    currency = currency.upper()

    portfolios = load_json(PORTFOLIOS_FILE)
    rates_data = load_json(RATES_FILE)

    rates = rates_data["rates"]

    if currency not in rates:
        raise ValueError(
            f"Не удалось получить курс для {currency}→USD"
        )

    portfolio = None

    for item in portfolios:
        if item["user_id"] == user.user_id:
            portfolio = item
            break

    if portfolio is None:
        raise ValueError("Портфель пользователя не найден")

    wallets = portfolio["wallets"]

    if currency not in wallets:
        raise ValueError(
            f"У вас нет кошелька '{currency}'. "
            "Добавьте валюту: она создаётся автоматически "
            "при первой покупке."
        )

    old_balance = wallets[currency]["balance"]

    if amount > old_balance:
        raise ValueError(
            f"Недостаточно средств: доступно {old_balance:.4f} "
            f"{currency}, требуется {amount:.4f} {currency}"
        )

    new_balance = old_balance - amount
    wallets[currency]["balance"] = new_balance

    revenue = amount * rates[currency]

    if currency != "USD":
        if "USD" not in wallets:
            wallets["USD"] = {"balance": 0.0}

        wallets["USD"]["balance"] += revenue

    save_json(PORTFOLIOS_FILE, portfolios)

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
        or from_currency != from_currency.upper()
        or to_currency != to_currency.upper()
        or not from_currency.isalpha()
        or not to_currency.isalpha()
    ):
        raise ValueError("Некорректный код валюты")

    rates_data = load_json(RATES_FILE)

    updated_at = datetime.fromisoformat(rates_data["updated_at"])
    current_time = datetime.now()

    if (current_time - updated_at).total_seconds() >= 300:
        rates_data["rates"] = {
            "USD": 1.0,
            "EUR": 1.08,
            "BTC": 65000.0
        }

        rates_data["updated_at"] = current_time.isoformat()

        save_json(RATES_FILE, rates_data)

    rates = rates_data["rates"]

    if from_currency not in rates or to_currency not in rates:
        raise ValueError(
            f"Курс {from_currency}→{to_currency} недоступен. "
            "Повторите попытку позже."
        )

    rate = rates[from_currency] / rates[to_currency]
    reverse_rate = 1 / rate

    updated_at = datetime.fromisoformat(rates_data["updated_at"])

    return (
        f"Курс {from_currency}→{to_currency}: "
        f"{rate:.8f} "
        f"(обновлено: {updated_at.strftime('%Y-%m-%d %H:%M:%S')})\n"
        f"Обратный курс {to_currency}→{from_currency}: "
        f"{reverse_rate:.2f}"
    )
