# virtuals_acp/contract_manager.py

import time
from datetime import datetime
from typing import Optional, Dict, Any

from eth_account import Account
from web3 import Web3
from web3.contract import Contract

from virtuals_acp.abi import ACP_ABI, ERC20_ABI
from virtuals_acp.alchemy import AlchemyAccountKit
from virtuals_acp.configs import ACPContractConfig
from virtuals_acp.models import ACPJobPhase, MemoType


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

    def _validate_transaction(
            self,
            hash_value: str,
            retry: bool = True,
            retry_count: int = 3
    ) -> Dict[str, Any]:
        attempts = 0
        while True:
            try:
                result = self.alchemy_kit.get_calls_status(hash_value)
                if result.get("status") == 200:
                    return result
                raise Exception(f"Unexpected status: {result.get('status')}")
            except Exception as e:
                attempts += 1
                if not retry or attempts >= retry_count:
                    raise Exception(f"Failed to validate transaction after {attempts} attempt(s): {e}")
                time.sleep(2 * attempts)


    def _sign_transaction(
            self,
            method_name: str,
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

        if not self.alchemy_kit.permissions_context:
            self.alchemy_kit.create_session()

        send_result = self.alchemy_kit.execute_calls(trx_data)
        user_op_hash = self.alchemy_kit.get_user_operation_hash(send_result)

        return user_op_hash

    def create_job(
            self,
            provider_address: str,
            evaluator_address: str,
            expire_at: datetime
    ) -> Dict[str, Any]:
        provider_address = Web3.to_checksum_address(provider_address)
        evaluator_address = Web3.to_checksum_address(evaluator_address)
        expire_timestamp = int(expire_at.timestamp())

        user_op_hash = self._sign_transaction(
            "createJob",
            [provider_address, evaluator_address, expire_timestamp]
        )

        if user_op_hash is None:
            raise Exception("Failed to sign transaction - approve_allowance")

        return self._validate_transaction(user_op_hash)


    def approve_allowance(self, price_in_wei: int) -> Dict[str, Any]:
        user_op_hash = self._sign_transaction(
            "approve",
            [self.config.contract_address, price_in_wei],
            self.config.virtuals_token_address
        )

        if user_op_hash is None:
            raise Exception("Failed to sign transaction - approve_allowance")

        return self._validate_transaction(user_op_hash)


    def create_memo(
            self,
            job_id: int,
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

        return self._validate_transaction(user_op_hash)


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

        return self._validate_transaction(user_op_hash)


    def set_budget(self, job_id: int, budget: int) -> Dict[str, Any]:
        user_op_hash = self._sign_transaction(
            "setBudget",
            [job_id, budget]
        )

        if user_op_hash is None:
            raise Exception("Failed to sign transaction - set_budget")

        return self._validate_transaction(user_op_hash)
