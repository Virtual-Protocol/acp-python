import time
import math
import secrets
from datetime import datetime
from typing import Dict, Any, Optional, List

from eth_account import Account
from web3 import Web3

from virtuals_acp.alchemy import AlchemyAccountKit
from virtuals_acp.configs import ACPContractConfig
from virtuals_acp.models import ACPJobPhase, MemoType, FeeType
from virtuals_acp.contracts.base_acp_contract_client import BaseAcpContractClient


class ACPContractClient(BaseAcpContractClient):
    MAX_RETRIES = 3
    PRIORITY_FEE_MULTIPLIER = 2
    MAX_FEE_PER_GAS = 20_000_000
    MAX_PRIORITY_FEE_PER_GAS = 21_000_000

    def __init__(
        self,
        wallet_private_key: str,
        agent_wallet_address: str,
        entity_id: int,
        config: ACPContractConfig,
    ):
        super().__init__(agent_wallet_address, config)
        self.account = Account.from_key(wallet_private_key)
        self.entity_id = entity_id
        self.alchemy_kit = AlchemyAccountKit(
            agent_wallet_address, entity_id, self.account, config.chain_id
        )

    # --- Nonce and Fee Helpers ---

    def _get_random_nonce(self, bits: int = 152) -> int:
        """Generate a random bigint nonce."""
        bytes_len = bits // 8
        random_bytes = secrets.token_bytes(bytes_len)
        return int.from_bytes(random_bytes, byteorder="big")

    def _calculate_gas_fees(self) -> int:
        return int(
            self.MAX_FEE_PER_GAS
            + self.MAX_PRIORITY_FEE_PER_GAS * max(0, self.PRIORITY_FEE_MULTIPLIER - 1)
        )

    # --- Abstract Implementations ---

    def handle_operation(
        self, encoded_data: str, contract_address: str, value: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Sends user operation via AlchemyAccountKit with retry and gas adjustments.
        """
        payload = [
            {
                "to": contract_address,
                "data": encoded_data,
                **({"value": value} if value else {}),
            }
        ]

        retries = self.MAX_RETRIES
        last_error = None

        while retries > 0:
            try:
                if retries < self.MAX_RETRIES:
                    # retry with adjusted gas
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

    def get_job_id(
        self, response: Dict[str, Any], client_address: str, provider_address: str
    ) -> int:
        """
        Extracts jobId from logs after a JobCreated event.
        """
        logs = response.get("receipts", [])[0].get("logs", [])
        decoded = [
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
            if log["topics"][0] == self.job_created_signature
        ]

        for log in decoded:
            args = log["args"]
            if (
                args["provider"].lower() == provider_address.lower()
                and args["client"].lower() == client_address.lower()
            ):
                return int(args["jobId"])

        raise Exception("Failed to find JobCreated event in logs")

    # --- Contract Logic Overrides ---

    def create_job(
        self,
        provider_address: str,
        evaluator_address: str,
        expire_at: datetime,
        payment_token_address: str,
        budget_base_unit: int,
        metadata: str = "",
    ) -> Dict[str, Any]:
        """
        Equivalent to TypeScript createJob + setBudgetWithPaymentToken
        """
        try:
            encoded = self.contract.encode_abi(
                "createJob",
                [
                    Web3.to_checksum_address(provider_address),
                    Web3.to_checksum_address(evaluator_address),
                    int(expire_at.timestamp()),
                ],
            )

            tx_response = self.handle_operation(encoded, self.config.contract_address)
            job_id = self.get_job_id(
                tx_response, self.agent_wallet_address, provider_address
            )

            self.set_budget_with_payment_token(job_id, budget_base_unit, payment_token_address)

            return {"tx_response": tx_response, "job_id": job_id}
        except Exception as e:
            raise Exception("Failed to create job") from e

    def create_payable_memo(
        self,
        job_id: int,
        content: str,
        amount_base_unit: int,
        recipient: str,
        fee_amount_base_unit: int,
        fee_type: FeeType,
        next_phase: ACPJobPhase,
        memo_type: MemoType,
        expired_at: datetime,
        token: Optional[str] = None,
        is_secured: bool = True,
    ) -> Dict[str, Any]:
        try:
            token_address = token or self.config.base_fare.contract_address
            encoded = self.contract.encode_abi(
                "createPayableMemo",
                [
                    job_id,
                    content,
                    token_address,
                    amount_base_unit,
                    Web3.to_checksum_address(recipient),
                    fee_amount_base_unit,
                    fee_type.value,
                    memo_type.value,
                    next_phase.value,
                    math.floor(expired_at.timestamp()),
                    is_secured,
                ],
            )

            return self.handle_operation(encoded, self.config.contract_address)
        except Exception as e:
            raise Exception("Failed to create payable memo") from e

    def create_job_with_account(
        self,
        account_id: int,
        provider_address: str,
        evaluator_address: str,
        budget_base_unit: int,
        payment_token_address: str,
        expired_at: datetime,
    ) -> Dict[str, Any]:
        try:
            encoded = self.contract.encode_abi(
                "createJobWithAccount",
                [
                    account_id,
                    Web3.to_checksum_address(evaluator_address),
                    int(budget_base_unit),
                    Web3.to_checksum_address(payment_token_address),
                    int(expired_at.timestamp()),
                ],
            )

            # Send the user operation through Alchemy or whatever backend handles operations
            tx_response = self.handle_operation(encoded, self.config.contract_address)

            # Extract jobId from JobCreated event logs
            job_id = self.get_job_id(
                tx_response,
                self.agent_wallet_address,
                provider_address,
            )

            return {
                "tx_response": tx_response,
                "job_id": job_id,
            }

        except Exception as e:
            raise Exception("Failed to create job with account") from e


    def update_account_metadata(self, account_id: int, metadata: str) -> Dict[str, Any]:
        try:
            encoded = self.contract.encode_abi(
                "updateAccountMetadata",
                [int(account_id), metadata],
            )

            tx_response = self.handle_operation(encoded, self.config.contract_address)

            return {
                "tx_response": tx_response,
                "account_id": account_id,
                "metadata": metadata,
            }

        except Exception as e:
            raise Exception("Failed to update account metadata") from e
