# virtuals_acp/contract_manager.py

import math
import time
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any

from eth_account import Account
from web3 import Web3
from web3.contract import Contract

from virtuals_acp.abi import ACP_ABI, ERC20_ABI
from virtuals_acp.alchemy import AlchemyAccountKit
from virtuals_acp.base_contract_manager import BaseACPContractManager
from virtuals_acp.configs import ACPContractConfig
from virtuals_acp.models import ACPJobPhase, MemoType, FeeType


class ACPContractManager(BaseACPContractManager):
    def __init__(
            self,
            web3_client: Web3,
            agent_wallet_address: str,
            entity_id: int,
            config: ACPContractConfig,
            wallet_private_key: str
    ):
        super().__init__(web3_client, agent_wallet_address, entity_id, config)
        self.account = Account.from_key(wallet_private_key)
        self.alchemy_kit = AlchemyAccountKit(agent_wallet_address, entity_id, self.account, config.chain_id)
        self.alchemy_account = None

        self.contract: Contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(config.contract_address), abi=ACP_ABI
        )
        self.token_contract: Contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(config.payment_token_address), abi=ERC20_ABI
        )

    def _format_amount(self, amount: float) -> int:
        amount_decimal = Decimal(str(amount))
        return int(amount_decimal * (10 ** self.config.payment_token_decimals))

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

    def validate_transaction(self, hash_value: str) -> Dict[str, Any]:
        try:
            return self.alchemy_kit.get_calls_status(hash_value)
        except Exception as e:
            raise Exception(f"Failed to get job_id {e}")

    def create_job(
            self,
            provider_address: str,
            evaluator_address: str,
            expired_at: datetime
    ) -> str:
        retries = 3
        while retries > 0:
            try:
                provider_address = Web3.to_checksum_address(provider_address)
                evaluator_address = Web3.to_checksum_address(evaluator_address)
                expire_timestamp = int(expired_at.timestamp())

                # Sign the transaction
                user_op_hash = self._sign_transaction(
                    "createJob",
                    [provider_address, evaluator_address, expire_timestamp]
                )
                return user_op_hash
            except Exception as e:
                if retries == 1:
                    print(f"Failed to create job: {e}")
                retries -= 1
                time.sleep(2 * (3 - retries))
        raise Exception("Failed to create job")

    def approve_allowance(self, amount: float) -> Dict[str, Any]:
        user_op_hash = self._sign_transaction(
            "approve",
            [self.config.contract_address, self._format_amount(amount)],
            self.config.payment_token_address
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

    def create_payable_memo(
            self,
            job_id: int,
            content: str,
            amount: float,
            receiver_address: str,
            fee_amount: float,
            fee_type: FeeType,
            next_phase: ACPJobPhase,
            memo_type: MemoType,
            expired_at: datetime,
            token: Optional[str] = None
    ) -> Dict[str, Any]:
        receiver_address = Web3.to_checksum_address(receiver_address)
        token = self.config.payment_token_address if token is None else token

        user_op_hash = self._sign_transaction(
            "createPayableMemo",
            [
                job_id,
                content,
                token,
                self._format_amount(amount),
                receiver_address,
                self._format_amount(fee_amount),
                fee_type.value,
                memo_type.value,
                next_phase.value,
                math.floor(expired_at.timestamp())
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

    def set_budget(self, job_id: int, budget: float) -> Dict[str, Any]:
        user_op_hash = self._sign_transaction(
            "setBudget",
            [job_id, self._format_amount(budget)]
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

    def set_budget_with_payment_token(
            self, job_id: int,
            budget: float,
            payment_token_address: str = None,
    ) -> Dict[str, Any]:

        if payment_token_address is None:
            payment_token_address = self.config.payment_token_address

        user_op_hash = self._sign_transaction(
            "setBudgetWithPaymentToken",
            [job_id, self._format_amount(budget), payment_token_address]
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
