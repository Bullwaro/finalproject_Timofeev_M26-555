import shlex

from prettytable import PrettyTable

from valutatrade_hub.core.currencies import CURRENCIES
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
)
from valutatrade_hub.core.usecases import (
    buy_currency,
    get_rate,
    login_user,
    register_user,
    sell_currency,
    show_portfolio,
)
from valutatrade_hub.parser_service.api_clients import (
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.parser_service.updater import RatesUpdater


def parse_options(args):
    options = {}
    index = 0

    while index < len(args):
        key = args[index]

        if not key.startswith("--") or index + 1 >= len(args):
            raise ValueError("Некорректные аргументы команды")

        options[key[2:].replace("-", "_")] = args[index + 1]
        index += 2

    return options


def show_cached_rates(options):
    config = ParserConfig()
    storage = RatesStorage(config)

    cache = storage.load_rates()

    if not cache or not cache.get("rates"):
        print(
            "Локальный кеш курсов пуст. "
            "Выполните 'update-rates', чтобы загрузить данные."
        )
        return

    rates = cache["rates"]

    base = options.get("base", config.BASE_FIAT_CURRENCY).upper()

    if base not in rates:
        print(f"Базовая валюта '{base}' не найдена в кеше.")
        return

    if "currency" in options and "top" in options:
        raise ValueError("Нельзя одновременно использовать --currency и --top")

    if "currency" in options:
        currency = options["currency"].upper()

        if currency not in rates:
            print(f"Курс для '{currency}' не найден в кеше.")
            return

        currencies = [currency]

    elif "top" in options:
        top_count = int(options["top"])

        if top_count <= 0:
            raise ValueError("--top должен быть положительным числом")

        currencies = [code for code in config.CRYPTO_CURRENCIES if code in rates]

        currencies.sort(
            key=lambda code: float(rates[code]) / float(rates[base]),
            reverse=True,
        )

        currencies = currencies[:top_count]

    else:
        currencies = sorted(code for code in rates if code != base)

    if not currencies:
        print("В кеше нет курсов, подходящих под заданные фильтры.")
        return

    updated_at = cache.get("updated_at", cache.get("last_refresh", "неизвестно"))

    print(f"Курсы из кеша (обновлено: {updated_at}, база: {base})")

    table = PrettyTable(
        [
            "Пара",
            "Курс",
            "Источник",
            "Обновлено",
        ]
    )

    pairs = cache.get("pairs", {})
    sources = cache.get("sources", {})

    for code in currencies:
        rate = float(rates[code]) / float(rates[base])

        source_pair = f"{code}_{config.BASE_FIAT_CURRENCY}"
        pair_info = pairs.get(source_pair, {})

        source = sources.get(source_pair, pair_info.get("source", "—"))

        pair_updated_at = pair_info.get("updated_at", updated_at)

        table.add_row(
            [
                f"{code}_{base}",
                f"{rate:.8f}",
                source,
                pair_updated_at,
            ]
        )

    print(table)


def show_help():
    print("""
Доступные команды:

  register --username NAME --password PASSWORD
  login --username NAME --password PASSWORD
  logout
  show-portfolio [--base-currency USD]
  update-rates [--source coingecko|exchangerate]
  show-rates [--currency BTC] [--top N] [--base EUR]
  buy --currency BTC --amount 0.1
  sell --currency BTC --amount 0.1
  get-rate --from USD --to BTC
  list-currencies
  help
  exit

""")


def run_cli():
    current_user = None

    print("Добро пожаловать в ValutaTrade Hub!")
    print("Введите help для просмотра команд.")

    while True:
        try:
            command_line = input("valutatrade> ").strip()

            if not command_line:
                continue

            parts = shlex.split(command_line)
            command = parts[0].lower()
            options = parse_options(parts[1:])
            match command:
                case "exit":
                    print("До свидания!")
                    break

                case "help":
                    show_help()

                case "register":
                    print(register_user(options["username"], options["password"]))

                case "login":
                    current_user = login_user(options["username"], options["password"])
                    print(f"Вы вошли как {current_user.username}")

                case "logout":
                    current_user = None
                    print("Вы вышли из аккаунта")

                case "show-portfolio":
                    print(show_portfolio(current_user, options.get("base_currency")))

                case "buy":
                    result = buy_currency(
                        current_user,
                        options["currency"],
                        float(options["amount"]),
                    )
                    print(f"Покупка выполнена успешно: {result}")

                case "sell":
                    result = sell_currency(
                        current_user,
                        options["currency"],
                        float(options["amount"]),
                    )
                    print(f"Продажа выполнена успешно: {result}")

                case "get-rate":
                    print(get_rate(options["from"].upper(), options["to"].upper()))

                case "list-currencies":
                    table = PrettyTable(["Код", "Информация"])

                    for currency in CURRENCIES.values():
                        table.add_row([currency.code, currency.get_display_info()])

                    print(table)
                case "update-rates":
                    source = options.get("source")

                    if source is not None:
                        source = source.lower()

                    if source not in (None, "coingecko", "exchangerate"):
                        raise ValueError(
                            "Источник должен быть coingecko или exchangerate"
                        )

                    config = ParserConfig()
                    clients = {}

                    if source in (None, "coingecko"):
                        clients["CoinGecko"] = CoinGeckoClient(config)

                    if source in (None, "exchangerate"):
                        clients["ExchangeRate-API"] = ExchangeRateApiClient(config)

                    updater = RatesUpdater(
                        clients,
                        RatesStorage(config),
                    )

                    try:
                        result = updater.run_update()

                    except ApiRequestError as error:
                        print(f"Не удалось обновить курсы: {error}")

                    else:
                        count = len(result["rates"]) - 1

                        if result.get("errors"):
                            print(
                                "Обновление завершено с ошибками. "
                                f"Получено курсов: {count}. "
                                "Подробности: logs/actions.log"
                            )
                        else:
                            print(
                                "Обновление успешно. "
                                f"Обновлено курсов: {count}. "
                                f"Последнее обновление: {result['updated_at']}"
                            )
                case "show-rates":
                    show_cached_rates(options)
                case _:
                    print(f"Неизвестная команда: {command}")

        except CurrencyNotFoundError as error:
            print(f"Ошибка: {error}")

        except ApiRequestError as error:
            print(f"Ошибка API: {error}")

        except InsufficientFundsError as error:
            print(f"Ошибка: {error}")

        except (ValueError, KeyError, IndexError) as error:
            print(f"Ошибка: {error}")

        except Exception as error:  # noqa: BLE001
            print(f"Ошибка выполнения: {error}")
