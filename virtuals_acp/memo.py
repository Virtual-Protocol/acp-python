from typing import Optional, Type, TypeVar

from pydantic import BaseModel, ConfigDict

from virtuals_acp.models import ACPJobPhase, T, PayloadType
from virtuals_acp.models import MemoType, GenericPayload
from virtuals_acp.utils import try_parse_json_model, try_validate_model


class ACPMemo(BaseModel):
    id: int
    type: MemoType
    content: str
    next_phase: ACPJobPhase
    structured_content: Optional[GenericPayload] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(self, **data):
        super().__init__(**data)
        self.structured_content = try_parse_json_model(self.content, GenericPayload)

    def __str__(self):
        return f"AcpMemo(id={self.id}, type={self.type}, content={self.content}, next_phase={self.next_phase})"

    @property
    def payload_type(self) -> Optional[PayloadType]:
        if self.structured_content is not None:
            return self.structured_content.type

    def get_data_as(self, model: Type[T]) -> Optional[T]:
        if self.structured_content is None:
            return None
        return try_validate_model(self.structured_content.data, model)
