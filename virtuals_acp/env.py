from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator, ConfigDict

class EnvSettings(BaseSettings):
    """Environment settings for ACP client configuration.
    
    Automatically loads values from .env files and environment variables.
    """
    
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    # Wallet config
    WHITELISTED_WALLET_PRIVATE_KEY: Optional[str] = None
    BUYER_AGENT_WALLET_ADDRESS: Optional[str] = None
    SELLER_AGENT_WALLET_ADDRESS: Optional[str] = None
    EVALUATOR_AGENT_WALLET_ADDRESS: Optional[str] = None
    
    # Twitter/Social config
    BUYER_GAME_TWITTER_ACCESS_TOKEN: Optional[str] = None
    SELLER_GAME_TWITTER_ACCESS_TOKEN: Optional[str] = None
    EVALUATOR_GAME_TWITTER_ACCESS_TOKEN: Optional[str] = None
    
    # Entity IDs
    BUYER_ENTITY_ID: Optional[int] = None
    SELLER_ENTITY_ID: Optional[int] = None
    EVALUATOR_ENTITY_ID: Optional[int] = None
    
    @field_validator("WHITELISTED_WALLET_PRIVATE_KEY")
    @classmethod
    def strip_0x_prefix(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v.startswith("0x"):
            raise ValueError("WHITELISTED_WALLET_PRIVATE_KEY must not start with '0x'. Please remove it.")
        return v.strip()

    @field_validator("BUYER_AGENT_WALLET_ADDRESS", "SELLER_AGENT_WALLET_ADDRESS", "EVALUATOR_AGENT_WALLET_ADDRESS")
    @classmethod
    def validate_wallet_address(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        
        v = v.strip()
        if not v:
            return None
            
        if not v.startswith("0x") or len(v) != 42:
            raise ValueError("Wallet address must start with '0x' and be 42 characters long.")
        
        # Validate hex characters
        try:
            int(v, 16)
        except ValueError:
            raise ValueError("Wallet address must contain only valid hexadecimal characters.")
            
        return v.lower() 
    