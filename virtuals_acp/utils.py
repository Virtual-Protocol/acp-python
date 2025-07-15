import json
from typing import Type, Optional

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


def get_tx_hash_from_alchemy_response(response: dict) -> str:
    return response.get('receipts', [])[0].get('transactionHash')
