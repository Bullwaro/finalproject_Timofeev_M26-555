from datetime import datetime
from functools import wraps
from inspect import signature

from valutatrade_hub.logging_config import get_action_logger

logger = get_action_logger()


def log_action(action: str, verbose: bool = False):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            bound = signature(func).bind_partial(*args, **kwargs)
            values = bound.arguments

            user = values.get("user")
            username = getattr(user, "username", None)
            user_id = getattr(user, "user_id", None)

            if username is None:
                username = values.get("username")

            currency = values.get(
                "currency_code",
                values.get("currency"),
            )
            amount = values.get("amount")
            rate = values.get("rate")
            base = values.get("base_currency")

            fields = [
                datetime.now().astimezone().isoformat(timespec="seconds"),
                action,
            ]

            if username is not None:
                fields.append(f"username={username!r}")
            elif user_id is not None:
                fields.append(f"user_id={user_id}")

            if currency is not None:
                fields.append(f"currency={currency!r}")

            if amount is not None:
                fields.append(f"amount={amount}")

            if rate is not None:
                fields.append(f"rate={rate}")

            if base is not None:
                fields.append(f"base={base!r}")

            if verbose:
                safe_args = {
                    key: value
                    for key, value in values.items()
                    if key not in ("user", "password", "hashed_password", "salt")
                }
                fields.append(f"context={safe_args!r}")

            try:
                result = func(*args, **kwargs)
                fields.append("result=OK")
                logger.info(" ".join(fields))
                return result

            except Exception as error:
                fields.append("result=ERROR")
                fields.append(f"error_type={type(error).__name__}")
                fields.append(f"error_message={str(error)!r}")
                logger.info(" ".join(fields))
                raise

        return wrapper

    return decorator
