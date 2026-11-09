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


def show_help():
    print("""
Доступные команды:

  register --username NAME --password PASSWORD
  login --username NAME --password PASSWORD
  logout
  show-portfolio [--base-currency USD]
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

            if command == "exit":
                print("До свидания!")
                break

            elif command == "help":
                show_help()

            elif command == "register":
                print(register_user(options["username"], options["password"]))

            elif command == "login":
                current_user = login_user(options["username"], options["password"])
                print(f"Вы вошли как {current_user.username}")

            elif command == "logout":
                current_user = None
                print("Вы вышли из аккаунта")

            elif command == "show-portfolio":
                print(show_portfolio(current_user, options.get("base_currency")))

            elif command == "buy":
                result = buy_currency(
                    current_user,
                    options["currency"],
                    float(options["amount"]),
                )
                print(f"Покупка выполнена успешно: {result}")

            elif command == "sell":
                result = sell_currency(
                    current_user,
                    options["currency"],
                    float(options["amount"]),
                )
                print(f"Продажа выполнена успешно: {result}")

            elif command == "get-rate":
                print(get_rate(options["from"].upper(), options["to"].upper()))

            elif command == "list-currencies":
                table = PrettyTable(["Код", "Информация"])

                for currency in CURRENCIES.values():
                    table.add_row([currency.code, currency.get_display_info()])

                print(table)

            else:
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
