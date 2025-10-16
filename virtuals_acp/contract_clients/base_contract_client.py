from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
import math
from typing import Dict, Any, Optional, List, cast

from eth_typing import ABIEvent
from web3 import Web3
from web3.contract import Contract
from eth_utils.abi import event_abi_to_log_topic

from virtuals_acp.abis.erc20_abi import ERC20_ABI
from virtuals_acp.abis.weth_abi import WETH_ABI
from virtuals_acp.configs.configs import ACPContractConfig
from virtuals_acp.exceptions import ACPError
from virtuals_acp.models import ACPJobPhase, MemoType, FeeType


class BaseAcpContractClient(ABC):
    def __init__(self, agent_wallet_address: str, config: ACPContractConfig):
        self.agent_wallet_address = Web3.to_checksum_address(agent_wallet_address)
        self.config = config
        self.w3 = Web3(Web3.HTTPProvider(config.rpc_url))

        self.chain = config.chain
        self.abi = config.abi
        self.contract_address = Web3.to_checksum_address(config.contract_address)

        if not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to RPC: {config.rpc_url}")

        self.contract: Contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(config.contract_address),
            abi=self.abi,
        )
        self.token_contract: Contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(config.base_fare.contract_address),
            abi=self.abi,
        )

        job_created_event_abi = next(
            (
                item
                for item in config.abi
                if item.get("type") == "event" and item.get("name") == "JobCreated"
            ),
            None,
        )

        if not job_created_event_abi:
            raise ACPError("JobCreated event not found in ACP_ABI")

        self.job_created_event_signature_hex = (
            "0x" + event_abi_to_log_topic(cast(ABIEvent, job_created_event_abi)).hex()
        )

    def _build_user_operation(
        self,
        method_name: str,
        args: List[Any],
        contract_address: Optional[str] = None,
        abi: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Build a single-call user operation to invoke a contract method.
        If no ABI is provided, defaults to the ACP contract ABI.
        """
        target_abi = abi or self.abi
        target_address = Web3.to_checksum_address(
            contract_address or self.config.contract_address
        )

        target_contract = self.w3.eth.contract(address=target_address, abi=target_abi)
        encoded_data = target_contract.encode_abi(method_name, args=args)

        return [{"to": target_address, "data": encoded_data}]

    @abstractmethod
    def _send_user_operation(self, trx_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_job_id(
        self, receipt: Dict[str, Any], client_address: str, provider_address: str
    ) -> int:
        """Abstract method to retrieve a job ID from a transaction hash and related addresses."""
        pass

    def _format_amount(self, amount: float) -> int:
        return int(Decimal(str(amount)) * (10**self.config.base_fare.decimals))

    def update_account_metadata(self, account_id: int, metadata: str) -> Dict[str, Any]:
        data = self._build_user_operation(
            "updateAccountMetadata",
            [account_id, metadata],
            self.config.contract_address,
        )
        return self._send_user_operation(data)

    def create_job(
        self,
        provider_address: str,
        evaluator_address: str,
        expired_at: datetime,
        payment_token_address: str,
        budget_base_unit: int,
        metadata: str,
    ) -> Dict[str, Any]:
        data = self._build_user_operation(
            "createJob",
            [
                Web3.to_checksum_address(provider_address),
                Web3.to_checksum_address(evaluator_address),
                math.floor(expired_at.timestamp()),
                payment_token_address,
                budget_base_unit,
                metadata,
            ],
        )
        return self._send_user_operation(data)

    def create_job_with_account(
        self,
        account_id: int,
        evaluator_address: str,
        budget_base_unit: int,
        payment_token_address: str,
        expired_at: datetime,
    ) -> Dict[str, Any]:
        data = self._build_user_operation(
            "createJobWithAccount",
            [
                account_id,
                Web3.to_checksum_address(evaluator_address),
                budget_base_unit,
                Web3.to_checksum_address(payment_token_address),
                math.floor(expired_at.timestamp()),
            ],
        )
        return self._send_user_operation(data)

    def approve_allowance(
        self,
        amount_base_unit: int,
        payment_token_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        data = self._build_user_operation(
            "approve",
            [self.config.contract_address, amount_base_unit],
            contract_address=payment_token_address,
            abi=ERC20_ABI,
        )
        return self._send_user_operation(data)

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
        secured: bool = True,
    ) -> Dict[str, Any]:
        data = self._build_user_operation(
            "createPayableMemo",
            [
                job_id,
                content,
                token or self.config.base_fare.contract_address,
                amount_base_unit,
                Web3.to_checksum_address(recipient),
                fee_amount_base_unit,
                fee_type,
                memo_type,
                math.floor(expired_at.timestamp()),
                secured,
                next_phase,
            ],
            self.config.contract_address,
        )
        return self._send_user_operation(data)

    def create_memo(
        self,
        job_id: int,
        content: str,
        memo_type: MemoType,
        is_secured: bool,
        next_phase: ACPJobPhase,
    ) -> Dict[str, Any]:
        data = self._build_user_operation(
            "createMemo",
            [job_id, content, memo_type.value, is_secured, next_phase.value],
            self.config.contract_address,
        )
        return self._send_user_operation(data)

    def sign_memo(
        self, memo_id: int, is_approved: bool, reason: Optional[str] = ""
    ) -> Dict[str, Any]:
        data = self._build_user_operation(
            "signMemo", [memo_id, is_approved, reason], self.config.contract_address
        )
        return self._send_user_operation(data)

    def set_budget_with_payment_token(
        self,
        job_id: int,
        budget_base_unit: int,
        payment_token_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        token = payment_token_address or self.config.base_fare.contract_address
        data = self._build_user_operation(
            "setBudgetWithPaymentToken", [job_id, budget_base_unit, token]
        )
        return self._send_user_operation(data)

    def wrap_eth(self, amount_base_unit: int) -> Dict[str, Any]:
        weth_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.config.base_fare.contract_address),
            abi=WETH_ABI,
        )
        # Build a user operation (single call)
        trx_data = self._build_user_operation(
            method_name="deposit",
            args=[],
            contract_address=weth_contract.address,
            abi=WETH_ABI,
        )

        # Add ETH value to send along with the deposit
        trx_data[0]["value"] = amount_base_unit

        # Send the user operation through Alchemy/Session key client
        return self._send_user_operation(trx_data)
