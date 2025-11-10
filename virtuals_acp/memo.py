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
from virtuals_acp.utils import (
    try_parse_json_model,
    try_validate_model,
    get_txn_hash_from_response,
)

if TYPE_CHECKING:
    from virtuals_acp.contract_clients.base_contract_client import BaseAcpContractClient


class ACPMemo(BaseModel):
    contract_client: "BaseAcpContractClient"
    id: int
    type: MemoType
    content: str
    next_phase: ACPJobPhase
    status: ACPMemoStatus
    signed_reason: Optional[str] = None
    expiry: Optional[datetime] = None
    payable_details: Optional[Dict[str, Any]] = None

    structured_content: Optional[GenericPayload] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def model_post_init(self, _):
        self.structured_content = try_parse_json_model(self.content, GenericPayload)

        if self.payable_details:
            self.payable_details["amount"] = int(self.payable_details["amount"])
            self.payable_details["feeAmount"] = int(self.payable_details["feeAmount"])

    def __str__(self):
        return f"AcpMemo({self.model_dump(exclude={'payable_details'})})"

    @property
    def payload_type(self) -> Optional[PayloadType]:
        if self.structured_content is not None:
            return self.structured_content.type

    def create(self, job_id: int, is_secured: bool = True):
        return self.contract_client.create_memo(
            job_id, self.content, self.type, is_secured, self.next_phase
        )

    def sign(self, approved: bool, reason: str | None = None) -> str | None:
        operation = self.contract_client.sign_memo(self.id, approved, reason)
        response = self.contract_client.handle_operation([operation])
        return get_txn_hash_from_response(response)
