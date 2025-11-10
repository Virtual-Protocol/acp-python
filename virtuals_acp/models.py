from dataclasses import dataclass, field
from typing import (
    Any,
    List,
    Optional,
    TYPE_CHECKING,
    Dict,
    Union,
    TypeVar,
    Generic,
    Literal,
)
from enum import Enum

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

if TYPE_CHECKING:
    from virtuals_acp.job_offering import ACPJobOffering, ACPResourceOffering


class ACPMemoStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class MemoType(int, Enum):
    MESSAGE = 0  # Text message
    CONTEXT_URL = 1  # URL for context
    IMAGE_URL = 2  # Image URL
    VOICE_URL = 3  # Voice/audio URL
    OBJECT_URL = 4  # Object/file URL
    TXHASH = 5  # Transaction hash reference
    PAYABLE_REQUEST = 6  # Payment request
    PAYABLE_TRANSFER = 7  # Direct payment transfer
    PAYABLE_TRANSFER_ESCROW = 8  # Escrowed payment transfer
    NOTIFICATION = 9  # Notification
    PAYABLE_NOTIFICATION = 10  # Payable notification


class ACPJobPhase(int, Enum):
    REQUEST = 0
    NEGOTIATION = 1
    TRANSACTION = 2
    EVALUATION = 3
    COMPLETED = 4
    REJECTED = 5
    EXPIRED = 6
    UNDEFINED = 999

    @classmethod
    def from_value(cls, value: str):
        try:
            return cls(value)
        except ValueError:
            return cls.UNDEFINED


class FeeType(int, Enum):
    NO_FEE = 0
    IMMEDIATE_FEE = 1
    DEFERRED_FEE = 2
    PERCENTAGE_FEE = 3


class PriceType(str, Enum):
    FIXED = "fixed"
    PERCENTAGE = "percentage"


class ACPAgentSort(str, Enum):
    SUCCESSFUL_JOB_COUNT = "successfulJobCount"
    SUCCESS_RATE = "successRate"
    UNIQUE_BUYER_COUNT = "uniqueBuyerCount"
    MINS_FROM_LAST_ONLINE = "minsFromLastOnlineTime"


class ACPGraduationStatus(str, Enum):
    GRADUATED = "graduated"
    NOT_GRADUATED = "not_graduated"
    ALL = "all"


class ACPOnlineStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    ALL = "all"


DeliverablePayload = Union[str, Dict[str, Any]]
IDeliverable = DeliverablePayload  # Deprecated: use DeliverablePayload instead


@dataclass
class IACPAgent:
    id: int
    name: str
    description: str
    wallet_address: str  # Checksummed address
    job_offerings: List["ACPJobOffering"] = field(default_factory=list)
    resources: List["ACPResourceOffering"] = field(default_factory=list)
    twitter_handle: Optional[str] = None
    # Full fields from TS for completeness, though browse_agent returns a subset
    document_id: Optional[str] = None
    is_virtual_agent: Optional[bool] = None
    profile_pic: Optional[str] = None
    category: Optional[str] = None
    token_address: Optional[str] = None
    owner_address: Optional[str] = None
    cluster: Optional[str] = None
    symbol: Optional[str] = None
    virtual_agent_id: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None
    processing_time: Optional[str] = None


class PayloadType(str, Enum):
    FUND_RESPONSE = "fund_response"
    OPEN_POSITION = "open_position"
    CLOSE_POSITION = "close_position"
    CLOSE_PARTIAL_POSITION = "close_partial_position"
    POSITION_FULFILLED = "position_fulfilled"
    CLOSE_JOB_AND_WITHDRAW = "close_job_and_withdraw"
    UNFULFILLED_POSITION = "unfulfilled_position"


T = TypeVar("T", bound=BaseModel)


class PayloadModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, validate_by_name=True)

    # JSON-friendly payload fields when using model_dump and model_dump_json
    def model_dump(self, *args, **kwargs):
        kwargs.setdefault("by_alias", True)
        return super().model_dump(*args, **kwargs)

    def model_dump_json(self, *args, **kwargs):
        kwargs.setdefault("by_alias", True)
        return super().model_dump_json(*args, **kwargs)

    def __str__(self):
        return f"{self.__class__.__name__}({self.model_dump(by_alias=False)})"


