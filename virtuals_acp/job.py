from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING, List, Optional, Dict, Any, Union

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
from virtuals_acp.utils import try_parse_json_model, deprecated
from virtuals_acp.fare import Fare
from virtuals_acp.models import (
    ACPJobPhase,
    MemoType,
    IACPAgent,
    IDeliverable,
    FeeType,
    GenericPayload,
    T,
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
    price_token_address: str
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

    def account(self):
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

    def create_requirement_memo(self, content: str) -> ACPMemo:
        return self.acp_contract_client.create_memo(
            self.id,
            content,
            MemoType.MESSAGE,
            False,
            ACPJobPhase.TRANSACTION,
        )

    def create_requirement_payable_memo(
        self,
        content: str,
        type: MemoType,
        amount: FareAmountBase,
        recipient: str,
        expired_at: Optional[datetime] = None,
    ) -> ACPMemo:
        if expired_at is None:
            expired_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        if type == MemoType.PAYABLE_TRANSFER_ESCROW or type == MemoType.PAYABLE_TRANSFER:
            self.acp_contract_client.approve_allowance(
                amount.amount,
                amount.fare.contract_address,
            )

        fee_amount = FareAmount(0, self.base_fare)

        return self.acp_contract_client.create_payable_memo(
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

    def pay_and_accept_requirement(self, reason: Optional[str] = None) -> ACPMemo:
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

        return self.acp_contract_client.create_memo(
            self.id,
            f"Payment made. {reason or ''}".strip(),
            MemoType.MESSAGE,
            True,
            ACPJobPhase.EVALUATION,
        )

    def accept(self, reason: Optional[str] = None):
        if self.latest_memo is None or self.latest_memo.next_phase != ACPJobPhase.NEGOTIATION:
            raise ValueError("No negotiation memo found")
        memo = self.latest_memo
        memo.sign(True, reason)
        return self.acp_contract_client.create_memo(
            self.id,
            f"Job {self.id} accepted. {reason or ''}",
            MemoType.MESSAGE,
            True,
            ACPJobPhase.TRANSACTION,
        )

    def reject(self, reason: Optional[str] = None):
        if self.latest_memo is None or self.latest_memo.next_phase != ACPJobPhase.NEGOTIATION:
            raise ValueError("No negotiation memo found")
        memo = self.latest_memo
        return self.acp_contract_client.sign_memo(
            memo.id,
            False,
            f"Job {self.id} rejected. {reason or ''}",
        )

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
    
    def create_notification(self, content: str):
        return self.acp_contract_client.create_memo(
            job_id=self.id,
            content=content,
            memo_type=MemoType.NOTIFICATION,
            is_secured=True,
            next_phase=ACPJobPhase.COMPLETED,
        )

    @deprecated("The method should not be used")
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

    @deprecated("The method should not be used")
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

    @deprecated("The method should not be used")
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

    @deprecated("The method should not be used")
    def respond_close_partial_position(
        self, memo_id: int, accept: bool, reason: Optional[str] = None
    ):
        memo = self._get_memo_by_id(memo_id)

        if (
            memo is None
            or memo.next_phase != ACPJobPhase.TRANSACTION
            or memo.type != MemoType.PAYABLE_REQUEST
        ):
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

    @deprecated("The method should not be used")
    def request_close_position(self, payload: RequestClosePositionPayload):
        return self.acp_client.send_message(
            self.id,
            GenericPayload(type=PayloadType.CLOSE_POSITION, data=payload),
            ACPJobPhase.TRANSACTION,
        )

    @deprecated("The method should not be used")
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

    @deprecated("The method should not be used")
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

    @deprecated("The method should not be used")
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

    @deprecated("The method should not be used")
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

    @deprecated("The method should not be used")
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

    @deprecated("The method should not be used")
    def close_job(self, message: str = "Close job and withdraw all"):
        close_job_payload = GenericPayload(
            type=PayloadType.CLOSE_JOB_AND_WITHDRAW,
            data=CloseJobAndWithdrawPayload(message=message),
        )

        return self.acp_client.send_message(
            self.id, close_job_payload, ACPJobPhase.TRANSACTION
        )

    @deprecated("The method should not be used")
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

    @deprecated("The method should not be used")
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
