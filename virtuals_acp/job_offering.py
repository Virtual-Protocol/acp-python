from datetime import datetime, timezone, timedelta
import json
from typing import Any, Dict, Optional, Union, TYPE_CHECKING
from pydantic import BaseModel, field_validator, ConfigDict
from jsonschema import ValidationError, validate
from virtuals_acp.fare import FareAmount
from virtuals_acp.contract_clients.base_contract_client import BaseAcpContractClient
from virtuals_acp.models import ACPJobPhase, MemoType
from virtuals_acp.configs.configs import BASE_SEPOLIA_CONFIG, BASE_MAINNET_CONFIG
from web3 import Web3


if TYPE_CHECKING:
    from virtuals_acp.client import VirtualsACP

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


class ACPJobOffering(BaseModel):
    acp_client: "VirtualsACP"
    contract_client: BaseAcpContractClient
    provider_address: str
    name: str
    price: float
    requirement: Optional[Union[Dict[str, Any], str]] = None
    deliverable: Optional[Union[Dict[str, Any], str]] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator("requirement", mode="before")
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
        expired_at: Optional[datetime] = None,
    ) -> int:
        if expired_at is None:
            expired_at = datetime.now(timezone.utc) + timedelta(days=1)

        # Validate against requirement schema if present
        if self.requirement:
            try:
                service_requirement = json.loads(json.dumps(service_requirement))
            except json.JSONDecodeError:
                raise ValueError(
                    f"Invalid JSON in service requirement. Required format: {json.dumps(self.requirement, indent=2)}"
                )

            if isinstance(self.requirement, dict):
                try:
                    validate(instance=service_requirement, schema=self.requirement)
                except ValidationError as e:
                    raise ValueError(f"Invalid service requirement: {str(e)}")

        final_service_requirement: Dict[str, Any] = {"name": self.name}

        if isinstance(service_requirement, str):
            final_service_requirement["requirement"] = service_requirement
        else:
            final_service_requirement["requirement"] = service_requirement

        # Prepare fare amount based on this offering's price and contract's base fare
        fare_amount = FareAmount(self.price, self.contract_client.config.base_fare)

        # Lookup existing account between client and provider
        account = self.acp_client.get_by_client_and_provider(
            self.contract_client.agent_wallet_address,
            self.provider_address,
            self.contract_client,
        )

        base_contract_addresses = {
            BASE_SEPOLIA_CONFIG.contract_address.lower(),
            BASE_MAINNET_CONFIG.contract_address.lower(),
        }

        use_simple_create = (
            self.contract_client.config.contract_address.lower()
            in base_contract_addresses
        )

        if use_simple_create or not account:
            response = self.contract_client.create_job(
                self.provider_address,
                evaluator_address or self.contract_client.agent_wallet_address,
                expired_at or datetime.utcnow(),
                fare_amount.fare.contract_address,
                fare_amount.amount,
                "",
            )
        else:
            evaluator_address = (
                Web3.to_checksum_address(evaluator_address)
                if evaluator_address
                else ZERO_ADDRESS
            )
            response = self.contract_client.create_job_with_account(
                account.id,
                evaluator_address or self.contract_client.agent_wallet_address,
                fare_amount.amount,
                fare_amount.fare.contract_address,
                expired_at or datetime.utcnow(),
            )

        job_id = self.contract_client.get_job_id(
            response,
            self.contract_client.agent_wallet_address,
            self.provider_address,
        )

        self.contract_client.create_memo(
            job_id,
            json.dumps(final_service_requirement),
            MemoType.MESSAGE,
            True,
            ACPJobPhase.NEGOTIATION,
        )

        return job_id


class ACPResourceOffering(BaseModel):
    acp_client: "VirtualsACP"
    name: str
    description: str
    url: str
    parameters: Optional[Dict[str, Any]]
    id: int
