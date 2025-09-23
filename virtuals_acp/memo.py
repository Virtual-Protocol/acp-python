from datetime import datetime
from typing import Optional, Type, Dict, List

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


class ACPMemo(BaseModel):
    id: int
    type: MemoType
    content: str
    next_phase: Optional[ACPJobPhase] = None
    status: ACPMemoStatus
    signed_reason: Optional[str] = None
    expiry: Optional[datetime] = None
    structured_content: Optional[GenericPayload] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(self, **data):
        super().__init__(**data)
        self.structured_content = try_parse_json_model(
            self.content, GenericPayload[Dict]
        )

    def __str__(self):
        return f"AcpMemo({self.model_dump(exclude={'structured_content'})})"

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
