from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
import math
from typing import Dict, Any, Optional, List

from web3 import Web3
from web3.contract import Contract
from eth_utils.abi import event_abi_to_log_topic

from virtuals_acp.abis.abi import ACP_ABI
from virtuals_acp.abis.weth_abi import WETH_ABI
from virtuals_acp.configs.configs import ACPContractConfig
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
            (e for e in ACP_ABI if e.get("type") == "event" and e.get("name") == "JobCreated"),
            None,
        )
        self.job_created_signature = "0x" + event_abi_to_log_topic(job_created_event_abi).hex()

    def _build_user_operation(
        self, method_name: str, args: List[Any], contract_address: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        encoded_data = (
            self.token_contract.encode_abi(method_name, args=args)
            if contract_address
            else self.contract.encode_abi(method_name, args=args)
        )

        trx_data = [
            {
                "to": contract_address or self.config.contract_address,
                "data": encoded_data,
            }
        ]
        return trx_data

    @abstractmethod
    def _send_user_operation(self, trx_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        pass

    def get_job_id(
        self, response: Dict[str, Any], client_address: str, provider_address: str
    ) -> int:
        logs: List[Dict[str, Any]] = response.get("receipts", [])[0].get("logs", [])

        decoded_create_job_logs = [
            self.contract.events.JobCreated().process_log(
                {
                    "topics": log["topics"],
                    "data": log["data"],
                    "address": log["address"],
                    "logIndex": 0,
                    "transactionIndex": 0,
                    "transactionHash": "0x0000",
                    "blockHash": "0x0000",
                    "blockNumber": 0,
                }
            )
            for log in logs
            if log["topics"][0] == self.job_created_event_signature_hex
        ]

        if len(decoded_create_job_logs) == 0:
            raise Exception("No logs found for JobCreated event")

        created_job_log = next(
            (
                log
                for log in decoded_create_job_logs
                if log["args"]["provider"] == provider_address
                and log["args"]["client"] == client_address
            ),
            None,
        )

        if not created_job_log:
            raise Exception(
                "No logs found for JobCreated event with provider and client addresses"
            )

        return int(created_job_log["args"]["jobId"])

    def _format_amount(self, amount: float) -> int:
        return int(Decimal(str(amount)) * (10 ** self.config.base_fare.decimals))

    def create_job(
        self,
        provider_address: str,
        evaluator_address: str,
        expired_at: datetime,
        payment_token_address: str,
        budget_base_unit: int,
        metadata: str
    ) -> Dict[str, Any]:
        data = self.contract.encode_abi(
            "createJob",
            [
                Web3.to_checksum_address(provider_address),
                Web3.to_checksum_address(evaluator_address),
                math.floor(expired_at.timestamp()),
                payment_token_address,
                budget_base_unit,
                metadata
            ],
        )
        return self._send_user_operation(data, self.config.contract_address)

    def create_job_with_account(
        self,
        account_id: int,
        provider_address: str,
        evaluator_address: str,
        budget_base_unit: int,
        payment_token_address: str,
        expired_at: datetime,
    ) -> Dict[str, Any]:
        data = self.contract.encode_abi(
            "createJobWithAccount",
            [
                account_id,
                Web3.to_checksum_address(provider_address),
                Web3.to_checksum_address(evaluator_address),
                budget_base_unit,
                Web3.to_checksum_address(payment_token_address),
                math.floor(expired_at.timestamp()),
            ],
        )
        return self._send_user_operation(data, self.config.contract_address)

    def approve_allowance(
        self,
        amount_base_unit: int,
        payment_token_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        token = payment_token_address or self.config.base_fare.contract_address
        data = self.token_contract.encode_abi(
            "approve",
            [self.config.contract_address, amount_base_unit],
        )
        return self._send_user_operation(data, token)

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
        data = self.contract.encode_abi(
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
        )
        return self.handle_operation(data, self.config.contract_address)

    def create_memo(
        self,
        job_id: int,
        content: str,
        memo_type: MemoType,
        is_secured: bool,
        next_phase: ACPJobPhase,
    ) -> Dict[str, Any]:
        data = self.contract.encode_abi(
            "createMemo",
            [job_id, content, memo_type.value, is_secured, next_phase.value],
        )
        return self.handle_operation(data, self.config.contract_address)

    def sign_memo(
        self, memo_id: int, is_approved: bool, reason: Optional[str] = ""
    ) -> Dict[str, Any]:
        data = self.contract.encode_abi("signMemo", [memo_id, is_approved, reason])
        return self.handle_operation(data, self.config.contract_address)

    def set_budget_with_payment_token(
        self, job_id: int, budget_base_unit: int, payment_token_address: Optional[str] = None
    ) -> Dict[str, Any]:
        token = payment_token_address or self.config.base_fare.contract_address
        data = self.contract.encode_abi(
            "setBudgetWithPaymentToken",
            [job_id, budget_base_unit, token],
        )
        return self.handle_operation(data, self.config.contract_address)

    def wrap_eth(self, amount_base_unit: int) -> Dict[str, Any]:
        weth_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.config.base_fare.contract_address),
            abi=WETH_ABI,
        )
        data = weth_contract.encode_abi("deposit", [])
        return self.handle_operation(data, weth_contract.address, value=amount_base_unit)
