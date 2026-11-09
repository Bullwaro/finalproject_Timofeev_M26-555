from datetime import datetime

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.logging_config import get_action_logger
from valutatrade_hub.parser_service.api_clients import BaseApiClient

logger = get_action_logger()


class RatesUpdater:
    def __init__(
        self,
        clients: dict[str, BaseApiClient],
        storage,
    ):
        self.clients = clients
        self.storage = storage

    def run_update(self) -> dict:
        logger.info("Начало обновления курсов")

        rates = {"USD": 1.0}
        sources = {}
        successful_sources = []
        failed_sources = []

        for source, client in self.clients.items():
            try:
                logger.info("Запрос курсов: %s", source)

                client_rates = client.fetch_rates()

                for pair, rate in client_rates.items():
                    currencies = pair.split("_")

                    if len(currencies) != 2 or currencies[1] != "USD":
                        raise ApiRequestError(f"Некорректная валютная пара: {pair}")

                    from_currency = currencies[0]

                    if (
                        not isinstance(rate, (int, float))
                        or isinstance(rate, bool)
                        or rate <= 0
                    ):
                        raise ApiRequestError(f"Некорректный курс для {pair}")

                    rates[from_currency] = float(rate)
                    sources[pair] = source

                successful_sources.append(source)

                logger.info(
                    "Источник %s успешно предоставил %s курсов",
                    source,
                    len(client_rates),
                )

            except Exception:
                failed_sources.append(source)
                logger.exception(
                    "Ошибка обновления курсов от %s",
                    source,
                )

        if not successful_sources:
            logger.error("Не удалось получить курсы ни от одного источника")
            raise ApiRequestError(
                "Не удалось обновить курсы: все API-источники недоступны"
            )

        last_refresh = datetime.now().isoformat(timespec="seconds")

        update_data = {
            "updated_at": last_refresh,
            "last_refresh": last_refresh,
            "source": ", ".join(successful_sources),
            "sources": sources,
            "rates": rates,
            "errors": failed_sources,
        }

        try:
            self.storage.save_rates(update_data)

        except Exception:
            logger.exception("Ошибка сохранения курсов")
            raise

        logger.info(
            "Обновление курсов завершено. Получено валют: %s",
            len(rates) - 1,
        )

        return update_data
