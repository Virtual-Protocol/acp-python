# virtuals_acp/contract_managerV2.py
"""
Contract Manager V2 - Frontend-signed authorization only.

This version requires frontend-generated authorization signatures.
No private keys are handled by the backend - all signing happens on the frontend.
Transactions are prepared by the backend and relayed through Privy with gas sponsorship.
"""

import math
import time
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, Tuple

from web3 import Web3
from web3.contract import Contract

from virtuals_acp.abi import ACP_ABI, ERC20_ABI
from virtuals_acp.base_contract_manager import BaseACPContractManager
from virtuals_acp.configs import ACPContractConfig
from virtuals_acp.models import ACPJobPhase, MemoType, FeeType


class ACPContractManagerV2(BaseACPContractManager):
    """
    Contract Manager V2 - Pure transaction preparation.
    
    This implementation only prepares transaction data for external execution.
    No transaction execution or HTTP calls are performed by this class.
    
    Backend applications must handle transaction execution separately
    using their own Privy client or similar service.
    """
    
    def __init__(
            self,
            web3_client: Web3,
            agent_wallet_address: str,
            entity_id: int,
            config: ACPContractConfig
    ):
        """
        Initialize contract manager for transaction preparation.
        
        Args:
            web3_client: Web3 instance for encoding transactions
            agent_wallet_address: The agent's wallet address
            entity_id: Entity ID for the agent
            config: Configuration with contract addresses
        """
        super().__init__(web3_client, agent_wallet_address, entity_id, config)
        
        # Initialize contract interfaces for encoding
        self.contract: Contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(config.contract_address), 
            abi=ACP_ABI
        )
        self.token_contract: Contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(config.payment_token_address), 
            abi=ERC20_ABI
        )

    def _format_amount(self, amount: float) -> int:
        """Convert float amount to token units."""
        amount_decimal = Decimal(str(amount))
        return int(amount_decimal * (10 ** self.config.payment_token_decimals))
    
    def _prepare_transaction(
        self, 
        method_name: str, 
        args: list, 
        contract_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Prepare transaction data for client signing.
        
        Args:
            method_name: Contract method name
            args: Method arguments
            contract_address: Optional contract address (for token operations)
        
        Returns:
            Transaction data dict with 'to', 'data', 'value' fields
        """
        if contract_address:
            encoded_data = self.token_contract.encode_abi(method_name, args=args)
        else:
            encoded_data = self.contract.encode_abi(method_name, args=args)
        
        return {
            "to": contract_address if contract_address else self.config.contract_address,
            "data": encoded_data,
            "value": "0x0"  # Most contract calls don't send ETH
        }
    
    
    # ===== Main Interface Methods (Implementing BaseACPContractManager) =====
    
    def create_job(
        self,
        provider_address: str,
        evaluator_address: str,
        expired_at: datetime
    ) -> Dict[str, Any]:
        """Create a new job on the blockchain (V2: prepares transaction data)."""
        provider_address = Web3.to_checksum_address(provider_address)
        evaluator_address = Web3.to_checksum_address(evaluator_address)
        expire_timestamp = int(expired_at.timestamp())
        
        # For V2, return transaction data directly for backend execution
        return self._prepare_transaction(
            "createJob",
            [provider_address, evaluator_address, expire_timestamp]
        )
    
    def approve_allowance(self, amount: float) -> Dict[str, Any]:
        """Approve token allowance for the contract (V2: prepares transaction data)."""
        return self._prepare_transaction(
            "approve",
            [self.config.contract_address, self._format_amount(amount)],
            self.config.payment_token_address
        )
    
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
        """Create a payable memo for a job (V2: prepares transaction data)."""
        receiver_address = Web3.to_checksum_address(receiver_address)
        token = self.config.payment_token_address if token is None else token
        
        return self._prepare_transaction(
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
    
    def create_memo(
        self,
        job_id: int,
        content: str,
        memo_type: MemoType,
        is_secured: bool,
        next_phase: ACPJobPhase
    ) -> Dict[str, Any]:
        """Create a memo for a job (V2: prepares transaction data)."""
        return self._prepare_transaction(
            "createMemo",
            [job_id, content, memo_type.value, is_secured, next_phase.value]
        )
    
    def sign_memo(
        self,
        memo_id: int,
        is_approved: bool,
        reason: Optional[str] = ""
    ) -> Dict[str, Any]:
        """Sign a memo (approve or reject) (V2: prepares transaction data)."""
        return self._prepare_transaction(
            "signMemo",
            [memo_id, is_approved, reason]
        )
    
    def set_budget(self, job_id: int, budget: float) -> Dict[str, Any]:
        """Set budget for a job (V2: prepares transaction data)."""
        return self._prepare_transaction(
            "setBudget",
            [job_id, self._format_amount(budget)]
        )
    
    def set_budget_with_payment_token(
        self,
        job_id: int,
        budget: float,
        payment_token_address: str = None
    ) -> Dict[str, Any]:
        """Set budget with specific payment token (V2: prepares transaction data)."""
        if payment_token_address is None:
            payment_token_address = self.config.payment_token_address
        
        return self._prepare_transaction(
            "setBudgetWithPaymentToken",
            [job_id, self._format_amount(budget), payment_token_address]
        )
    
    def validate_transaction(self, hash_value: str) -> Dict[str, Any]:
        """Validate a transaction by its hash."""
        try:
            receipt = self.w3.eth.wait_for_transaction_receipt(hash_value)
            return {
                "status": 200 if receipt.status == 1 else 500,
                "hash": hash_value,
                "receipt": receipt
            }
        except Exception as e:
            raise Exception(f"Failed to validate transaction {hash_value}: {e}")