class GenericPayload(PayloadModel, Generic[T]):
    type: PayloadType
    data: T | List[T]


class RequestPayload(PayloadModel):
    name: Optional[str] = None
    requirement: Optional[Union[str, Dict[str, Any]]] = None
    service_name: Optional[str] = None
    service_requirement: Optional[Dict[str, Any]] = None
    price_type: PriceType = PriceType.FIXED
    price_value: Optional[float] = None
    model_config = ConfigDict(extra="allow")


class FundResponsePayload(PayloadModel):
    reporting_api_endpoint: str
    wallet_address: Optional[str] = None


class TPSLConfig(PayloadModel):
    price: Optional[float] = None
    percentage: Optional[float] = None


class PositionDirection(str, Enum):
    LONG = "long"
    SHORT = "short"


class OpenPositionPayload(PayloadModel):
    symbol: str
    amount: float
    chain: Optional[str] = None
    contract_address: Optional[str] = None
    direction: Optional[PositionDirection] = None
    tp: TPSLConfig
    sl: TPSLConfig


class UpdateTPSLConfig(PayloadModel):
    amount_percentage: Optional[float] = None


class UpdatePositionPayload(PayloadModel):
    symbol: str
    contract_address: Optional[str] = None
    tp: Optional[UpdateTPSLConfig] = None
    sl: Optional[UpdateTPSLConfig] = None


class ClosePositionPayload(PayloadModel):
    position_id: int
    amount: float


class PositionFulfilledPayload(PayloadModel):
    symbol: str
    amount: float
    contract_address: str
    type: Literal["TP", "SL", "CLOSE"]
    pnl: float
    entry_price: float
    exit_price: float


class UnfulfilledPositionPayload(PayloadModel):
    symbol: str
    amount: float
    contract_address: str
    type: Literal["ERROR", "PARTIAL"]
    reason: Optional[str] = None


class CloseJobAndWithdrawPayload(PayloadModel):
    message: str


class RequestClosePositionPayload(PayloadModel):
    position_id: int


class AcpJobX402PaymentDetails(PayloadModel):
    is_x402: bool
    is_budget_received: bool


class X402Config(PayloadModel):
    url: str


class X402RequirementExtra(PayloadModel):
    name: str
    version: str


class X402Requirement(PayloadModel):
    scheme: str
    network: str
    maxAmountRequired: str
    resource: str
    description: str
    mimeType: str
    payTo: str  # Address as str
    maxTimeoutSeconds: int
    asset: str  # Address as str
    extra: X402RequirementExtra
    outputSchema: Any


class X402PayableRequirements(PayloadModel):
    x402Version: int
    error: str
    accepts: List[X402Requirement]


class X402PayableRequest(PayloadModel):
    to: str  # Address as str
    value: int
    maxTimeoutSeconds: int
    asset: str  # Address as str


class X402Payment(PayloadModel):
    encodedPayment: str
    message: Dict[str, Any]
    signature: str


class X402PaymentPayload(PayloadModel):
    x402_version: int
    scheme: str
    network: str
    payload: Dict[str, Any]


class OperationPayload(PayloadModel):
    data: str  # Should start with '0x'
    to: str  # Address as str
    value: Optional[int] = None


class OffChainJob(PayloadModel):
    id: int
    documentId: str
    txHash: str  # Address as str
    clientId: int
    providerId: int
    budget: float
    createdAt: str
    updatedAt: str
    publishedAt: str
    locale: Optional[str] = None
    clientAddress: str
    providerAddress: str
    evaluators: List[str]
    budgetTxHash: Optional[str] = None
    phase: str  # AcpJobPhases as str (define separately if available)
    agentIdPair: str
    onChainJobId: str
    summary: str
    userOpHash: Optional[str] = None
    amountClaimed: float
    context: Optional[Dict[str, Any]] = None
    expiry: str
    refundRetryTimes: int
    additionalFees: float
    budgetTokenAddress: str
    budgetUSD: float
    amountClaimedUSD: Optional[float] = None
    additionalFeesUSD: Optional[float] = None
    contractAddress: str
    accountId: Optional[int] = None
    x402Nonce: str


class X402PaymentResponse(PayloadModel):
    isPaymentRequired: bool
    data: X402PayableRequirements
