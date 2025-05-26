from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator

class EnvSettings(BaseSettings):
    BUYER_WALLET_PRIVATE_KEY: Optional[str] = None
    SELLER_WALLET_PRIVATE_KEY: Optional[str] = None
    EVALUATOR_WALLET_PRIVATE_KEY: Optional[str] = None
    BUYER_AGENT_WALLET_ADDRESS: Optional[str] = None
    SELLER_AGENT_WALLET_ADDRESS: Optional[str] = None
    EVALUATOR_AGENT_WALLET_ADDRESS: Optional[str] = None
    BUYER_GAME_TWITTER_ACCESS_TOKEN: Optional[str] = None
    SELLER_GAME_TWITTER_ACCESS_TOKEN: Optional[str] = None
    EVALUATOR_GAME_TWITTER_ACCESS_TOKEN: Optional[str] = None
    @field_validator("BUYER_WALLET_PRIVATE_KEY", "SELLER_WALLET_PRIVATE_KEY", "EVALUATOR_WALLET_PRIVATE_KEY")
    @classmethod
    def strip_0x_prefix(cls, v: str) -> str:
        if v and v.startswith("0x"):
            raise ValueError("WALLET_PRIVATE_KEY must not start with '0x'. Please remove it.")
        return v

    @field_validator("BUYER_AGENT_WALLET_ADDRESS", "SELLER_AGENT_WALLET_ADDRESS", "EVALUATOR_AGENT_WALLET_ADDRESS")
    @classmethod
    def validate_wallet_address(cls, v: str) -> str:
        if v is None:
            return None
        if not v.startswith("0x") or len(v) != 42:
            raise ValueError("Wallet address must start with '0x' and be 42 characters long.")
        return v
    