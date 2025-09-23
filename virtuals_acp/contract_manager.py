# virtuals_acp/contract_manager.py

import math
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any

from eth_account import Account
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
        wallet_private_key: str,
    ):
        self.w3 = web3_client
        self.account = Account.from_key(wallet_private_key)
        self.config = config
        self.alchemy_kit = AlchemyAccountKit(
            agent_wallet_address, entity_id, self.account, config.chain_id
        )
        self.agent_wallet_address = agent_wallet_address

        self.contract: Contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(config.contract_address), abi=ACP_ABI
        )
        self.token_contract: Contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(config.payment_token_address),
            abi=ERC20_ABI,
        )

    def _format_amount(self, amount: float) -> int:
        amount_decimal = Decimal(str(amount))
        return int(amount_decimal * (10**self.config.payment_token_decimals))

    def _send_user_operation(
        self, method_name: str, args: list, contract_address: Optional[str] = None
    ) -> Dict[str, Any]:
        if contract_address:
            encoded_data = self.token_contract.encode_abi(method_name, args=args)
        else:
            encoded_data = self.contract.encode_abi(method_name, args=args)

        trx_data = [
            {
                "to": (
                    contract_address
                    if contract_address
                    else self.config.contract_address
                ),
                "data": encoded_data,
            }
        ]

        return self.alchemy_kit.handle_user_operation(trx_data)

    def create_job(
        self, provider_address: str, evaluator_address: str, expired_at: datetime
    ) -> Dict[str, Any]:
        try:

            provider_address = Web3.to_checksum_address(provider_address)
            evaluator_address = Web3.to_checksum_address(evaluator_address)
            expire_timestamp = int(expired_at.timestamp())

            return self._send_user_operation(
                "createJob", [provider_address, evaluator_address, expire_timestamp]
            )
        except Exception as e:
            raise Exception("Failed to create job", e)

    def approve_allowance(self, amount: float) -> Dict[str, Any]:
        try:
            return self._send_user_operation(
                "approve",
                [self.config.contract_address, self._format_amount(amount)],
                self.config.payment_token_address,
            )
        except Exception as e:
            raise Exception("Failed to approve allowance", e)

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
        token: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            receiver_address = Web3.to_checksum_address(receiver_address)
            token = self.config.payment_token_address if token is None else token

            return self._send_user_operation(
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
                    math.floor(expired_at.timestamp()),
                ],
            )
        except Exception as e:
            raise Exception("Failed to create payable memo", e)

    def create_memo(
        self,
        job_id: int,
        content: str,
        memo_type: MemoType,
        is_secured: bool,
        next_phase: ACPJobPhase,
    ) -> Dict[str, Any]:
        try:
            return self._send_user_operation(
                "createMemo",
                [job_id, content, memo_type.value, is_secured, next_phase.value],
            )
        except Exception as e:
            raise Exception("Failed to create memo", e)

    def sign_memo(
        self, memo_id: int, is_approved: bool, reason: Optional[str] = ""
    ) -> Dict[str, Any]:
        try:
            return self._send_user_operation("signMemo", [memo_id, is_approved, reason])
        except Exception as e:
            raise Exception("Failed to sign memo", e)

    def set_budget(self, job_id: int, budget: float) -> Dict[str, Any]:
        try:
            return self._send_user_operation(
                "setBudget", [job_id, self._format_amount(budget)]
            )
        except Exception as e:
            raise Exception("Failed to set budget", e)

    def set_budget_with_payment_token(
        self,
        job_id: int,
        budget: float,
        payment_token_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            if payment_token_address is None:
                payment_token_address = self.config.payment_token_address

            return self._send_user_operation(
                "setBudgetWithPaymentToken",
                [job_id, self._format_amount(budget), payment_token_address],
            )
        except Exception as e:
            raise Exception("Failed to set budget with payment token", e)
