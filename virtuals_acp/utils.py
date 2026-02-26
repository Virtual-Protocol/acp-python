import functools
import json
import warnings
from typing import Optional, Type, Union, Dict, Any
import base64

from pydantic import ValidationError

from virtuals_acp.models import T


def get_txn_hash_from_response(response: Dict[str, Any]) -> Optional[str]:
    try:
        return response.get("receipts", [])[0].get("transactionHash")
    except (IndexError, AttributeError):
        print(f"Error getting transaction hash from response: {response}")
        return None


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


def safe_base64_encode(data: Union[str, bytes]) -> str:
    if isinstance(data, str):
        data_bytes = data.encode("utf-8")
    else:
        data_bytes = data
    return base64.b64encode(data_bytes).decode("utf-8")

def get_destination_endpoint_id(chain_id: int) -> int:
    id_to_eid = {
        84532: 40245,    # baseSepolia.id
        11155111: 40161, # sepolia.id
        80002: 40267,    # polygonAmoy.id
        421614: 40231,   # arbitrumSepolia.id
        97: 40102,       # bscTestnet.id
        8453: 30184,     # base.id
        1: 30101,        # mainnet.id
        137: 30109,      # polygon.id
        42161: 30110,    # arbitrum.id
        56: 30102,       # bsc.id
    }
    if chain_id in id_to_eid:
        return id_to_eid[chain_id]
    raise ValueError(f"Unsupported chain ID: {chain_id}")
    
def get_destination_chain_id(endpoint_id: int) -> int:
    eid_to_id = {
        40245: 84532,     # baseSepolia.id
        40161: 11155111,  # sepolia.id
        40267: 80002,     # polygonAmoy.id
        40231: 421614,    # arbitrumSepolia.id
        40102: 97,        # bscTestnet.id
        30184: 8453,      # base.id
        30101: 1,         # mainnet.id
        30109: 137,       # polygon.id
        30110: 42161,     # arbitrum.id
        30102: 56,        # bsc.id
    }
    if endpoint_id in eid_to_id:
        return eid_to_id[endpoint_id]
    raise ValueError(f"Unsupported endpoint ID: {endpoint_id}")