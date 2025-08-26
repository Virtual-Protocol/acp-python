# virtuals_acp/base_contract_manager.py
"""
Abstract base class for ACP Contract Managers.
Defines the interface that all implementations (Alchemy, Privy, etc.) must follow.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, Optional, Union
from web3 import Web3

# Import the enums directly for type hints
from virtuals_acp.models import ACPJobPhase, MemoType, FeeType


class BaseACPContractManager(ABC):
    """
    Abstract base class for ACP Contract Manager implementations.
    
    All implementations (Alchemy, Privy, etc.) must implement these methods
    with the exact same signatures to ensure interoperability.
    
    NOTE: Some implementations may have additional helper methods not defined here.
    For example, ACPContractManagerV2 has an execute_transaction() method for
    frontend signing flow, which is not part of this base interface.
    """
    
    def __init__(
        self,
        web3_client: Web3,
        agent_wallet_address: str,
        entity_id: int,
        config: Any
    ):
        """Initialize the contract manager."""
        self.w3 = web3_client
        self.agent_wallet_address = agent_wallet_address
        self.entity_id = entity_id
        self.config = config
    
    @abstractmethod
    def create_job(
        self,
        provider_address: str,
        evaluator_address: str,
        expired_at: datetime
    ) -> Union[str, Dict[str, Any]]:
        """
        Create a new job on the blockchain.
        
        Args:
            provider_address: Address of the job provider
            evaluator_address: Address of the job evaluator
            expired_at: Job expiration datetime
            
        Returns:
            V1 (Alchemy): Transaction hash (str)
            V2 (Privy): Transaction data (Dict[str, Any]) for backend execution
        """
        pass
    
    @abstractmethod
    def approve_allowance(self, amount: float) -> Dict[str, Any]:
        """
        Approve token allowance for the contract.
        
        Args:
            amount: Amount to approve
            
        Returns:
            V1 (Alchemy): Transaction result with hash and receipt
            V2 (Privy): Transaction data for backend execution
        """
        pass
    
    @abstractmethod
    def create_memo(
        self,
        job_id: int,
        content: str,
        memo_type: MemoType,
        is_secured: bool,
        next_phase: ACPJobPhase
    ) -> Dict[str, Any]:
        """
        Create a memo for a job.
        
        Args:
            job_id: ID of the job
            content: Memo content
            memo_type: Type of memo
            is_secured: Whether memo is secured
            next_phase: Next phase of the job
            
        Returns:
            Transaction result
        """
        pass
    
    @abstractmethod
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
        """
        Create a payable memo for a job.
        
        Args:
            job_id: ID of the job
            content: Memo content
            amount: Payment amount
            receiver_address: Payment receiver
            fee_amount: Fee amount
            fee_type: Type of fee
            next_phase: Next phase
            memo_type: Type of memo
            expired_at: Expiration datetime
            token: Optional token address
            
        Returns:
            Transaction result
        """
        pass
    
    @abstractmethod
    def sign_memo(
        self,
        memo_id: int,
        is_approved: bool,
        reason: Optional[str] = ""
    ) -> Dict[str, Any]:
        """
        Sign a memo (approve or reject).
        
        Args:
            memo_id: ID of the memo
            is_approved: Whether to approve
            reason: Reason for decision
            
        Returns:
            Transaction result
        """
        pass
    
    @abstractmethod
    def set_budget(self, job_id: int, budget: float) -> Dict[str, Any]:
        """
        Set budget for a job.
        
        Args:
            job_id: ID of the job
            budget: Budget amount
            
        Returns:
            Transaction result
        """
        pass
    
    @abstractmethod
    def set_budget_with_payment_token(
        self,
        job_id: int,
        budget: float,
        payment_token_address: str = None
    ) -> Dict[str, Any]:
        """
        Set budget with specific payment token.
        
        Args:
            job_id: ID of the job
            budget: Budget amount
            payment_token: Token address
            
        Returns:
            Transaction result
        """
        pass
    
    @abstractmethod
    def validate_transaction(self, hash_value: str) -> Dict[str, Any]:
        """
        Validate a transaction by its hash.
        
        Args:
            hash_value: Transaction hash
            
        Returns:
            Transaction details
        """
        pass
    
    def _format_amount(self, amount: float) -> int:
        """
        Helper method to format amounts for blockchain.
        
        Args:
            amount: Amount as float
            
        Returns:
            Amount as integer (with decimals)
        """
        from decimal import Decimal
        amount_decimal = Decimal(str(amount))
        return int(amount_decimal * (10 ** self.config.payment_token_decimals))