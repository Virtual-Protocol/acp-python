from datetime import datetime
import json
from typing import Any, Dict, Optional, Union, TYPE_CHECKING
from pydantic import BaseModel, field_validator, ConfigDict
from jsonschema import ValidationError, validate

if TYPE_CHECKING:
    from virtuals_acp.client import VirtualsACP

class ACPJobOffering(BaseModel):
    acp_client: "VirtualsACP"
    provider_address: str
    name: str
    price: float
    price_usd: float
    requirement_schema: Optional[Dict[str, Any]] = None
    
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator('requirement_schema', mode='before')
    def parse_requirement_schema(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(json.dumps(v))
            except json.JSONDecodeError:
                return None
        return v

    def __str__(self):
        return f"ACPJobOffering({self.model_dump(exclude={'acp_client'})})"

    def __repr__(self) -> str:
        return self.__str__()

    def initiate_job(
        self,
        service_requirement: Union[Dict[str, Any], str],
        evaluator_address: Optional[str] = None,
        expired_at: Optional[datetime] = None
    ) -> int:
        # Validate against requirement schema if present
        if self.requirement_schema:
            try:
                service_requirement = json.loads(json.dumps(service_requirement))
            except json.JSONDecodeError:
                raise ValueError(f"Invalid JSON in service requirement. Required format: {json.dumps(self.requirement_schema, indent=2)}")

            try:
                validate(instance=service_requirement, schema=self.requirement_schema)
            except ValidationError as e:
                raise ValueError(f"Invalid service requirement: {str(e)}")

        final_service_requirement = {
            "name": self.name
        }

        if isinstance(service_requirement, str):
            final_service_requirement["message"] = service_requirement
        else:
            final_service_requirement["serviceRequirement"] = service_requirement

        return self.acp_client.initiate_job(
            provider_address=self.provider_address,
            service_requirement=final_service_requirement,
            evaluator_address=evaluator_address,
            amount=self.price,
            expired_at=expired_at,
        )
