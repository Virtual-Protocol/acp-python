import secrets
from typing import Dict, Any, List, Optional

from eth_account import Account
from web3 import Web3

from virtuals_acp.abis.job_manager import JOB_MANAGER_ABI
from virtuals_acp.alchemy import AlchemyAccountKit
from virtuals_acp.configs.configs import ACPContractConfig, BASE_MAINNET_CONFIG_V2
from virtuals_acp.contract_clients.base_contract_client import BaseAcpContractClient
from virtuals_acp.exceptions import ACPError
from virtuals_acp.models import AcpJobX402PaymentDetails, OffChainJob, OperationPayload, X402PayableRequest, X402PayableRequirements, X402Payment
from virtuals_acp.x402 import ACPX402


class ACPContractClientV2(BaseAcpContractClient):
    def __init__(
        self,
        agent_wallet_address: str,
        wallet_private_key: str,
        entity_id: int,
        config: ACPContractConfig = BASE_MAINNET_CONFIG_V2,
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
        self.x402 = ACPX402(config, self.account, self.w3, self.agent_wallet_address, self.entity_id)
        


        def multicall_read(
            w3: Web3, contract_address: str, abi: list[Dict[str, Any]], calls: list[str]
        ):
            contract = w3.eth.contract(
                address=Web3.to_checksum_address(contract_address), abi=abi
            )
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
        
    def getAcpVersion(self) -> str:
        return "2"

    def _get_random_nonce(self, bits: int = 152) -> int:
        """Generate a random bigint nonce."""
        bytes_len = bits // 8
        random_bytes = secrets.token_bytes(bytes_len)
        return int.from_bytes(random_bytes, byteorder="big")

    def handle_operation(self, trx_data: List[OperationPayload]) -> Dict[str, Any]:
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
            raise Exception("No logs found for JobCreated event")

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
            raise Exception(
                "No logs found for JobCreated event with provider and client addresses"
            )

        return int(created_job_log["args"]["jobId"])
    
    def update_job_x402_nonce(self, job_id: int, nonce: str) -> OffChainJob:
        """Update job X402 nonce."""
        try:
            return self.x402.update_job_nonce(job_id, nonce)
        except Exception as e:
            raise ACPError("Failed to update job X402 nonce", e)

    def generate_x402_payment(
        self, 
        payable_request: X402PayableRequest, 
        requirements: X402PayableRequirements
    ) -> X402Payment:
        """Generate X402 payment."""
        try:
            return self.x402.generate_payment(payable_request, requirements)
        except Exception as e:
            raise ACPError("Failed to generate X402 payment", e)
        
    def perform_x402_request(self, url: str, version: str, budget: Optional[str] = None, signature: Optional[str] = None) -> Dict[str, Any]:
        try:
            return self.x402.perform_request(url, version, budget, signature)
        except Exception as e:
            raise ACPError("Failed to perform X402 request", e)

    def get_x402_payment_details(self, job_id: int) -> AcpJobX402PaymentDetails:
        """Get X402 payment details for a job."""
        try:
            from virtuals_acp.abis.job_manager import JOB_MANAGER_ABI

            x402_config = self.config.x402_config
            if not x402_config or not getattr(x402_config, "url", None):
                return AcpJobX402PaymentDetails(is_x402=False, is_budget_received=False)

            # Use the job manager address & JOB_MANAGER_ABI directly
            job_manager_address = Web3.to_checksum_address(self.job_manager_address)
            if not job_manager_address:
                raise ACPError("Job manager address not provided in config.")

            job_manager_contract = self.w3.eth.contract(
                address=job_manager_address,
                abi=JOB_MANAGER_ABI,
            )

            result = job_manager_contract.functions.x402PaymentDetails(job_id).call()

            return AcpJobX402PaymentDetails(
                is_x402=result[0], is_budget_received=result[1]
            )
        except Exception as e:
            raise ACPError("Failed to get X402 payment details", e)