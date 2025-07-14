from datetime import datetime, timedelta
import json
from typing import Any, Dict, Optional, Union, TYPE_CHECKING
from pydantic import BaseModel, field_validator, ConfigDict
from jsonschema import ValidationError, validate

if TYPE_CHECKING:
    from virtuals_acp.client import VirtualsACP

class ACPJobOffering(BaseModel):
    acp_client: "VirtualsACP"
    provider_address: str
    type: str
    price: float
    agent_twitter_handle: Optional[str] = None
    requirementSchema: Optional[Dict[str, Any]] = None
    
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator('requirementSchema', mode='before')
    def parse_requirement_schema(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(json.dumps(v))
            except json.JSONDecodeError:
                return None
        return v
    
    def __str__(self) -> str:
        return (
            f"ACPJobOffering(\n"
            f"  provider_address='{self.provider_address}',\n"
            f"  type='{self.type}',\n"
            f"  price={self.price},\n"
            f"  requirementSchema={json.dumps(self.requirementSchema, indent=2) if self.requirementSchema else None}\n"
            f")"
        )

    def __repr__(self) -> str:
        return self.__str__()

    def initiate_job(
        self,
        service_requirement: Union[Dict[str, Any], str],
        evaluator_address: Optional[str] = None,
        expired_at: Optional[datetime] = None
    ) -> int:
        # Default expiry: 1 day from now
        if expired_at is None:
            expired_at = datetime.utcnow() + timedelta(days=1)
        
        # Validate against requirement schema if present
        if self.requirementSchema:
            try:
                service_requirement = json.loads(json.dumps(service_requirement))
            except json.JSONDecodeError:
                raise ValueError(f"Invalid JSON in service requirement. Required format: {json.dumps(self.requirementSchema, indent=2)}")

            try:
                validate(instance=service_requirement, schema=self.requirementSchema)
            except ValidationError as e:
                raise ValueError(f"Invalid service requirement: {str(e)}")

        return self.acp_client.initiate_job(
            provider_address=self.provider_address,
            service_requirement=service_requirement,
            evaluator_address=evaluator_address,
            amount=self.price,
            expired_at=expired_at,
        )