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
            config=config,
            agent_wallet_address=agent_wallet_address,
            entity_id=entity_id,
            owner_account=self.account,
            chain_id=config.chain_id,
        )
        self.w3 = Web3(Web3.HTTPProvider(config.rpc_url))

        def multicall_read(
            w3: Web3, contract_address: str, abi: list[str], calls: list[str]
        ):
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

        self.job_manager_address = Web3.to_checksum_address(job_manager)

        self.job_manager_contract = self.w3.eth.contract(
            address=self.job_manager_address, abi=JOB_MANAGER_ABI
        )

    def _get_random_nonce(self, bits: int = 152) -> int:
        """Generate a random bigint nonce."""
        bytes_len = bits // 8
        random_bytes = secrets.token_bytes(bytes_len)
        return int.from_bytes(random_bytes, byteorder="big")

    def _send_user_operation(self, trx_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self.alchemy_kit.handle_user_operation(trx_data)

    def get_job_id(
        self, response: Dict[str, Any], client_address: str, provider_address: str
    ) -> int:
        logs: List[Dict[str, Any]] = response.get("receipts", [])[0].get("logs", [])

        job_manager_logs = [
            log
            for log in logs
            if log["address"].lower() == self.job_manager_address.lower()
        ]

        decoded_logs = []
        for log in job_manager_logs:
            try:
                event = self.job_manager_contract.events.JobCreated().process_log(
                    {
                        "topics": log["topics"],
                        "data": log["data"],
                        "address": log["address"],
                        "logIndex": 0,
                        "transactionIndex": 0,
                        "transactionHash": "0x0",
                        "blockHash": "0x0",
                        "blockNumber": 0,
                    }
                )
                decoded_logs.append(event)
            except Exception:
                continue

        if not decoded_logs:
            raise ACPError("No JobCreated events decoded from JobManager logs")

        for event in decoded_logs:
            if (
                event["args"]["provider"].lower() == provider_address.lower()
                and event["args"]["client"].lower() == client_address.lower()
            ):
                return int(event["args"]["jobId"])

        raise ACPError("No JobCreated event matched given client/provider addresses")
