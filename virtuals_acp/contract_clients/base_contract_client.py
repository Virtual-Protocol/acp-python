from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
import math
from typing import Dict, Any, Optional, List, cast

from eth_typing import ABIEvent
import requests
from web3 import Web3
from web3.contract import Contract
from eth_utils.abi import event_abi_to_log_topic

from virtuals_acp.abis.erc20_abi import ERC20_ABI
from virtuals_acp.abis.weth_abi import WETH_ABI
from virtuals_acp.configs.configs import ACPContractConfig
from virtuals_acp.exceptions import ACPError
from virtuals_acp.models import ACPJobPhase, MemoType, FeeType, AcpJobX402PaymentDetails,X402PayableRequest,X402Payment,X402PayableRequirements, OperationPayload


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
    ) -> Dict[str, Any]:
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

        return {"to": target_address, "data": encoded_data}

    @abstractmethod
    def handle_operation(self, trx_data: List[OperationPayload]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_job_id(
        self, receipt: Dict[str, Any], client_address: str, provider_address: str
    ) -> int:
        """Abstract method to retrieve a job ID from a transaction hash and related addresses."""
        pass

    def _format_amount(self, amount: float) -> int:
        return int(Decimal(str(amount)) * (10**self.config.base_fare.decimals))

    def update_account_metadata(self, account_id: int, metadata: str) -> OperationPayload:
        operation = self._build_user_operation(
            "updateAccountMetadata",
            [account_id, metadata],
            self.config.contract_address,
        )

        return OperationPayload(
            data=operation["data"],
            to=operation['to'],
        )

    def create_job(
        self,
        provider_address: str,
        evaluator_address: str,
        expired_at: datetime,
        payment_token_address: str,
        budget_base_unit: int,
        metadata: str,
    ) -> OperationPayload:
        operation = self._build_user_operation(
            "createJob",
            [
                Web3.to_checksum_address(provider_address),
                Web3.to_checksum_address(evaluator_address),
                math.floor(expired_at.timestamp()),
                payment_token_address,
                budget_base_unit,
                metadata,
            ],
            self.config.contract_address,
        )

        return OperationPayload(
            data=operation["data"],
            to=operation['to'],
        )

    def create_job_with_account(
        self,
        account_id: int,
        evaluator_address: str,
        budget_base_unit: int,
        payment_token_address: str,
        expired_at: datetime,
    ) -> OperationPayload:
        operation = self._build_user_operation(
            "createJobWithAccount",
            [
                account_id,
                Web3.to_checksum_address(evaluator_address),
                budget_base_unit,
                Web3.to_checksum_address(payment_token_address),
                math.floor(expired_at.timestamp()),
            ],
        )
        
        return OperationPayload(
            data=operation["data"],
            to=operation['to'],
        )

    def approve_allowance(
        self,
        amount_base_unit: int,
        payment_token_address: Optional[str] = None,
    ) -> OperationPayload:
        operation = self._build_user_operation(
            "approve",
            [self.config.contract_address, amount_base_unit],
            contract_address=payment_token_address,
            abi=ERC20_ABI,
        )
        
        return OperationPayload(
            data=operation["data"],
            to=operation['to'],
        )

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
    ) -> OperationPayload:
        operation = self._build_user_operation(
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
        
        return OperationPayload(
            data=operation["data"],
            to=operation['to'],
        )

    def create_memo(
        self,
        job_id: int,
        content: str,
        memo_type: MemoType,
        is_secured: bool,
        next_phase: ACPJobPhase,
    ) -> OperationPayload:
        operation = self._build_user_operation(
            "createMemo",
            [job_id, content, memo_type.value, is_secured, next_phase.value],
            self.config.contract_address,
        )
        
        return OperationPayload(
            data=operation["data"],
            to=operation['to'],
        )

    def sign_memo(
        self, memo_id: int, is_approved: bool, reason: Optional[str] = ""
    ) -> OperationPayload:
        operation = self._build_user_operation(
            "signMemo", [memo_id, is_approved, reason], self.config.contract_address
        )

        return OperationPayload(
            data=operation["data"],
            to=operation['to'],
        )

    def set_budget_with_payment_token(
        self,
        job_id: int,
        budget_base_unit: int,
        payment_token_address: Optional[str] = None,
    ) -> OperationPayload | None:
        return None

    def wrap_eth(self, amount_base_unit: int) -> OperationPayload:
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
        
        operation = OperationPayload(
            data=trx_data["data"],
            to=trx_data["to"],
            value=amount_base_unit,
        )
        
        return operation
    
    def create_job_with_x402(
        self,
        provider_address: str,
        evaluator_address: str,
        expired_at: datetime,
        payment_token_address: str,
        budget_base_unit: int,
        metadata: str,
    ) -> OperationPayload:
        """
        Build the payload for createJobWithX402 operation.
        """
        try:
            # Convert datetime to Unix timestamp
            expired_at_timestamp = int(expired_at.timestamp())
            operation = self._build_user_operation(
                "createJobWithX402",
                [
                    Web3.to_checksum_address(provider_address),
                    Web3.to_checksum_address(evaluator_address),
                    expired_at_timestamp,
                    Web3.to_checksum_address(payment_token_address),
                    budget_base_unit,
                    metadata,
                ],
            )
            
            operation = OperationPayload(
                data=operation["data"],
                to=operation["to"],
            )
            
            return operation
        except Exception as e:
            raise ACPError("Failed to create job", e)
        
    def get_x402_payment_details(self, job_id: int) -> AcpJobX402PaymentDetails:
        """Get X402 payment details for a job."""
        try:
            x402_config = self.config.x402_config
            if not x402_config or not getattr(x402_config, 'url', None):
                return AcpJobX402PaymentDetails(
                    is_x402=False,
                    is_budget_received=False
            )
            
            # Call the contract function
            result = self.contract.functions.x402PaymentDetails(job_id).call()
            
            return AcpJobX402PaymentDetails(
                is_x402=result[0],
                is_budget_received=result[1]
            )
        except Exception as e:
            raise ACPError("Failed to get X402 payment details", e)
    
    def update_job_x402_nonce(self, job_id: int, nonce: str) -> Dict[str, Any]:
        raise NotImplementedError("update_job_x402_nonce is not implemented.")
    
    def generate_x402_payment(self, payable_request: X402PayableRequest, requirements: X402PayableRequirements) -> X402Payment:
        raise NotImplementedError("generate_x402_payment is not implemented.")
    
    def perform_x402_request(self, url: str, budget: Optional[str] = None, signature: Optional[str] = None) -> dict:
        base_url = self.config.x402_config.url if self.config.x402_config else None

        if not base_url:
            raise ACPError("X402 URL not configured")

        headers = {}
        if signature:
            headers["x-payment"] = signature
        if budget:
            headers["x-budget"] = budget

        try:
            response = requests.get(f"{base_url}{url}", headers=headers)
            if response.status_code == 402:
                try:
                    data = response.json()
                except Exception:
                    data = {}
                return {
                    "isPaymentRequired": True,
                    "data": data
                }
            else:
                response.raise_for_status()
                data = response.json()
                return {
                    "isPaymentRequired": False,
                    "data": data
                }
        except Exception as e:
            raise ACPError("Failed to perform X402 request", e)

