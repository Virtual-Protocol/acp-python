from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING, List, Optional, Dict, Any, Union

from pydantic import BaseModel, Field, ConfigDict

from virtuals_acp.account import ACPAccount
from virtuals_acp.memo import ACPMemo
from virtuals_acp.models import (NegotiationPayload, ACPMemoStatus)
from virtuals_acp.utils import try_parse_json_model, prepare_payload
from virtuals_acp.models import (
    ACPJobPhase,
    MemoType,
    IACPAgent,
    DeliverablePayload,
    FeeType
)
from virtuals_acp.fare import Fare, FareAmountBase, FareAmount

if TYPE_CHECKING:
    from virtuals_acp.client import VirtualsACP


class ACPJob(BaseModel):
    acp_client: "VirtualsACP"
    id: int
    provider_address: str
    client_address: str
    evaluator_address: str
    contract_address: Optional[str] = None
    price: float
    price_token_address: Optional[str] = None
    memos: List[ACPMemo] = Field(default_factory=list)
    phase: ACPJobPhase
    context: Dict[str, Any] | None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    _base_fare: Optional[Fare] = None
    _name: Optional[str] = None
    _requirement: Optional[Union[str, Dict[str, Any]]] = None

    def model_post_init(self, __context: Any) -> None:
        if self.acp_client:
            self._base_fare = self.acp_client.config.base_fare

        memo = next(
            (
                m
                for m in self.memos
                if ACPJobPhase(m.next_phase) == ACPJobPhase.NEGOTIATION
            ),
            None,
        )

        if not memo:
            return None

        if not memo.content:
            return None

        content_obj = try_parse_json_model(memo.content, NegotiationPayload)
        if content_obj:
            self._requirement = (
                content_obj.service_requirement or content_obj.requirement
            )
            self._name = content_obj.service_name or content_obj.name

    @property
    def requirement(self) -> Optional[Union[str, Dict[str, Any]]]:
        return self._requirement

    @property
    def name(self) -> Optional[str]:
        return self._name

    def __str__(self):
        return (
            f"AcpJob(\n"
            f"  id={self.id},\n"
            f"  provider_address='{self.provider_address}',\n"
            f"  client_address='{self.client_address}',\n"
            f"  evaluator_address='{self.evaluator_address}',\n"
            f"  contract_address='{self.contract_address}',\n"
            f"  price={self.price},\n"
            f"  price_token_address='{self.price_token_address}',\n"
            f"  memos=[{', '.join(str(memo) for memo in self.memos)}],\n"
            f"  phase={self.phase}\n"
            f"  context={self.context}\n"
            f")"
        )

    @property
    def acp_contract_client(self):
        if not self.contract_address:
            return self.acp_client.contract_client
        return self.acp_client.contract_client_by_address(self.contract_address)

    @property
    def config(self):
        return self.acp_contract_client.config

    @property
    def base_fare(self) -> Fare:
        return self.acp_contract_client.config.base_fare

    @property
    def account(self) -> Optional[ACPAccount]:
        return self.acp_client.get_account_by_job_id(self.id, self.acp_contract_client)

    @property
    def deliverable(self) -> Optional[str]:
        """Get the deliverable from the completed memo"""
        memo = next(
            (
                m
                for m in self.memos
                if ACPJobPhase(m.next_phase) == ACPJobPhase.COMPLETED
            ),
            None,
        )
        return memo.content if memo else None

    @property
    def rejection_reason(self) -> Optional[str]:
        """Get the rejection reason from the rejected memo"""
        request_memo = next(
            (
                m
                for m in self.memos
                if m.next_phase == ACPJobPhase.NEGOTIATION and m.status == ACPMemoStatus.REJECTED
            ),
            None
        )
        if request_memo:
            return request_memo.signed_reason

        fallback_memo = next(
            (m for m in self.memos if m.next_phase == ACPJobPhase.REJECTED),
            None
        )
        return fallback_memo.content if fallback_memo else None

    def create_requirement(self, content: str) -> str:
        result = self.acp_contract_client.create_memo(
            self.id,
            content,
            MemoType.MESSAGE,
            False,
            ACPJobPhase.TRANSACTION,
        )

        tx_hash = result.get("receipts", [])[0].get("transactionHash")
        return tx_hash

    def create_payable_requirement(
        self,
        content: str,
        type: MemoType,
        amount: FareAmountBase,
        recipient: str,
        expired_at: Optional[datetime] = None,
    ) -> str:
        if expired_at is None:
            expired_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        if (
            type == MemoType.PAYABLE_TRANSFER_ESCROW
            or type == MemoType.PAYABLE_TRANSFER
        ):
            self.acp_contract_client.approve_allowance(
                amount.amount,
                amount.fare.contract_address,
            )

        fee_amount = FareAmount(0, self.base_fare)

        result = self.acp_contract_client.create_payable_memo(
            self.id,
            content,
            amount.amount,
            recipient,
            fee_amount.amount,
            FeeType.NO_FEE,
            ACPJobPhase.TRANSACTION,
            type,
            expired_at,
            amount.fare.contract_address,
        )

        tx_hash = result.get("receipts", [])[0].get("transactionHash")
        return tx_hash

    def pay_and_accept_requirement(self, reason: Optional[str] = "") -> str:
        memo = next(
            (m for m in self.memos if m.next_phase == ACPJobPhase.TRANSACTION), None
        )

        if not memo:
            raise Exception("No transaction memo found")

        base_fare_amount = FareAmount(self.price, self.base_fare)

        if memo.payable_details:
            transfer_amount = FareAmountBase.from_contract_address(
                memo.payable_details["amount"],
                memo.payable_details["token"],
                self.config,
            )
        else:
            transfer_amount = FareAmount(0, self.base_fare)

        # merge amounts if same token
        if (
            base_fare_amount.fare.contract_address
            == transfer_amount.fare.contract_address
        ):
            total_amount = base_fare_amount.add(transfer_amount)
        else:
            total_amount = base_fare_amount

        # approve base fare
        self.acp_contract_client.approve_allowance(
            total_amount.amount,
            self.base_fare.contract_address,
        )

        # approve transfer if token differs
        if (
            base_fare_amount.fare.contract_address
            != transfer_amount.fare.contract_address
        ):
            self.acp_contract_client.approve_allowance(
                transfer_amount.amount,
                transfer_amount.fare.contract_address,
            )

        # sign memo
        memo.sign(True, reason)

        result = self.acp_contract_client.create_memo(
            self.id,
            f"Payment made. {reason or ''}".strip(),
            MemoType.MESSAGE,
            True,
            ACPJobPhase.EVALUATION,
        )

        tx_hash = result.get("receipts", [])[0].get("transactionHash")
        return tx_hash

    def accept(self, reason: Optional[str] = None) -> str:
        memo_content = f"Job {self.id} accepted. {reason or ''}"
        if (
            self.latest_memo is None
            or self.latest_memo.next_phase != ACPJobPhase.NEGOTIATION
        ):
            raise ValueError("No request memo found")
        memo = self.latest_memo

        result = memo.sign(True, memo_content)
        tx_hash = result.get("receipts", [])[0].get("transactionHash")
        return tx_hash

    def reject(self, reason: Optional[str] = None):
        memo_content = f"Job {self.id} rejected. {reason or ''}"
        if self.phase is ACPJobPhase.REQUEST:
            if self.latest_memo is None or self.latest_memo.next_phase != ACPJobPhase.NEGOTIATION:
                raise ValueError("No request memo found")

            memo = self.latest_memo
            result = self.acp_contract_client.sign_memo(
                memo.id,
                False,
                memo_content
            )
            tx_hash = result.get("receipts", [])[0].get("transactionHash")
            return tx_hash

        result = self.acp_contract_client.create_memo(
            self.id,
            memo_content,
            MemoType.MESSAGE,
            True,
            ACPJobPhase.REJECTED
        )
        tx_hash = result.get("receipts", [])[0].get("transactionHash")
        return tx_hash

    def respond(
            self,
            accept: bool,
            reason: Optional[str] = None,
    ) -> str:
        memo_content = f"Job {self.id} {'accepted' if accept else 'rejected'}. {reason or ''}"
        if accept:
            self.accept(memo_content)
            return self.create_requirement(memo_content)

        return self.reject(memo_content)

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

    @property
    def latest_memo(self) -> Optional[ACPMemo]:
        """Get the latest memo in the job"""
        return self.memos[-1] if self.memos else None

    def _get_memo_by_id(self, memo_id):
        return next((m for m in self.memos if m.id == memo_id), None)

    def deliver(self, deliverable: DeliverablePayload):
        if (
            self.latest_memo is None
            or self.latest_memo.next_phase != ACPJobPhase.EVALUATION
        ):
            raise ValueError("No transaction memo found")

        return self.acp_contract_client.create_memo(
            self.id,
            prepare_payload(deliverable),
            MemoType.MESSAGE,
            True,
            ACPJobPhase.COMPLETED
        )

    def deliver_payable(
        self,
        deliverable: DeliverablePayload,
        amount: FareAmountBase,
        expired_at: Optional[datetime] = None,
    ):
        if expired_at is None:
            expired_at = datetime.now(timezone.utc) + timedelta(minutes=5)

        if (
            self.latest_memo is None
            or self.latest_memo.next_phase != ACPJobPhase.EVALUATION
        ):
            raise ValueError("No transaction memo found")

        self.acp_contract_client.approve_allowance(
            amount.amount,
            amount.fare.contract_address
        )

        fee_amount = FareAmount(0, self.acp_contract_client.config.base_fare)

        return self.acp_contract_client.create_payable_memo(
            job_id=self.id,
            content=prepare_payload(deliverable),
            amount_base_unit=amount.amount,
            recipient=self.client_address,
            fee_amount_base_unit=fee_amount.amount,
            fee_type=FeeType.NO_FEE,
            next_phase=ACPJobPhase.COMPLETED,
            memo_type=MemoType.PAYABLE_TRANSFER,
            expired_at=expired_at,
            token=amount.fare.contract_address
        )

    def evaluate(self, accept: bool, reason: Optional[str] = None):
        if (
            self.latest_memo is None
            or self.latest_memo.next_phase != ACPJobPhase.COMPLETED
        ):
            raise ValueError("No evaluation memo found")

        if not reason:
            reason = f"Job {self.id} delivery {'accepted' if accept else 'rejected'}"

        return self.acp_client.sign_memo(self.latest_memo.id, accept, reason)

    def create_notification(self, content: str):
        return self.acp_contract_client.create_memo(
            job_id=self.id,
            content=content,
            memo_type=MemoType.NOTIFICATION,
            is_secured=True,
            next_phase=ACPJobPhase.COMPLETED,
        )

    def create_payable_notification(
        self,
        content: str,
        amount: FareAmountBase,
        expired_at: Optional[datetime] = None,
    ):
        if expired_at is None:
            expired_at = datetime.now(timezone.utc) + timedelta(minutes=5)

        self.acp_contract_client.approve_allowance(
            amount.amount,
            amount.fare.contract_address
        )

        fee_amount = FareAmount(0, self.acp_contract_client.config.base_fare)

        return self.acp_contract_client.create_payable_memo(
            job_id=self.id,
            content=content,
            amount_base_unit=amount.amount,
            recipient=self.client_address,
            fee_amount_base_unit=fee_amount.amount,
            fee_type=FeeType.NO_FEE,
            next_phase=ACPJobPhase.COMPLETED,
            memo_type=MemoType.PAYABLE_NOTIFICATION,
            expired_at=expired_at,
            token=amount.fare.contract_address
        )
