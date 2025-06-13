# virtuals_acp/configs.py
from dataclasses import dataclass
from typing import Literal

ChainEnv = Literal["base-sepolia", "base"]

@dataclass
class ACPContractConfig:
    chain_env: ChainEnv
    rpc_url: str
    chain_id: int
    contract_address: str
    virtuals_token_address: str
    acp_api_url: str
    alchemy_policy_id: str
    alchemy_base_url: str

# Configuration for Base Sepolia
BASE_SEPOLIA_CONFIG = ACPContractConfig(
    chain_env="base-sepolia",
    rpc_url="https://sepolia.base.org",
    chain_id=84532,
    contract_address="0x2422c1c43451Eb69Ff49dfD39c4Dc8C5230fA1e6",
    virtuals_token_address="0xbfAB80ccc15DF6fb7185f9498d6039317331846a",
    alchemy_base_url="https:/alchemy-proxy.virtuals.io/v2",
    alchemy_policy_id="186aaa4a-5f57-4156-83fb-e456365a8820",
    acp_api_url="https://acpx-staging.virtuals.io/api",
)

# Configuration for Base Mainnet
BASE_MAINNET_CONFIG = ACPContractConfig(
    chain_env="base",
    rpc_url="https://mainnet.base.org", 
    chain_id=8453,
    contract_address="0x2422c1c43451Eb69Ff49dfD39c4Dc8C5230fA1e6",
    virtuals_token_address="0xbfAB80ccc15DF6fb7185f9498d6039317331846a",
    alchemy_base_url="https://alchemy-proxy-prod.virtuals.io/api/proxy/rpc",
    alchemy_policy_id="186aaa4a-5f57-4156-83fb-e456365a8820",
    acp_api_url="https://acpx.virtuals.io/api", # PROD
)

# Define the default configuration for the SDK
# For a production-ready SDK, this would typically be BASE_MAINNET_CONFIG.
# For initial development/testing, BASE_SEPOLIA_CONFIG might be more appropriate.
DEFAULT_CONFIG = BASE_MAINNET_CONFIG 
# Or: DEFAULT_CONFIG = BASE_SEPOLIA_CONFIG
