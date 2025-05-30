# virtuals_acp/models.py

from dataclasses import dataclass, field
from typing import Any, List, Optional, TYPE_CHECKING, Dict
from enum import Enum

if TYPE_CHECKING:
    from virtuals_acp.offering import ACPJobOffering

class MemoType(Enum):
    MESSAGE = 0
    CONTEXT_URL = 1
    IMAGE_URL = 2
    VOICE_URL = 3
    OBJECT_URL = 4
    TXHASH = 5

class ACPJobPhase(Enum):
    REQUEST = 0
    NEGOTIATION = 1
    TRANSACTION = 2
    EVALUATION = 3
    COMPLETED = 4
    REJECTED = 5
    
class ACPAgentSort(Enum):
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


