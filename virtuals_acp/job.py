from typing import TYPE_CHECKING, List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from virtuals_acp.memo import ACPMemo
from virtuals_acp.models import ACPJobPhase, IACPAgent

if TYPE_CHECKING:
    from virtuals_acp.client import VirtualsACP

class ACPJob(BaseModel):
    id: int
    provider_address: str
    client_address: str
    evaluator_address: str
    price: float
    acp_client: "VirtualsACP"
    memos: List[ACPMemo] = Field(default_factory=list)
    phase: ACPJobPhase
    context: Dict[str, Any] | None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __str__(self):
        return (
            f"AcpJob(\n"
            f"  id={self.id},\n"
            f"  provider_address='{self.provider_address}',\n"
            f"  memos=[{', '.join(str(memo) for memo in self.memos)}],\n"
            f"  phase={self.phase}\n"
            f"  context={self.context}\n"
            f")"
        )
        
    @property
    def service_requirement(self) -> Optional[str]:
        """Get the service requirement from the negotiation memo"""
        memo = next(
            (m for m in self.memos if ACPJobPhase(m.next_phase) == ACPJobPhase.NEGOTIATION),
            None
        )
        return memo.content if memo else None

    @property 
    def deliverable(self) -> Optional[str]:
        """Get the deliverable from the completed memo"""
        memo = next(
            (m for m in self.memos if ACPJobPhase(m.next_phase) == ACPJobPhase.COMPLETED),
            None
        )
        return memo.content if memo else None

    @property
    def provider_agent(self) -> Optional["IACPAgent"]:
        """Get the provider agent details"""
        return self.acp_client.get_agent(self.provider_address)

    @property
    def client_agent(self) -> Optional["IACPAgent"]:
        """Get the client agent details"""
        return self.acp_client.get_agent(self.client_address)

    @property
    def evaluator_agent(self) -> Optional["IACPAgent"]:
        """Get the evaluator agent details"""
        return self.acp_client.get_agent(self.evaluator_address)
    
    
    def pay(self, amount: int, reason: Optional[str] = None):
        memo = next(
            (m for m in self.memos if ACPJobPhase(m.next_phase) == ACPJobPhase.TRANSACTION),
            None
        )
        
        if not memo:
            raise ValueError("No transaction memo found")
        
        if not reason:
            reason = f"Job {self.id} paid."
            
        return self.acp_client.pay_for_job(self.id, memo.id, amount, reason)

    def respond(self, accept: bool, reason: Optional[str] = None):
        memo = next(
            (m for m in self.memos if ACPJobPhase(m.next_phase) == ACPJobPhase.NEGOTIATION), 
            None
        )
        
        if not memo:
            raise ValueError("No negotiation memo found")
            
        if not reason:
            reason = f"Job {self.id} {'accepted' if accept else 'rejected'}."
            
        return self.acp_client.respond_to_job_memo(self.id, memo.id, accept, reason)

    def deliver(self, deliverable: str):
        memo = next(
            (m for m in self.memos if ACPJobPhase(m.next_phase) == ACPJobPhase.EVALUATION),
            None
        )
        
        if not memo:
            raise ValueError("No evaluation memo found")
            
        return self.acp_client.submit_job_deliverable(self.id, deliverable)

    def evaluate(self, accept: bool, reason: Optional[str] = None):
        memo = next(
            (m for m in self.memos if ACPJobPhase(m.next_phase) == ACPJobPhase.COMPLETED),
            None
        )
        
        if not memo:
            raise ValueError("No evaluation memo found")
            
        if not reason:
            reason = f"Job {self.id} delivery {'accepted' if accept else 'rejected'}."
            
        return self.acp_client.evaluate_job_delivery(memo.id, accept, reason)