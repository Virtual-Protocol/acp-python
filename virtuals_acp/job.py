from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING, List, Optional, Dict, Any

from pydantic import BaseModel, Field, ConfigDict

from virtuals_acp.memo import ACPMemo
from virtuals_acp.models import (
    ACPJobPhase,
    IACPAgent,
    IDeliverable,
    GenericPayload,
    OpenPositionPayload,
    PayloadType,
    ClosePositionPayload,
    PositionFulfilledPayload,
    CloseJobAndWithdrawPayload,
    FeeType,
    MemoType,
    UnfulfilledPositionPayload,
    RequestClosePositionPayload,
    NegotiationPayload,
    T,
)
from virtuals_acp.utils import try_parse_json_model

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

        if not content_obj:
            return None

        if content_obj.service_requirement:
            return content_obj.service_requirement

        return content_obj

    @property
    def service_name(self) -> Optional[str]:
        """Get the service name from the negotiation memo"""
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

        if not content_obj:
            return memo.content

        return content_obj.name

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

    def pay(self, amount: float, reason: Optional[str] = None) -> dict[str, Any]:
        memo = next(
            (
                m
                for m in self.memos
                if ACPJobPhase(m.next_phase) == ACPJobPhase.TRANSACTION
            ),
            None,
        )

        if not memo:
            raise ValueError("No transaction memo found")

        if not reason:
            reason = f"Job {self.id} paid"

        return self.acp_client.pay_job(self.id, memo.id, amount, reason)

    def respond(
        self,
        accept: bool,
        payload: Optional[GenericPayload[T]] = None,
        reason: Optional[str] = None,
    ) -> str:
        if (
            self.latest_memo is None
            or self.latest_memo.next_phase != ACPJobPhase.NEGOTIATION
        ):
            raise ValueError("No negotiation memo found")

        if not reason:
            reason = f"Job {self.id} {'accepted' if accept else 'rejected'}"

        return self.acp_client.respond_to_job(
            self.id,
            self.latest_memo.id,
            accept,
            payload.model_dump_json() if payload else None,
            reason,
        )

    def deliver(self, deliverable: IDeliverable):
        if (
            self.latest_memo is None
            or self.latest_memo.next_phase != ACPJobPhase.EVALUATION
        ):
            raise ValueError("No transaction memo found")

        return self.acp_client.deliver_job(self.id, deliverable)

    def evaluate(self, accept: bool, reason: Optional[str] = None):
        if (
            self.latest_memo is None
            or self.latest_memo.next_phase != ACPJobPhase.COMPLETED
        ):
            raise ValueError("No evaluation memo found")

        if not reason:
            reason = f"Job {self.id} delivery {'accepted' if accept else 'rejected'}"

        return self.acp_client.sign_memo(self.latest_memo.id, accept, reason)

    def open_position(
        self,
        payload: List[OpenPositionPayload],
        fee_amount: float,
        expired_at: Optional[datetime] = None,
        wallet_address: Optional[str] = None,
    ) -> str:
        if not payload:
            raise ValueError("No positions to open")

        if expired_at is None:
            expired_at = datetime.now(timezone.utc) + timedelta(minutes=3)

        total_amount = sum(p.amount for p in payload)

        open_position_payload = GenericPayload(
            type=PayloadType.OPEN_POSITION, data=payload
        )

        return self.acp_client.transfer_funds(
            self.id,
            total_amount,
            wallet_address or self.provider_address,
            fee_amount,
            FeeType.IMMEDIATE_FEE,
            open_position_payload,
            ACPJobPhase.TRANSACTION,
            expired_at,
        )

    def respond_open_position(
        self,
        memo_id: int,
        accept: bool,
        reason: Optional[str] = None,
    ):
        memo = self._get_memo_by_id(memo_id)
        if (
            memo is None
            or memo.next_phase != ACPJobPhase.TRANSACTION
            or memo.type != MemoType.PAYABLE_TRANSFER_ESCROW
        ):
            raise ValueError("No open position memo found")

        open_position_payload = try_parse_json_model(
            memo.content, GenericPayload[OpenPositionPayload]
        )
        if (
            open_position_payload is None
            or open_position_payload.type != PayloadType.OPEN_POSITION
        ):
            raise ValueError("Invalid open position memo")

        if not reason:
            reason = (
                f"Job {self.id} position opening {'accepted' if accept else 'rejected'}"
            )

        return self.acp_client.respond_to_funds_transfer(memo.id, accept, reason)

    def close_partial_position(
        self, payload: ClosePositionPayload, expired_at: Optional[datetime] = None
    ):
        if expired_at is None:
            expired_at = datetime.now(timezone.utc) + timedelta(days=1)

        close_position_payload = GenericPayload(
            type=PayloadType.CLOSE_PARTIAL_POSITION, data=payload
        )

        return self.acp_client.request_funds(
            self.id,
            payload.amount,
            self.client_address,
            0,
            FeeType.NO_FEE,
            close_position_payload,
            ACPJobPhase.TRANSACTION,
            expired_at,
        )

    def respond_close_partial_position(
        self, memo_id: int, accept: bool, reason: Optional[str] = None
    ):
        memo = self._get_memo_by_id(memo_id)

        if (
            memo is None
            or memo.next_phase != ACPJobPhase.TRANSACTION
            or memo.type != MemoType.PAYABLE_REQUEST
        ):
            print(memo)
            raise ValueError("No close position memo found")

        close_position_payload = try_parse_json_model(
            memo.content, GenericPayload[ClosePositionPayload]
        )
        if (
            close_position_payload is None
            or close_position_payload.type != PayloadType.CLOSE_PARTIAL_POSITION
        ):
            raise ValueError("Invalid close position memo")

        if not reason:
            reason = (
                f"Job {self.id} position closing {'accepted' if accept else 'rejected'}"
            )

        return self.acp_client.respond_to_funds_request(
            memo.id, accept, close_position_payload.data.amount, reason
        )

    def request_close_position(self, payload: RequestClosePositionPayload):
        return self.acp_client.send_message(
            self.id,
            GenericPayload(type=PayloadType.CLOSE_POSITION, data=payload),
            ACPJobPhase.TRANSACTION,
        )

    def response_request_close_position(
        self,
        memo_id: int,
        accept: bool,
        payload: ClosePositionPayload,
        reason: Optional[str] = None,
        expired_at: Optional[datetime] = None,
    ):
        memo = self._get_memo_by_id(memo_id)
        if (
            memo is None
            or memo.next_phase != ACPJobPhase.TRANSACTION
            or memo.type != MemoType.MESSAGE
        ):
            raise ValueError("No message memo found")

        message_payload = try_parse_json_model(
            memo.content, GenericPayload[RequestClosePositionPayload]
        )
        if (
            message_payload is None
            or message_payload.type != PayloadType.CLOSE_POSITION
        ):
            raise ValueError("Invalid close position memo")

        if not reason:
            reason = f"Job {self.id} close position request {'accepted' if accept else 'rejected'}"

        # Sign the memo
        self.acp_client.contract_manager.sign_memo(memo_id, accept, reason)

        if accept:
            if expired_at is None:
                expired_at = datetime.now(timezone.utc) + timedelta(days=1)

            return self.acp_client.transfer_funds(
                self.id,
                payload.amount,
                self.client_address,
                0,
                FeeType.NO_FEE,
                GenericPayload(type=PayloadType.CLOSE_POSITION, data=payload),
                ACPJobPhase.TRANSACTION,
                expired_at,
            )

    def confirm_close_position(
        self, memo_id: int, accept: bool, reason: Optional[str] = None
    ):
        memo = self._get_memo_by_id(memo_id)
        if (
            memo is None
            or memo.next_phase != ACPJobPhase.TRANSACTION
            or memo.type != MemoType.PAYABLE_TRANSFER_ESCROW
        ):
            raise ValueError("No payable transfer memo found")

        payload = try_parse_json_model(
            memo.content, GenericPayload[ClosePositionPayload]
        )
        if payload is None or payload.type != PayloadType.CLOSE_POSITION:
            raise ValueError("Invalid close position memo")

        if not reason:
            reason = f"Job {self.id} close position confirmation {'accepted' if accept else 'rejected'}"

        # Sign the memo
        self.acp_client.contract_manager.sign_memo(memo_id, accept, reason)

    def position_fulfilled(
        self, payload: PositionFulfilledPayload, expired_at: Optional[datetime] = None
    ):
        if expired_at is None:
            expired_at = datetime.now(timezone.utc) + timedelta(days=1)

        position_fulfilled_payload = GenericPayload(
            type=PayloadType.POSITION_FULFILLED, data=payload
        )

        return self.acp_client.transfer_funds(
            self.id,
            payload.amount,
            self.client_address,
            0,
            FeeType.NO_FEE,
            position_fulfilled_payload,
            ACPJobPhase.TRANSACTION,
            expired_at,
        )

    def respond_position_fulfilled(
        self, memo_id: int, accept: bool, reason: Optional[str] = None
    ):
        memo = self._get_memo_by_id(memo_id)
        if (
            memo is None
            or memo.next_phase != ACPJobPhase.TRANSACTION
            or memo.type != MemoType.PAYABLE_TRANSFER_ESCROW
        ):
            raise ValueError("No position fulfilled memo found")

        position_fulfilled_payload = try_parse_json_model(
            memo.content, GenericPayload[PositionFulfilledPayload]
        )
        if (
            position_fulfilled_payload is None
            or position_fulfilled_payload.type != PayloadType.POSITION_FULFILLED
        ):
            raise ValueError("Invalid position fulfilled memo")

        if not reason:
            reason = f"Job {self.id} position fulfilled {'accepted' if accept else 'rejected'}"

        return self.acp_client.respond_to_funds_transfer(memo.id, accept, reason)

    def unfulfilled_position(
        self, payload: UnfulfilledPositionPayload, expired_at: Optional[datetime] = None
    ):
        if expired_at is None:
            expired_at = datetime.now(timezone.utc) + timedelta(days=1)

        unfulfilled_position_payload = GenericPayload(
            type=PayloadType.UNFULFILLED_POSITION, data=payload
        )

        return self.acp_client.transfer_funds(
            self.id,
            payload.amount,
            self.client_address,
            0,
            FeeType.NO_FEE,
            unfulfilled_position_payload,
            ACPJobPhase.TRANSACTION,
            expired_at,
        )

    def respond_unfulfilled_position(
        self, memo_id: int, accept: bool, reason: Optional[str] = None
    ):
        memo = self._get_memo_by_id(memo_id)
        if (
            memo is None
            or memo.next_phase != ACPJobPhase.TRANSACTION
            or memo.type != MemoType.PAYABLE_TRANSFER_ESCROW
        ):
            raise ValueError("No unfulfilled position memo found")

        unfulfilled_position_payload = try_parse_json_model(
            memo.content, GenericPayload[UnfulfilledPositionPayload]
        )
        if (
            unfulfilled_position_payload is None
            or unfulfilled_position_payload.type != PayloadType.UNFULFILLED_POSITION
        ):
            raise ValueError("Invalid unfulfilled position memo")

        if not reason:
            reason = f"Job {self.id} unfulfilled position {'accepted' if accept else 'rejected'}"

        return self.acp_client.respond_to_funds_transfer(memo.id, accept, reason)

    def close_job(self, message: str = "Close job and withdraw all"):
        close_job_payload = GenericPayload(
            type=PayloadType.CLOSE_JOB_AND_WITHDRAW,
            data=CloseJobAndWithdrawPayload(message=message),
        )

        return self.acp_client.send_message(
            self.id, close_job_payload, ACPJobPhase.TRANSACTION
        )

    def respond_close_job(
        self,
        memo_id: int,
        accept: bool,
        fulfilled_positions: List[PositionFulfilledPayload],
        reason: Optional[str] = None,
        expired_at: Optional[datetime] = None,
    ):
        memo = self._get_memo_by_id(memo_id)
        if (
            memo is None
            or memo.next_phase != ACPJobPhase.TRANSACTION
            or memo.type != MemoType.MESSAGE
        ):
            raise ValueError("No close job memo found")

        close_job_payload = try_parse_json_model(
            memo.content, GenericPayload[CloseJobAndWithdrawPayload]
        )
        if (
            close_job_payload is None
            or close_job_payload.type != PayloadType.CLOSE_JOB_AND_WITHDRAW
        ):
            raise ValueError("Invalid close job memo")

        if not reason:
            reason = f"Job {self.id} job closing {'accepted' if accept else 'rejected'}"

        self.acp_client.sign_memo(memo.id, accept, reason)

        if accept:
            if expired_at is None:
                expired_at = datetime.now(timezone.utc) + timedelta(days=1)

            total_amount = sum(p.amount for p in fulfilled_positions)
            close_job_response_payload = GenericPayload(
                type=PayloadType.POSITION_FULFILLED,
                data=fulfilled_positions,
            )

            return self.acp_client.transfer_funds(
                self.id,
                total_amount,
                self.provider_address,
                0,
                FeeType.NO_FEE,
                close_job_response_payload,
                ACPJobPhase.COMPLETED,
                expired_at,
            )

    def confirm_job_closure(
        self, memo_id: int, accept: bool, reason: Optional[str] = None
    ):
        memo = self._get_memo_by_id(memo_id)
        if memo is None:
            raise ValueError("Memo not found")

        job_closure_payload = try_parse_json_model(
            memo.content, GenericPayload[CloseJobAndWithdrawPayload]
        )
        if (
            job_closure_payload is None
            or job_closure_payload.type != PayloadType.CLOSE_JOB_AND_WITHDRAW
        ):
            raise ValueError("Invalid close job and withdraw memo")

        if not reason:
            reason = f"Job {self.id} closing confirmation {'accepted' if accept else 'rejected'}"

        return self.acp_client.sign_memo(memo.id, accept, reason)
