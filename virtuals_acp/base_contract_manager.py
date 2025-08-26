
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, Optional, Union
from web3 import Web3
from virtuals_acp.models import ACPJobPhase, MemoType, FeeType


class BaseACPContractManager(ABC):
    
    def __init__(
        self,
        web3_client: Web3,
        agent_wallet_address: str,
        entity_id: int,
        config: Any
    ):
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
        pass
    
    @abstractmethod
    def approve_allowance(self, amount: float) -> Dict[str, Any]:
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
        pass
    
    @abstractmethod
    def sign_memo(
        self,
        memo_id: int,
        is_approved: bool,
        reason: Optional[str] = ""
    ) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def set_budget(self, job_id: int, budget: float) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def set_budget_with_payment_token(
        self,
        job_id: int,
        budget: float,
        payment_token_address: str = None
    ) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def validate_transaction(self, hash_value: str) -> Dict[str, Any]:
        pass
    
    def _format_amount(self, amount: float) -> int:
        from decimal import Decimal
        amount_decimal = Decimal(str(amount))
        return int(amount_decimal * (10 ** self.config.payment_token_decimals))