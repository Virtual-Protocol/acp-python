# virtuals_acp/contract_manager.py

import math
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any

from eth_account import Account
from web3 import Web3
from web3.contract import Contract
from web3.middleware import ExtraDataToPOAMiddleware

from virtuals_acp.abi import ACP_ABI, ERC20_ABI
from virtuals_acp.alchemy import AlchemyAccountKit
from virtuals_acp.configs import ACPContractConfig
from virtuals_acp.models import ACPJobPhase, MemoType, FeeType
from eth_account.signers.local import LocalAccount


class ACPContractManager:
    def __init__(
        self,
        wallet_private_key: str,
        agent_wallet_address: str,
        entity_id: int,
        config: ACPContractConfig,
    ):
        self.wallet_private_key = wallet_private_key
        self.config = config
        self.w3 = Web3(Web3.HTTPProvider(self.config.rpc_url))
        self.account = Account.from_key(wallet_private_key)

        if self.config.chain == "base-sepolia":
            self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        
        if not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to RPC URL: {config.rpc_url}")

        self.alchemy_kit = AlchemyAccountKit(
            agent_wallet_address, entity_id, self.account, config.chain_id
        )
        self.agent_wallet_address = agent_wallet_address

        self.contract: Contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(config.contract_address), abi=ACP_ABI
        )
        self.token_contract: Contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(config.base_fare.contract_address),
            abi=ERC20_ABI,
        )

    def _format_amount(self, amount: float) -> int:
        amount_decimal = Decimal(str(amount))
        return int(amount_decimal * (10**self.config.base_fare.decimals))

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

    def approve_allowance(
            self, 
            amount_base_unit: int,
            payment_token_address: Optional[str] = None,
        ) -> Dict[str, Any]:
        try:
            if payment_token_address is None:
                payment_token_address = self.config.base_fare.contract_address

            return self._send_user_operation(
                "approve",
                [self.config.contract_address, amount_base_unit],
                payment_token_address,
            )
        except Exception as e:
            raise Exception("Failed to approve allowance", e)

    def create_payable_memo(
        self,
        job_id: int,
        content: str,
        amount_base_unit: int,
        recipient: str,
        fee_amount_base_unit: int,
        fee_type: FeeType,
        next_phase: ACPJobPhase,
        memo_type: MemoType,
        expired_at: datetime,
        token: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            receiver_address = Web3.to_checksum_address(recipient)
            token = self.config.payment_token_address if token is None else token

            return self._send_user_operation(
                "createPayableMemo",
                [
                    job_id,
                    content,
                    token,
                    amount_base_unit,
                    receiver_address,
                    fee_amount_base_unit,
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
                "setBudget", [job_id, budget]
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
                payment_token_address = self.config.base_fare.contract_address

            return self._send_user_operation(
                "setBudgetWithPaymentToken",
                [job_id, budget, payment_token_address],
            )
        except Exception as e:
            raise Exception("Failed to set budget with payment token", e)
