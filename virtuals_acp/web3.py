from typing import Union

from web3 import Web3
from virtuals_acp.abis.erc20_abi import ERC20_ABI


def getERC20Balance(
    public_client: Web3,
    contract_address: str,
    wallet_address: str,
) -> int:
    erc20_contract_instance = public_client.eth.contract(
        address=contract_address, abi=ERC20_ABI
    )
    
    balance = erc20_contract_instance.functions.balanceOf(wallet_address).call()
    
    return balance

def getERC20Allowance(
    public_client: Web3,
    contract_address: str,
    wallet_address: str,
    spender_address: str,
) -> int:
    erc20_contract_instance = public_client.eth.contract(
        address=contract_address, abi=ERC20_ABI
    )
    
    allowance = erc20_contract_instance.functions.allowance(wallet_address, spender_address).call()
    
    return allowance

def getERC20Symbol(
    public_client: Web3,
    contract_address: str,
) -> str:
    erc20_contract_instance = public_client.eth.contract(
        address=contract_address, abi=ERC20_ABI
    )
    
    symbol = erc20_contract_instance.functions.symbol().call()
    
    return symbol

def getERC20Decimals(
    public_client: Web3,
    contract_address: str,
) -> int:
    erc20_contract_instance = public_client.eth.contract(
        address=contract_address, abi=ERC20_ABI
    )
    
    decimals = erc20_contract_instance.functions.decimals().call()
    
    return decimals