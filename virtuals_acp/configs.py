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
    payment_token_address: str
    payment_token_decimals: int
    acp_api_url: str
    alchemy_policy_id: str
    alchemy_base_url: str

# Configuration for Base Sepolia
BASE_SEPOLIA_CONFIG = ACPContractConfig(
    chain_env="base-sepolia",
    rpc_url="https://sepolia.base.org",
    chain_id=84532,
    contract_address="0x8Db6B1c839Fc8f6bd35777E194677B67b4D51928",
    payment_token_address="0x036CbD53842c5426634e7929541eC2318f3dCF7e",
    payment_token_decimals=6,
    alchemy_base_url="https://alchemy-proxy.virtuals.io/api/proxy/wallet",
    alchemy_policy_id="186aaa4a-5f57-4156-83fb-e456365a8820",
    acp_api_url="https://acpx.virtuals.gg/api",
)

# Configuration for Base Mainnet
BASE_MAINNET_CONFIG = ACPContractConfig(
    chain_env="base",
    rpc_url="https://mainnet.base.org", 
    chain_id=8453,
    contract_address="0x6a1FE26D54ab0d3E1e3168f2e0c0cDa5cC0A0A4A",
    payment_token_address="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    payment_token_decimals=6,
    alchemy_base_url="https://alchemy-proxy-prod.virtuals.io/api/proxy/wallet",
    alchemy_policy_id="186aaa4a-5f57-4156-83fb-e456365a8820",
    acp_api_url="https://acpx.virtuals.io/api", # PROD
)

# Define the default configuration for the SDK
# For a production-ready SDK, this would typically be BASE_MAINNET_CONFIG.
# For initial development/testing, BASE_SEPOLIA_CONFIG might be more appropriate.
DEFAULT_CONFIG = BASE_MAINNET_CONFIG 
# Or: DEFAULT_CONFIG = BASE_SEPOLIA_CONFIG
