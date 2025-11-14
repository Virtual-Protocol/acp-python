from datetime import datetime, timezone, timedelta
import time
from typing import TYPE_CHECKING, List, Optional, Dict, Any, Union, Literal

from pydantic import BaseModel, Field, ConfigDict, PrivateAttr

from virtuals_acp.account import ACPAccount
from virtuals_acp.memo import ACPMemo
from virtuals_acp.models import (
    PriceType,
    OperationPayload,
    X402PayableRequest,
    X402PayableRequirements,
    RequestPayload,
)
from virtuals_acp.utils import (
    try_parse_json_model,
    prepare_payload,
    get_txn_hash_from_response,
)
from virtuals_acp.models import (
    ACPJobPhase,
    MemoType,
    IACPAgent,
    DeliverablePayload,
    FeeType,
)
from virtuals_acp.fare import Fare, FareAmountBase, FareAmount

if TYPE_CHECKING:
    from virtuals_acp.client import VirtualsACP


class ACPJob(BaseModel):
    acp_client: "VirtualsACP"
    id: int
    client_address: str
    provider_address: str
    evaluator_address: str
    price: float
    price_token_address: Optional[str] = None
    memos: List[ACPMemo] = Field(default_factory=list)
    phase: ACPJobPhase
    context: Dict[str, Any] | None
    contract_address: Optional[str] = None
    net_payable_amount: Optional[float] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    _base_fare: Optional[Fare] = PrivateAttr(default=None)
    _name: Optional[str] = PrivateAttr(default=None)
    _requirement: Optional[Union[str, Dict[str, Any]]] = PrivateAttr(default=None)
    _price_type: PriceType = PrivateAttr(default=PriceType.FIXED)
    _price_value: float = PrivateAttr(default=0.0)

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

        content_obj = try_parse_json_model(memo.content, RequestPayload)

        if not content_obj:
            return None

        self._requirement = content_obj.service_requirement or content_obj.requirement
        self._name = content_obj.service_name or content_obj.name
        self._price_type = content_obj.price_type or PriceType.FIXED
        self._price_value = content_obj.price_value or self.price

    @property
    def requirement(self) -> Optional[Union[str, Dict[str, Any]]]:
        return self._requirement

    @property
    def name(self) -> Optional[str]:
        return self._name

    @property
    def price_type(self) -> PriceType:
        return self._price_type

    @property
    def price_value(self) -> float:
        return self._price_value

    def __str__(self):
        return (
            f"AcpJob(\n"
            f"  id={self.id},\n"
            f"  client_address='{self.client_address}',\n"
            f"  provider_address='{self.provider_address}',\n"
            f"  evaluator_address='{self.evaluator_address}',\n"
            f"  price={self.price},\n"
            f"  price_token_address='{self.price_token_address}',\n"
            f"  memos=[{', '.join(str(memo) for memo in self.memos)}],\n"
            f"  phase={self.phase}\n"
            f"  context={self.context}\n"
            f"  contract_address='{self.contract_address}',\n"
            f"  net_payable_amount='{self.net_payable_amount}',\n"
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
        if self.phase != ACPJobPhase.REJECTED:
            return None

        request_memo = next(
            (
                m
                for m in self.memos
                if m.next_phase == ACPJobPhase.NEGOTIATION
            ),
            None,
        )
        if request_memo:
            return request_memo.signed_reason

        fallback_memo = next(
            (m for m in self.memos if m.next_phase == ACPJobPhase.REJECTED),
            None
        )
        return fallback_memo.content if fallback_memo else None

    def create_requirement(self, content: str) -> str | None:
        operations: List[OperationPayload] = []

        operations.append(
            self.acp_contract_client.create_memo(
                self.id,
                content,
                MemoType.MESSAGE,
                False,
                ACPJobPhase.TRANSACTION,
            )
        )

        response = self.acp_contract_client.handle_operation(operations)
        return get_txn_hash_from_response(response)

    def create_payable_requirement(
        self,
        content: str,
        type: Literal[MemoType.PAYABLE_REQUEST, MemoType.PAYABLE_TRANSFER_ESCROW],
        amount: FareAmountBase,
        recipient: str,
        expired_at: Optional[datetime] = None,
    ) -> str | None:
        operations: List[OperationPayload] = []

        if expired_at is None:
            expired_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        if type == MemoType.PAYABLE_TRANSFER_ESCROW:
            operations.append(
                self.acp_contract_client.approve_allowance(
                    amount.amount,
                    amount.fare.contract_address,
                )
            )

        if self._price_type == PriceType.PERCENTAGE:
            fee_amount = int(self.price_value * 10000)
            fee_type = FeeType.PERCENTAGE_FEE
        else:
            fee_amount = (FareAmount(0, self.base_fare)).amount
            fee_type = FeeType.NO_FEE

        operations.append(
            self.acp_contract_client.create_payable_memo(
                self.id,
                content,
                amount.amount,
                recipient,
                fee_amount,
                fee_type,
                ACPJobPhase.TRANSACTION,
                type,
                expired_at,
                amount.fare.contract_address,
            )
        )

        response = self.acp_contract_client.handle_operation(operations)
        return get_txn_hash_from_response(response)

    def pay_and_accept_requirement(self, reason: Optional[str] = "") -> str | None:
        memo = next(
            (m for m in self.memos if m.next_phase == ACPJobPhase.TRANSACTION), None
        )

        if not memo:
            raise Exception("No negotiation memo found")

        operations: List[OperationPayload] = []
        base_fare_amount = FareAmount(self.price, self.base_fare)

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
        operations.append(
            self.acp_contract_client.approve_allowance(
                total_amount.amount,
                self.base_fare.contract_address,
            )
        )

        # approve transfer if token differs
        if (
            base_fare_amount.fare.contract_address
            != transfer_amount.fare.contract_address
        ):
            operations.append(
                self.acp_contract_client.approve_allowance(
                    transfer_amount.amount,
                    transfer_amount.fare.contract_address,
                )
            )

        # sign memo
        operations.append(self.acp_contract_client.sign_memo(memo.id, True, reason))

        operations.append(
            self.acp_contract_client.create_memo(
                self.id,
                f"Payment made. {reason or ''}".strip(),
                MemoType.MESSAGE,
                True,
                ACPJobPhase.EVALUATION,
            )
        )

        x402PaymentDetails = self.acp_contract_client.get_x402_payment_details(self.id)
        if x402PaymentDetails.is_x402:
            self.perform_x402_payment(self.price)

        response = self.acp_contract_client.handle_operation(operations)
        return get_txn_hash_from_response(response)

    def accept(self, reason: Optional[str] = None) -> str | None:
        memo_content = f"Job {self.id} accepted. {reason or ''}"
        latest_memo = self.latest_memo
        if latest_memo is None or latest_memo.next_phase != ACPJobPhase.NEGOTIATION:
            raise ValueError("No request memo found")

        return latest_memo.sign(True, memo_content)

    def reject(self, reason: Optional[str] = None) -> str | None:
        memo_content = f"Job {self.id} rejected. {reason or ''}"
        latest_memo = self.latest_memo
        operations: List[OperationPayload] = []

        if self.phase is ACPJobPhase.REQUEST:
            if latest_memo is None or latest_memo.next_phase != ACPJobPhase.NEGOTIATION:
                raise ValueError("No request memo found")

            return latest_memo.sign(False, memo_content)

        operations.append(
            self.acp_contract_client.create_memo(
                self.id,
                memo_content,
                MemoType.MESSAGE,
                True,
                ACPJobPhase.REJECTED
            )
        )

        response = self.acp_contract_client.handle_operation(operations)
        return get_txn_hash_from_response(response)

    def reject_payable(
        self,
        reason: Optional[str],
        amount: FareAmountBase,
        expired_at: Optional[datetime] = None,
    ) -> str | None:
        if expired_at is None:
            expired_at = datetime.now(timezone.utc) + timedelta(minutes=5)

        memo_content = f"Job {self.id} rejected. {reason or ''}"
        fee_amount = FareAmount(0, self.acp_contract_client.config.base_fare)
        operations: List[OperationPayload] = []

        operations.append(
            self.acp_contract_client.approve_allowance(
                amount.amount,
                amount.fare.contract_address
            )
        )

        operations.append(
            self.acp_contract_client.create_payable_memo(
                job_id=self.id,
                content=memo_content,
                amount_base_unit=amount.amount,
                recipient=self.client_address,
                fee_amount_base_unit=fee_amount.amount,
                fee_type=FeeType.NO_FEE,
                next_phase=ACPJobPhase.REJECTED,
                memo_type=MemoType.PAYABLE_TRANSFER,
                expired_at=expired_at,
                token=amount.fare.contract_address,
            )
        )

        response = self.acp_contract_client.handle_operation(operations)
        return get_txn_hash_from_response(response)

    def respond(
        self,
        accept: bool,
        reason: Optional[str] = None,
    ) -> str | None:
        memo_content = (
            f"Job {self.id} {'accepted' if accept else 'rejected'}. {reason or ''}"
        )
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

    def _get_memo_by_id(self, memo_id) -> Optional[ACPMemo]:
        return next((m for m in self.memos if m.id == memo_id), None)

    def deliver(self, deliverable: DeliverablePayload) -> str | None:
        if (
            self.latest_memo is None
            or self.latest_memo.next_phase != ACPJobPhase.EVALUATION
        ):
            raise ValueError("No transaction memo found")

        operations: List[OperationPayload] = []

        operations.append(
            self.acp_contract_client.create_memo(
                self.id,
                prepare_payload(deliverable),
                MemoType.MESSAGE,
                True,
                ACPJobPhase.COMPLETED,
            )
        )

        response = self.acp_contract_client.handle_operation(operations)
        return get_txn_hash_from_response(response)

    def deliver_payable(
        self,
        deliverable: DeliverablePayload,
        amount: FareAmountBase,
        expired_at: Optional[datetime] = None,
    ) -> str | None:
        if expired_at is None:
            expired_at = datetime.now(timezone.utc) + timedelta(minutes=5)

        if (
            self.latest_memo is None
            or self.latest_memo.next_phase != ACPJobPhase.EVALUATION
        ):
            raise ValueError("No transaction memo found")

        operations: List[OperationPayload] = []

        operations.append(
            self.acp_contract_client.approve_allowance(
                amount.amount, amount.fare.contract_address
            )
        )

        fee_amount = FareAmount(0, self.acp_contract_client.config.base_fare)

        operations.append(
            self.acp_contract_client.create_payable_memo(
                job_id=self.id,
                content=prepare_payload(deliverable),
                amount_base_unit=amount.amount,
                recipient=self.client_address,
                fee_amount_base_unit=fee_amount.amount,
                fee_type=FeeType.NO_FEE,
                next_phase=ACPJobPhase.COMPLETED,
                memo_type=MemoType.PAYABLE_TRANSFER,
                expired_at=expired_at,
                token=amount.fare.contract_address,
            )
        )

        response = self.acp_contract_client.handle_operation(operations)
        return get_txn_hash_from_response(response)

    def evaluate(self, accept: bool, reason: Optional[str] = None) -> str | None:
        if (
            self.latest_memo is None
            or self.latest_memo.next_phase != ACPJobPhase.COMPLETED
        ):
            raise ValueError("No evaluation memo found")

        if not reason:
            reason = f"Job {self.id} delivery {'accepted' if accept else 'rejected'}"

        return self.latest_memo.sign(accept, reason)

    def create_notification(self, content: str) -> str | None:
        operations: List[OperationPayload] = []

        operations.append(
            self.acp_contract_client.create_memo(
                job_id=self.id,
                content=content,
                memo_type=MemoType.NOTIFICATION,
                is_secured=True,
                next_phase=ACPJobPhase.COMPLETED,
            )
        )

        response = self.acp_contract_client.handle_operation(operations)
        return get_txn_hash_from_response(response)

    def create_payable_notification(
        self,
        content: str,
        amount: FareAmountBase,
        expired_at: Optional[datetime] = None,
    ):
        operations: List[OperationPayload] = []

        if expired_at is None:
            expired_at = datetime.now(timezone.utc) + timedelta(minutes=5)

        operations.append(
            self.acp_contract_client.approve_allowance(
                amount.amount,
                amount.fare.contract_address
            )
        )

        fee_amount = FareAmount(0, self.acp_contract_client.config.base_fare)

        operations.append(
            self.acp_contract_client.create_payable_memo(
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
        )

        response = self.acp_contract_client.handle_operation(operations)
        return get_txn_hash_from_response(response)

    def perform_x402_payment(self, budget: float):
        try:
            payment_url = "/acp-budget"

            # Perform X402 request to get payment requirements
            x402_payable_requirements = self.acp_contract_client.perform_x402_request(
                payment_url, self.acp_contract_client.getAcpVersion(), str(budget)
            )

            if not x402_payable_requirements.get("isPaymentRequired"):
                return

            accepts = x402_payable_requirements["data"].get("accepts", [])
            if not accepts:
                raise Exception("No X402 payment requirements found")

            requirement = accepts[0]

            x402_payment = self.acp_contract_client.generate_x402_payment(
                X402PayableRequest(
                    to=requirement["payTo"],
                    value=int(requirement["maxAmountRequired"]),
                    maxTimeoutSeconds=requirement["maxTimeoutSeconds"],
                    asset=requirement["asset"],
                ),
                X402PayableRequirements.model_validate(
                    x402_payable_requirements["data"]
                ),
            )
            encoded_payment = x402_payment.encodedPayment
            signature = x402_payment.signature
            message = x402_payment.message
            nonce = message.get("nonce") if message else None

            if not nonce:
                raise Exception("No nonce found in X402 message")

            self.acp_contract_client.update_job_x402_nonce(self.id, str(nonce))

            x402_response = self.acp_contract_client.perform_x402_request(
                payment_url, self.acp_contract_client.getAcpVersion(), str(budget), encoded_payment
            )
            if x402_response.get("isPaymentRequired"):
                # If payment is required, submit transfer with authorization and handle the operation
                operations = (
                    self.acp_contract_client.submit_transfer_with_authorization(
                        message["from"],
                        message["to"],
                        int(message["value"]),
                        int(message["validAfter"]),
                        int(message["validBefore"]),
                        message["nonce"],
                        signature,
                    )
                )
                self.acp_contract_client.handle_operation(operations)

            wait_ms = 2000
            max_wait_ms = 30000  # max 30 seconds of polling
            iteration_count = 0
            max_iterations = 10

            while True:
                x402_payment_details = (
                    self.acp_contract_client.get_x402_payment_details(self.id)
                )
                if x402_payment_details.is_budget_received:
                    break

                iteration_count += 1
                if iteration_count >= max_iterations:
                    raise Exception("X402 payment timed out")
                time.sleep(wait_ms / 1000.0)
                wait_ms = min(wait_ms * 2, max_wait_ms)

        except Exception as e:
            # Optionally: handle exception, log, or re-raise
            print(f"An error occurred during perform_x402_payment: {e}")
            raise
