# virtuals_acp/configs.py
from web3 import Web3

from typing import Literal, Optional, List, Dict, Any, TypedDict
from virtuals_acp.fare import Fare
from virtuals_acp.abis.abi import ACP_ABI
from virtuals_acp.abis.abi_v2 import ACP_V2_ABI
from virtuals_acp.models import ChainConfig, X402Config

ChainEnv = Literal["base-sepolia", "base"]

TESTNET_CHAINS = [
    ChainConfig(chain_id=84532, rpc_url="https://base-sepolia.g.alchemy.com/v2"), # baseSepolia,
    # ChainConfig(chain_id=11_155_111, rpc_url="https://eth-sepolia.g.alchemy.com/v2"), #   sepolia
    # ChainConfig(chain_id=80_002, rpc_url="https://polygon-amoy.g.alchemy.com/v2"), #   polygonAmoy
    # ChainConfig(chain_id=421_614, rpc_url="https://arb-sepolia.g.alchemy.com/v2"), #   arbitrumSepolia
    # ChainConfig(chain_id=56, rpc_url="https://bnb-testnet.g.alchemy.com/v2"), #   bscTestnet
]

MAINNET_CHAINS = [
    ChainConfig(chain_id=8453, rpc_url="https://base.g.alchemy.com/v2"), # base
    # ChainConfig(chain_id=1, rpc_url="https://eth-mainnet.g.alchemy.com/v2"), # mainnet
    # ChainConfig(chain_id=137, rpc_url="https://polygon-mainnet.g.alchemy.com/v2"), # polygon
    # ChainConfig(chain_id=42_161, rpc_url="https://arb-mainnet.g.alchemy.com/v2"), # arbitrum
    # ChainConfig(chain_id=56, rpc_url="https://bnb-mainnet.g.alchemy.com/v2"), # bsc
]

class ACPContractConfig:
    def __init__(
        self,
        chain: ChainEnv,
        rpc_url: str,
        chain_id: int,
        contract_address: str,
        base_fare: Fare,
        alchemy_base_url: str,
        acp_api_url: str,
        alchemy_policy_id: str,
        abi: List[Dict[str, Any]],
        rpc_endpoint: Optional[str] = None,
        x402_config: Optional[X402Config] = None,
        chains: Optional[List[ChainConfig]] = None,
    ):
        self.chain = chain
        self.rpc_url = rpc_url
        self.chain_id = chain_id
        self.contract_address = contract_address
        self.base_fare = base_fare
        self.alchemy_base_url = alchemy_base_url
        self.acp_api_url = acp_api_url
        self.alchemy_policy_id = alchemy_policy_id
        self.abi = abi
        self.rpc_endpoint = rpc_endpoint
        self.x402_config = x402_config
        self.chains = chains


BASE_SEPOLIA_CONFIG = ACPContractConfig(
    chain="base-sepolia",
    rpc_url="https://alchemy-proxy.virtuals.io/api/proxy/rpc",
    chain_id=84532,
    contract_address="0x8Db6B1c839Fc8f6bd35777E194677B67b4D51928",
    base_fare=Fare(
        "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
        6,
        84532
    ),
    alchemy_base_url="https://alchemy-proxy.virtuals.io/api/proxy/wallet",
    alchemy_policy_id="186aaa4a-5f57-4156-83fb-e456365a8820",
    acp_api_url="https://acpx.virtuals.gg/api",
    abi=ACP_ABI,
    chains=TESTNET_CHAINS,
)


BASE_SEPOLIA_ACP_X402_CONFIG = ACPContractConfig(
    chain="base-sepolia",
    rpc_url="https://alchemy-proxy.virtuals.io/api/proxy/rpc",
    chain_id=84532,
    contract_address="0x8Db6B1c839Fc8f6bd35777E194677B67b4D51928",
    base_fare=Fare(
        "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
        6,
        84532
    ),
    alchemy_base_url="https://alchemy-proxy.virtuals.io/api/proxy/wallet",
    alchemy_policy_id="186aaa4a-5f57-4156-83fb-e456365a8820",
    acp_api_url="https://acpx.virtuals.gg/api",
    abi=ACP_ABI,
    x402_config=X402Config(
        url="https://dev-acp-x402.virtuals.io",
    ),
    chains=TESTNET_CHAINS,
)


