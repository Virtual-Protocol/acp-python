# virtuals_acp/models.py

from dataclasses import dataclass, field
from typing import Any, List, Optional, TYPE_CHECKING, Dict, Union, TypeVar, Generic, Literal
from enum import Enum

from pydantic import Field, BaseModel, ConfigDict
from pydantic.aliases import AliasChoices
from pydantic.alias_generators import to_camel

if TYPE_CHECKING:
    from virtuals_acp.offering import ACPJobOffering

class ACPMemoStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class MemoType(Enum):
    MESSAGE = 0
    CONTEXT_URL = 1
    IMAGE_URL = 2
    VOICE_URL = 3
    OBJECT_URL = 4
    TXHASH = 5
    PAYABLE_REQUEST = 6
    PAYABLE_TRANSFER = 7
    PAYABLE_TRANSFER_ESCROW = 8


class ACPJobPhase(Enum):
    REQUEST = 0
    NEGOTIATION = 1
    TRANSACTION = 2
    EVALUATION = 3
    COMPLETED = 4
    REJECTED = 5
    EXPIRED = 6


class FeeType(Enum):
    NO_FEE = 0
    IMMEDIATE_FEE = 1
    DEFERRED_FEE = 2


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


class IDeliverable(BaseModel):
    type: str
    value: Union[str, dict]


@dataclass
class IACPAgent:
    id: int
    name: str
    description: str
    wallet_address: str # Checksummed address
    offerings: List["ACPJobOffering"] = field(default_factory=list)
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
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True
    )

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


class NegotiationPayload(PayloadModel):
    name: Optional[str] = None
    service_requirement: Optional[Union[str, Dict[str, Any]]] = Field(
        default=None,
        validation_alias=AliasChoices("serviceRequirement", "service_requirement", "message"),
    )
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
