from typing import Any, Dict
import json
from virtuals_acp.contract_clients.base_contract_client import BaseAcpContractClient
from virtuals_acp.models import OperationPayload


class ACPAccount:
    def __init__(
        self,
        contract_client: BaseAcpContractClient,
        id: int,
        client_address: str,
        provider_address: str,
        metadata: Dict[str, Any],
    ):
        self.contract_client = contract_client
        self.id = id
        self.client_address = client_address
        self.provider_address = provider_address
        self.metadata = metadata

    def update_metadata(self, metadata: Dict[str, Any]) -> OperationPayload:
        result = self.contract_client.update_account_metadata(
            self.id,
            json.dumps(metadata),
        )
        return result
