import time
import secrets
from datetime import datetime
from typing import Dict, Any, Optional, List

from eth_account import Account
from web3 import Web3

from virtuals_acp.abi import JOB_MANAGER_ABI, ACP_ABI
from virtuals_acp.alchemy import AlchemyAccountKit
from virtuals_acp.configs import ACPContractConfig
from virtuals_acp.contracts.base_acp_contract_client import BaseAcpContractClient
from virtuals_acp.models import ACPJobPhase, MemoType, FeeType


class ACPContractClientV2(BaseAcpContractClient):
    MAX_RETRIES = 3
    PRIORITY_FEE_MULTIPLIER = 2
    MAX_FEE_PER_GAS = 20_000_000
    MAX_PRIORITY_FEE_PER_GAS = 21_000_000

    def __init__(
        self,
        job_manager_address: str,
        memo_manager_address: str,
        account_manager_address: str,
        agent_wallet_address: str,
        wallet_private_key: str,
        entity_id: int,
        config: ACPContractConfig,
    ):
        super().__init__(agent_wallet_address, config)

        self.job_manager_address = Web3.to_checksum_address(job_manager_address)
        self.memo_manager_address = Web3.to_checksum_address(memo_manager_address)
        self.account_manager_address = Web3.to_checksum_address(account_manager_address)

        self.account = Account.from_key(wallet_private_key)
        self.entity_id = entity_id
        self.alchemy_kit = AlchemyAccountKit(
            agent_wallet_address, entity_id, self.account, config.chain_id
        )

        self.job_manager_contract = self.w3.eth.contract(
            address=self.job_manager_address, abi=JOB_MANAGER_ABI
        )

    # --- Static Builder (like .build in Node) ---

    @classmethod
    def build(
        cls,
        wallet_private_key: str,
        entity_id: int,
        agent_wallet_address: str,
        config: ACPContractConfig,
    ):
        w3 = Web3(Web3.HTTPProvider(config.rpc_url))
        contract = w3.eth.contract(address=config.contract_address, abi=ACP_ABI)

        job_manager = contract.functions.jobManager().call()
        memo_manager = contract.functions.memoManager().call()
        account_manager = contract.functions.accountManager().call()

        if not (job_manager and memo_manager and account_manager):
            raise Exception("Failed to fetch sub-manager contract addresses")

        return cls(
            job_manager_address=job_manager,
            memo_manager_address=memo_manager,
            account_manager_address=account_manager,
            agent_wallet_address=agent_wallet_address,
            wallet_private_key=wallet_private_key,
            entity_id=entity_id,
            config=config,
        )

    # --- Helpers ---

    def _get_random_nonce(self, bits: int = 152) -> int:
        bytes_len = bits // 8
        random_bytes = secrets.token_bytes(bytes_len)
        return int.from_bytes(random_bytes, byteorder="big")

    def _calculate_gas_fees(self) -> int:
        return int(
            self.MAX_FEE_PER_GAS
            + self.MAX_PRIORITY_FEE_PER_GAS * max(0, self.PRIORITY_FEE_MULTIPLIER - 1)
        )

    # --- Core User Operation Logic ---

    def handle_operation(
        self, encoded_data: str, contract_address: Optional[str] = None, value: Optional[int] = None
    ) -> Dict[str, Any]:
        contract_address = contract_address or self.config.contract_address
        payload = [
            {
                "to": contract_address,
                "data": encoded_data,
                **({"value": value} if value else {}),
                "nonce": self._get_random_nonce(),
            }
        ]

        retries = self.MAX_RETRIES
        last_error = None

        while retries > 0:
            try:
                if retries < self.MAX_RETRIES:
                    gas_fees = self._calculate_gas_fees()
                    payload[0]["maxFeePerGas"] = f"0x{gas_fees:x}"

                response = self.alchemy_kit.handle_user_operation(payload)
                return response
            except Exception as e:
                last_error = e
                retries -= 1
                if retries > 0:
                    time.sleep(2 * retries)
                else:
                    raise Exception("Failed to send user operation") from last_error

    # --- Event Decoding ---

    def get_job_id(
        self, response: Dict[str, Any], client_address: str, provider_address: str
    ) -> int:
        logs = response.get("receipts", [])[0].get("logs", [])
        decoded_events = [
            self.job_manager_contract.events.JobCreated().process_log(
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
            if log["address"].lower() == self.job_manager_address.lower()
        ]

        for event in decoded_events:
            args = event["args"]
            if (
                args["client"].lower() == client_address.lower()
                and args["provider"].lower() == provider_address.lower()
            ):
                return int(args["jobId"])

        raise Exception("Failed to find JobCreated event in logs")

    # --- Job Logic (Example) ---

    def create_job(
        self,
        provider_address: str,
        evaluator_address: str,
        expire_at: datetime,
        payment_token_address: str,
        budget_base_unit: int,
        metadata: str = "",
    ) -> Dict[str, Any]:
        try:
            encoded = self.job_manager_contract.encode_abi(
                "createJob",
                [
                    Web3.to_checksum_address(provider_address),
                    Web3.to_checksum_address(evaluator_address),
                    int(expire_at.timestamp()),
                    Web3.to_checksum_address(payment_token_address),
                    int(budget_base_unit),
                    metadata,
                ],
            )

            tx_response = self.handle_operation(encoded, self.job_manager_address)
            job_id = self.get_job_id(tx_response, self.agent_wallet_address, provider_address)

            return {"tx_response": tx_response, "job_id": job_id}
        except Exception as e:
            raise Exception("Failed to create job") from e
