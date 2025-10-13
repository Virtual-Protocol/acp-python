import secrets
from typing import Dict, Any, Optional, List

from eth_account import Account
from web3 import Web3

from virtuals_acp.abis.job_manager import JOB_MANAGER_ABI
from virtuals_acp.alchemy import AlchemyAccountKit
from virtuals_acp.configs.configs import ACPContractConfig
from virtuals_acp.contract_clients.base_contract_client import BaseAcpContractClient
from virtuals_acp.exceptions import ACPError


class ACPContractClientV2(BaseAcpContractClient):
    def __init__(
        self,
        agent_wallet_address: str,
        wallet_private_key: str,
        entity_id: int,
        config: ACPContractConfig,
    ):
        super().__init__(agent_wallet_address, config)

        self.account = Account.from_key(wallet_private_key)
        self.entity_id = entity_id
        self.alchemy_kit = AlchemyAccountKit(
            config, agent_wallet_address, entity_id, self.account, config.chain_id
        )

        def multicall_read(w3: Web3, contract_address: str, abi: list[str], calls: list[str]):
            contract = w3.eth.contract(address=contract_address, abi=abi)
            results = []
            for fn_name in calls:
                fn = getattr(contract.functions, fn_name)
                results.append(fn().call())
            return results

        calls = ["jobManager", "memoManager", "accountManager"]
        job_manager, memo_manager, account_manager = multicall_read(
            self.w3, config.contract_address, config.abi, calls
        )

        if not all([job_manager, memo_manager, account_manager]):
            raise ACPError("Failed to fetch sub-manager contract addresses")
        
        self.job_manager_address = job_manager

        self.job_manager_contract = self.w3.eth.contract(
            address=self.job_manager_address, abi=JOB_MANAGER_ABI
        )

    def _get_random_nonce(self, bits: int = 152) -> int:
        """Generate a random bigint nonce."""
        bytes_len = bits // 8
        random_bytes = secrets.token_bytes(bytes_len)
        return int.from_bytes(random_bytes, byteorder="big")
    
    def _send_user_operation(
        self, method_name: str, args: list, contract_address: Optional[str] = None
    ) -> Dict[str, Any]:
        if contract_address:
            encoded_data = self.token_contract.encode_abi(method_name, args=args)
        else:
            encoded_data = self.contract.encode_abi(method_name, args=args)

        trx_data = [
            {
                "to": (
                    contract_address
                    if contract_address
                    else self.config.contract_address
                ),
                "data": encoded_data,
            }
        ]

        return self.alchemy_kit.handle_user_operation(trx_data)

    def get_job_id(
        self, response: Dict[str, Any], client_address: str, provider_address: str
    ) -> int:
        logs: List[Dict[str, Any]] = response.get("receipts", [])[0].get("logs", [])

        decoded_create_job_logs = [
            self.contract.events.JobCreated().process_log(
                {
                    "topics": log["topics"],
                    "data": log["data"],
                    "address": log["address"],
                    "logIndex": 0,
                    "transactionIndex": 0,
                    "transactionHash": "0x0000",
                    "blockHash": "0x0000",
                    "blockNumber": 0,
                }
            )
            for log in logs
            if log["topics"][0] == self.job_created_event_signature_hex
        ]

        if len(decoded_create_job_logs) == 0:
            raise ACPError("No logs found for JobCreated event")

        created_job_log = next(
            (
                log
                for log in decoded_create_job_logs
                if log["args"]["provider"] == provider_address
                and log["args"]["client"] == client_address
            ),
            None,
        )

        if not created_job_log:
            raise ACPError(
                "No logs found for JobCreated event with provider and client addresses"
            )

        return int(created_job_log["args"]["jobId"])
