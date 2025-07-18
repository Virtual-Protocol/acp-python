# virtuals_acp/models.py

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional, TYPE_CHECKING, Dict, TypeVar, Generic, Literal

from pydantic import BaseModel

if TYPE_CHECKING:
    from virtuals_acp.offering import ACPJobOffering


class MemoType(Enum):
    MESSAGE = 0
    CONTEXT_URL = 1
    IMAGE_URL = 2
    VOICE_URL = 3
    OBJECT_URL = 4
    TXHASH = 5
    PAYABLE_REQUEST = 6
    PAYABLE_TRANSFER = 7
    PAYABLE_FEE = 8
    PAYABLE_FEE_REQUEST = 9


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
    IS_ONLINE = "isOnline"


@dataclass
class IACPAgent:
    id: int
    name: str
    description: str
    wallet_address: str  # Checksummed address
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
    POSITION_FULFILLED = "position_fulfilled"
    CLOSE_JOB_AND_WITHDRAW = "close_job_and_withdraw"
    UNFULFILLED_POSITION = "unfulfilled_position"


T = TypeVar("T", bound=BaseModel)


class GenericPayload(BaseModel, Generic[T]):
    type: PayloadType
    data: T | List[T]


class FundResponsePayload(BaseModel):
    reporting_api_endpoint: str
    wallet_address: Optional[str] = None


class TPSLConfig(BaseModel):
    price: Optional[float] = None
    percentage: Optional[float] = None


class OpenPositionPayload(BaseModel):
    symbol: str
    amount: float
    contract_address: Optional[str] = None
    tp: TPSLConfig
    sl: TPSLConfig


class UpdateTPSLConfig(TPSLConfig):
    amount_percentage: Optional[float] = None


class UpdatePositionPayload(BaseModel):
    symbol: str
    contract_address: Optional[str] = None
    tp: Optional[UpdateTPSLConfig] = None
    sl: Optional[UpdateTPSLConfig] = None


class ClosePositionPayload(BaseModel):
    symbol: str
    amount: float
    contract_address: Optional[str] = None


class PositionFulfilledPayload(BaseModel):
    symbol: str
    amount: float
    contract_address: str
    type: Literal["TP", "SL", "CLOSE"]
    pnl: float
    entry_price: float
    exit_price: float


class UnfulfilledPositionPayload(BaseModel):
    symbol: str
    amount: float
    contract_address: str
    type: Literal["ERROR", "PARTIAL"]
    reason: Optional[str] = None


class CloseJobAndWithdrawPayload(BaseModel):
    message: str
