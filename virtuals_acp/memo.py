from datetime import datetime
from typing import TYPE_CHECKING, Optional, Type, Dict, List, Any

from pydantic import BaseModel, ConfigDict

from virtuals_acp.models import (
    ACPJobPhase,
    MemoType,
    PayloadType,
    GenericPayload,
    T,
    ACPMemoStatus,
)
from virtuals_acp.utils import try_parse_json_model, try_validate_model

if TYPE_CHECKING:
    from virtuals_acp.client import VirtualsACP


class ACPMemo(BaseModel):
    acp_client: "VirtualsACP"
    id: int
    type: MemoType
    content: str
    next_phase: ACPJobPhase
    status: ACPMemoStatus
    signed_reason: Optional[str] = None
    expiry: Optional[datetime] = None
    payable_details: Optional[Dict[str, Any]] = None

    structured_content: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def model_post_init(self, _):
        self.structured_content = try_parse_json_model(
            self.content, GenericPayload[Dict]
        )

        if self.payable_details:
            self.payable_details["amount"] = int(self.payable_details["amount"])
            self.payable_details["feeAmount"] = int(self.payable_details["feeAmount"])

        self.structured_content = try_parse_json_model(
            self.content, GenericPayload[Dict]
        )

    def __str__(self):
        return f"AcpMemo({self.model_dump(exclude={'payable_details'})})"

    @property
    def payload_type(self) -> Optional[PayloadType]:
        if self.structured_content is not None:
            return self.structured_content.type

    def get_data_as(self, model: Type[T]) -> Optional[T | List[T]]:
        if self.structured_content is None:
            return None

        data = self.structured_content.data
        if isinstance(data, list):
            validated = [try_validate_model(i, model) for i in data]
            return validated[0] if len(validated) == 1 else validated
        else:
            return try_validate_model(data, model)

    def create(self, job_id: int, is_secured: bool = True):
        return self.acp_client.contract_manager.create_memo(
            job_id, self.content, self.type, is_secured, self.next_phase
        )

    def sign(self, approved: bool, reason: str | None = None):
        return self.acp_client.contract_manager.sign_memo(self.id, approved, reason)
