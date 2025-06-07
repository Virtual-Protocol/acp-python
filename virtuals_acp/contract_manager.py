# virtuals_acp/contract_manager.py

import json
import time
from datetime import datetime
from typing import Optional, Tuple
import requests

from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3
from web3.contract import Contract

from virtuals_acp.abi import ACP_ABI, ERC20_ABI
from virtuals_acp.configs import ACPContractConfig
from virtuals_acp.models import ACPJobPhase, MemoType



class _ACPContractManager:
    def __init__(self, web3_client: Web3, config: ACPContractConfig, wallet_private_key: str):
        self.w3 = web3_client
        self.account = Account.from_key(wallet_private_key)
        self.config = config
     
        self.contract: Contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(config.contract_address), abi=ACP_ABI
        )
        self.token_contract: Contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(config.virtuals_token_address), abi=ERC20_ABI
        )
        
    def validate_transaction(self, hash_value: str) -> object:
        try:
            response = requests.post(f"{self.config.acp_api_url}/acp-agent-wallets/trx-result", json={"userOpHash": hash_value})
            return response.json()
        except Exception as e:
            raise Exception(f"Failed to get job_id {e}")
    
    def _sign_transaction(self, method_name: str, args: list, contract_address: Optional[str] = None) -> Tuple[dict, str]:
        if contract_address:
            encoded_data = self.token_contract.encode_abi(method_name, args=args)
        else:
            encoded_data = self.contract.encode_abi(method_name, args=args)
        
        trx_data = {
            "target": contract_address if contract_address else self.config.contract_address,
            "value": "0",
            "data": encoded_data
        }
        
        message_json = json.dumps(trx_data, separators=(",", ":"), sort_keys=False)
        message_bytes = message_json.encode()
        
        # Sign the transaction
        message = encode_defunct(message_bytes)
        signature = "0x" + self.account.sign_message(message).signature.hex()
        return trx_data, signature

    def create_job(
        self,
        agent_wallet_address: str,
        provider_address: str,
        evaluator_address: str,
        expire_at: datetime
    ) -> dict:
        retries = 3
        while retries > 0:
            try:
                provider_address = Web3.to_checksum_address(provider_address)
                evaluator_address = Web3.to_checksum_address(evaluator_address)
                expire_timestamp = int(expire_at.timestamp())
        
                # Sign the transaction
                trx_data, signature = self._sign_transaction(
                    "createJob", 
                    [provider_address, evaluator_address, expire_timestamp]
                )
                    
                # Prepare payload
                payload = {
                    "agentWallet": agent_wallet_address,
                    "trxData": trx_data,
                    "signature": signature
                }
                # Submit to custom API
                api_url = f"{self.config.acp_api_url}/acp-agent-wallets/transactions"
                response = requests.post(api_url, json=payload)
                
                if response.json().get("error"):
                    raise Exception(f"Failed to create job {response.json().get('error').get('status')}, Message: {response.json().get('error').get('message')}")
                
                # Return transaction hash or response ID
                return {"txHash": response.json().get("data", {}).get("userOpHash", "")}
            except Exception as e:
                if (retries == 1):
                    print(f"Failed to create job: {e}")
                retries -= 1
                time.sleep(2 * (3 - retries))
                

    def approve_allowance(self, agent_wallet_address: str, price_in_wei: int) -> str:
        retries = 3
        while retries > 0:
            try:
                trx_data, signature = self._sign_transaction(
                    "approve", 
                    [self.config.contract_address, price_in_wei],
                    self.config.virtuals_token_address
                )
            
                payload = {
                    "agentWallet": agent_wallet_address,
                    "trxData": trx_data,
                    "signature": signature
                }
                
                api_url = f"{self.config.acp_api_url}/acp-agent-wallets/transactions"
                response = requests.post(api_url, json=payload)
                data = response.json()
                
                if (data.get("error")):
                    raise Exception(
                    f"Failed to approve allowance {data['error'].get('status')}, "
                    f"Message: {data['error'].get('message')}"
                )
                    
                return data
            except Exception as e:
                retries -= 1
                if retries == 0:
                    print(f"Error during approve_allowance: {e}")
                    raise
                time.sleep(2 * (3 - retries))

    def get_balance(self, agent_wallet_address: str) -> float:
        balance = self.token_contract.functions.balanceOf(Web3.to_checksum_address(agent_wallet_address)).call()
        return balance / 10 ** 18
        
    def create_memo(self, agent_wallet_address: str, job_id: int, content: str, memo_type: MemoType, is_secured: bool, next_phase: ACPJobPhase) -> str:
        retries = 3

        while retries > 0:
            try:
                trx_data, signature = self._sign_transaction(
                    "createMemo", 
                    [job_id, content, memo_type.value, is_secured, next_phase.value]
                )
                

                payload = {
                    "agentWallet": agent_wallet_address,
                    "trxData": trx_data,
                    "signature": signature
                }
                

                api_url = f"{self.config.acp_api_url}/acp-agent-wallets/transactions"
                response = requests.post(api_url, json=payload)
                
                if (response.json().get("error")):
                    raise Exception(f"Failed to create memo {response.json().get('error').get('status')}, Message: {response.json().get('error').get('message')}")
                
                return { "txHash": response.json().get("txHash", response.json().get("id", "")), "id": response.json().get("id", "")}
            except Exception as e:
                retries -= 1
                if retries == 0:
                    print(f"Error during create_memo: {e}")
                    raise
                time.sleep(2 * (3 - retries))


    def sign_memo(
        self,
        agent_wallet_address: str,
        memo_id: int,
        is_approved: bool,
        reason: Optional[str] = ""
    ) -> str:
        retries = 3
        while retries > 0:
            try:
                trx_data, signature = self._sign_transaction(
                    "signMemo", 
                    [memo_id, is_approved, reason]
                )
                
                payload = {
                    "agentWallet": agent_wallet_address,
                    "trxData": trx_data,
                    "signature": signature
                }
                
                api_url = f"{self.config.acp_api_url}/acp-agent-wallets/transactions"
                response = requests.post(api_url, json=payload)
                
                if (response.json().get("error")):
                    raise Exception(f"Failed to sign memo {response.json().get('error').get('status')}, Message: {response.json().get('error').get('message')}")
                
                return response.json()
                
            except Exception as e:
                retries -= 1
                if retries == 0:
                    print(f"Error during sign_memo: {e}")
                    raise
                time.sleep(2 * (3 - retries))
                
        raise Exception(f"Failed to sign memo")
    
    def set_budget(self, agent_wallet_address: str, job_id: int, budget: int) -> str:
        retries = 3
        while retries > 0:
            try:
                trx_data, signature = self._sign_transaction(
                    "setBudget", 
                    [job_id, budget]
                )
                
                payload = {
                    "agentWallet": agent_wallet_address,
                    "trxData": trx_data,
                    "signature": signature
                }
                
                api_url = f"{self.config.acp_api_url}/acp-agent-wallets/transactions"
                response = requests.post(api_url, json=payload)
                
                if (response.json().get("error")):
                    raise Exception(f"Failed to set budget {response.json().get('error').get('status')}, Message: {response.json().get('error').get('message')}")
                
                return response.json()
            except Exception as e:
                retries -= 1
                if retries == 0:
                    print(f"Error during set_budget: {e}")
                    raise
                time.sleep(2 * (3 - retries))
                
        