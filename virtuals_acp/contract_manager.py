# virtuals_acp/contract_manager.py

import json
import time
from datetime import datetime
from typing import Optional, Tuple, Dict, Any, Union
import requests

from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3
from web3.contract import Contract

from virtuals_acp.abi import ACP_ABI, ERC20_ABI
from virtuals_acp.alchemy import AlchemyAccountKit
from virtuals_acp.configs import ACPContractConfig
from virtuals_acp.models import ACPJobPhase, MemoType, FeeType


class _ACPContractManager:
    def __init__(
            self,
            web3_client: Web3,
            agent_wallet_address: str,
            entity_id: int,
            config: ACPContractConfig,
            wallet_private_key: str
    ):
        self.w3 = web3_client
        self.account = Account.from_key(wallet_private_key)
        self.config = config
        self.alchemy_kit = AlchemyAccountKit(agent_wallet_address, entity_id, self.account, config.chain_id)
        self.alchemy_account = None
        self.agent_wallet_address = agent_wallet_address
     
        self.contract: Contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(config.contract_address), abi=ACP_ABI
        )
        self.token_contract: Contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(config.virtuals_token_address), abi=ERC20_ABI
        )
        
    def validate_transaction(self, hash_value: str) -> Dict[str, Any]:
        try:
            return self.alchemy_kit.get_calls_status(hash_value)
        except Exception as e:
            raise Exception(f"Failed to get job_id {e}")
    
    def _sign_transaction(
            self, method_name: str,
            args: list,
            contract_address: Optional[str] = None
    ) -> str:
        if contract_address:
            encoded_data = self.token_contract.encode_abi(method_name, args=args)
        else:
            encoded_data = self.contract.encode_abi(method_name, args=args)
        
        trx_data = [{
            "to": contract_address if contract_address else self.config.contract_address,
            "data": encoded_data
        }]

        self.alchemy_kit.create_session()
        send_result = self.alchemy_kit.execute_calls(trx_data)
        user_op_hash = self.alchemy_kit.get_user_operation_hash(send_result)

        return user_op_hash
        
    def create_job(
        self,
        agent_wallet_address: str,
        provider_address: str,
        evaluator_address: str,
        expire_at: datetime
    ) -> str:
        retries = 3
        while retries > 0:
            try:
                provider_address = Web3.to_checksum_address(provider_address)
                evaluator_address = Web3.to_checksum_address(evaluator_address)
                expire_timestamp = int(expire_at.timestamp())
        
                # Sign the transaction
                user_op_hash = self._sign_transaction(
                    "createJob", 
                    [provider_address, evaluator_address, expire_timestamp]
                )
                return user_op_hash
            except Exception as e:
                if (retries == 1):
                    print(f"Failed to create job: {e}")
                retries -= 1
                time.sleep(2 * (3 - retries))
        raise Exception("Failed to create job")
                

    def approve_allowance(self, price_in_wei: int) -> Dict[str, Any]:
        user_op_hash = self._sign_transaction(
            "approve", 
            [self.config.contract_address, price_in_wei],
            self.config.virtuals_token_address
        )
        
        if user_op_hash is None:
            raise Exception("Failed to sign transaction - approve_allowance")
        
        retries = 3
        while retries > 0:
            try:
                result = self.validate_transaction(user_op_hash)
                
                if result.get("status") == 200:
                    return result
                else:
                    raise Exception(f"Failed to approve allowance")
            except Exception as e:
                retries -= 1
                if retries == 0:
                    print(f"Error during approve_allowance: {e}")
                    raise
                time.sleep(2 * (3 - retries))
                
        raise Exception("Failed to approve allowance")


    def create_payable_fee_memo(
            self,
            job_id: int,
            content: str,
            amount: int,
            memo_type: Union[MemoType.PAYABLE_FEE, MemoType.PAYABLE_FEE_REQUEST],
            next_phase: ACPJobPhase,
    ) -> Dict[str, Any]:
        user_op_hash = self._sign_transaction(
            "createPayableFeeMemo",
            [job_id, content, amount, memo_type.value, next_phase.value]
        )

        if user_op_hash is None:
            raise Exception("Failed to sign transaction - create_payable_fee_memo")

        retries = 3
        while retries > 0:
            try:
                result = self.validate_transaction(user_op_hash)

                if result.get("status") == 200:
                    return result
                else:
                    raise Exception(f"Failed to create payable fee memo")
            except Exception as e:
                retries -= 1
                if retries == 0:
                    print(f"Error during create_payable_fee_memo: {e}")
                    raise
                time.sleep(2 * (3 - retries))

        raise Exception(f"Failed to create payable fee memo")


    def create_payable_memo(
            self,
            job_id: int,
            content: str,
            amount: int,
            receiver_address: str,
            fee_amount: int,
            fee_type: FeeType,
            next_phase: ACPJobPhase,
            memo_type: Union[MemoType.PAYABLE_REQUEST, MemoType.PAYABLE_TRANSFER],
            token: Optional[str] = None
    ) -> Dict[str, Any]:
        receiver_address = Web3.to_checksum_address(receiver_address)
        token = self.config.virtuals_token_address if token is None else token

        user_op_hash = self._sign_transaction(
            "createPayableMemo",
            [
                job_id,
                content,
                token,
                amount,
                receiver_address,
                fee_amount,
                fee_type.value,
                memo_type.value,
                next_phase.value
            ]
        )

        if user_op_hash is None:
            raise Exception("Failed to sign transaction - create_payable_memo")

        retries = 3
        while retries > 0:
            try:
                result = self.validate_transaction(user_op_hash)

                if result.get("status") == 200:
                    return result
                else:
                    raise Exception(f"Failed to create payable memo")
            except Exception as e:
                retries -= 1
                if retries == 0:
                    print(f"Error during create_payable_memo: {e}")
                    raise
                time.sleep(2 * (3 - retries))

        raise Exception(f"Failed to create payable memo")


    def create_memo(
            self, job_id: int,
            content: str,
            memo_type: MemoType,
            is_secured: bool,
            next_phase: ACPJobPhase
    ) -> Dict[str, Any]:
        user_op_hash = self._sign_transaction(
            "createMemo",
            [job_id, content, memo_type.value, is_secured, next_phase.value]
        )

        if user_op_hash is None:
            raise Exception("Failed to sign transaction - create_memo")

        retries = 3
        while retries > 0:
            try:
                result = self.validate_transaction(user_op_hash)

                if result.get("status") == 200:
                    return result
                else:
                    raise Exception(f"Failed to create memo")

            except Exception as e:
                retries -= 1
                if retries == 0:
                    print(f"Error during create_memo: {e}")
                    raise
                time.sleep(2 * (3 - retries))

        raise Exception("Failed to create memo")


    def sign_memo(
        self,
        memo_id: int,
        is_approved: bool,
        reason: Optional[str] = ""
    ) -> Dict[str, Any]:
        user_op_hash = self._sign_transaction(
            "signMemo", 
            [memo_id, is_approved, reason]
        )
        
        if user_op_hash is None:
            raise Exception("Failed to sign transaction - sign_memo")
        
        retries = 3
        while retries > 0:
            try:
                result = self.validate_transaction(user_op_hash)
                
                if result.get("status") == 200:
                    return result
                else:
                    raise Exception(f"Failed to sign memo")
            except Exception as e:
                retries -= 1
                if retries == 0:
                    print(f"Error during sign_memo: {e}")
                    raise
                time.sleep(2 * (3 - retries))
                
        raise Exception(f"Failed to sign memo")
    
    def set_budget(self, job_id: int, budget: int) -> Dict[str, Any]:
        user_op_hash = self._sign_transaction(
            "setBudget", 
            [job_id, budget]
        )
        
        if user_op_hash is None:
            raise Exception("Failed to sign transaction - set_budget")
        
        retries = 3
        while retries > 0:
            try:
                result = self.validate_transaction(user_op_hash)
                
                if result.get("status") == 200:
                    return result
                else:
                    raise Exception(f"Failed to set budget {result}")
                
            except Exception as e:
                retries -= 1
                if retries == 0:
                    print(f"Error during set_budget: {e}")
                    raise
                time.sleep(2 * (3 - retries))
                
        raise Exception("Failed to set budget")