BASE_SEPOLIA_CONFIG_V2 = ACPContractConfig(
    chain="base-sepolia",
    rpc_url="https://alchemy-proxy.virtuals.io/api/proxy/rpc",
    chain_id=84532,
    contract_address="0xdf54E6Ed6cD1d0632d973ADECf96597b7e87893c",
    base_fare=Fare(
        "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
        6,
        84532
    ),
    alchemy_base_url="https://alchemy-proxy.virtuals.io/api/proxy/wallet",
    alchemy_policy_id="186aaa4a-5f57-4156-83fb-e456365a8820",
    acp_api_url="https://acpx.virtuals.gg/api",
    abi=ACP_V2_ABI,
    chains=TESTNET_CHAINS,
)


BASE_SEPOLIA_ACP_X402_CONFIG_V2 = ACPContractConfig(
    chain="base-sepolia",
    rpc_url="https://alchemy-proxy.virtuals.io/api/proxy/rpc",
    chain_id=84532,
    contract_address="0xdf54E6Ed6cD1d0632d973ADECf96597b7e87893c",
    base_fare=Fare(
        "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
        6,
        84532
    ),
    alchemy_base_url="https://alchemy-proxy.virtuals.io/api/proxy/wallet",
    alchemy_policy_id="186aaa4a-5f57-4156-83fb-e456365a8820",
    acp_api_url="https://acpx.virtuals.gg/api",
    abi=ACP_V2_ABI,
    x402_config=X402Config(
        url="https://dev-acp-x402.virtuals.io",
    ),
    chains=TESTNET_CHAINS,
)


BASE_MAINNET_CONFIG = ACPContractConfig(
    chain="base",
    rpc_url="https://alchemy-proxy-prod.virtuals.io/api/proxy/rpc",
    chain_id=8453,
    contract_address="0x6a1FE26D54ab0d3E1e3168f2e0c0cDa5cC0A0A4A",
    base_fare=Fare(
        "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        6,
        8453
    ),
    alchemy_base_url="https://alchemy-proxy.virtuals.io/api/proxy/wallet",
    alchemy_policy_id="186aaa4a-5f57-4156-83fb-e456365a8820",
    acp_api_url="https://acpx.virtuals.io/api",
    abi=ACP_ABI,
    chains=MAINNET_CHAINS,
)


BASE_MAINNET_ACP_X402_CONFIG = ACPContractConfig(
    chain="base",
    rpc_url="https://alchemy-proxy-prod.virtuals.io/api/proxy/rpc",
    chain_id=8453,
    contract_address="0x6a1FE26D54ab0d3E1e3168f2e0c0cDa5cC0A0A4A",
    base_fare=Fare(
        "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        6,
        8453
    ),
    alchemy_base_url="https://alchemy-proxy.virtuals.io/api/proxy/wallet",
    alchemy_policy_id="186aaa4a-5f57-4156-83fb-e456365a8820",
    acp_api_url="https://acpx.virtuals.io/api",
    abi=ACP_ABI,
    x402_config=X402Config(
        url="https://acp-x402.virtuals.io",
    ),
    chains=MAINNET_CHAINS,
)



BASE_MAINNET_CONFIG_V2 = ACPContractConfig(
    chain="base",
    rpc_url="https://alchemy-proxy-prod.virtuals.io/api/proxy/rpc",
    chain_id=8453,
    contract_address="0xa6C9BA866992cfD7fd6460ba912bfa405adA9df0",
    base_fare=Fare(
        "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        6,
        8453
    ),
    alchemy_base_url="https://alchemy-proxy.virtuals.io/api/proxy/wallet",
    alchemy_policy_id="186aaa4a-5f57-4156-83fb-e456365a8820",
    acp_api_url="https://acpx.virtuals.io/api",
    abi=ACP_V2_ABI,
    chains=MAINNET_CHAINS,
)


BASE_MAINNET_ACP_X402_CONFIG_V2 = ACPContractConfig(
    chain="base",
    rpc_url="https://alchemy-proxy-prod.virtuals.io/api/proxy/rpc",
    chain_id=8453,
    contract_address="0xa6C9BA866992cfD7fd6460ba912bfa405adA9df0",
    base_fare=Fare(
        "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        6,
        8453
    ),
    alchemy_base_url="https://alchemy-proxy.virtuals.io/api/proxy/wallet",
    alchemy_policy_id="186aaa4a-5f57-4156-83fb-e456365a8820",
    acp_api_url="https://acpx.virtuals.io/api",
    abi=ACP_V2_ABI,
    x402_config=X402Config(
        url="https://acp-x402.virtuals.io",
    ),
    chains=MAINNET_CHAINS,
)


DEFAULT_CONFIG = BASE_MAINNET_CONFIG_V2
# Or: DEFAULT_CONFIG = BASE_SEPOLIA_CONFIG_V2
