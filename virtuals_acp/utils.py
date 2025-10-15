import functools
import json
import warnings
from typing import Optional, Type, Union, Dict, Any

from pydantic import ValidationError

from virtuals_acp.models import T


def try_parse_json_model(content: str, model: Type[T]) -> Optional[T]:
    try:
        return model.model_validate_json(content)
    except (json.JSONDecodeError, ValidationError):
        return None


def try_validate_model(data: dict, model: Type[T]) -> Optional[T]:
    try:
        return model.model_validate(data)
    except ValidationError:
        return None


def prepare_payload(payload: Union[str, Dict[str, Any]]) -> str:
    return payload if isinstance(payload, str) else json.dumps(payload)

def deprecated(reason: str = "This function is deprecated and should not be used."):
    """Decorator to mark functions or methods as deprecated."""

    def decorator(func):
        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            warnings.warn(
                f"Call to deprecated function {func.__name__}: {reason}",
                category=DeprecationWarning,
                stacklevel=2,
            )
            return func(*args, **kwargs)

        return wrapped

    return decorator
