from typing import Any, Dict
import json
from virtuals_acp.contract_clients.base_contract_client import BaseAcpContractClient


class ACPAccount:
    def __init__(
        self,
        contract_manager: BaseAcpContractClient,
        id: int,
        client_address: str,
        provider_address: str,
        metadata: Dict[str, Any],
    ):
        self.contract_manager = contract_manager
        self.id = id
        self.client_address = client_address
        self.provider_address = provider_address
        self.metadata = metadata

    def update_metadata(self, metadata: Dict[str, Any]) -> str:
        hash_ = self.contract_manager.update_account_metadata(
            self.id,
            json.dumps(metadata),
        )
        return hash_
