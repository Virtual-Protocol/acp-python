import json
import math
import secrets
from datetime import datetime
import time
from typing import Dict, Any, Optional, List, TypedDict
from typing_extensions import Literal

from eth_account import Account
from pydantic import BaseModel, ConfigDict, field_validator
import requests
from web3 import Web3
from eth_account.messages import encode_typed_data
import json

from virtuals_acp.abis.erc20_abi import ERC20_ABI
from virtuals_acp.alchemy import AlchemyAccountKit
from virtuals_acp.configs.configs import ACPContractConfig, BASE_MAINNET_CONFIG
from virtuals_acp.contract_clients.base_contract_client import BaseAcpContractClient
from virtuals_acp.exceptions import ACPError
from virtuals_acp.models import ACPJobPhase, MemoType, FeeType, AcpJobX402PaymentDetails,X402PayableRequest,X402Payment,X402PayableRequirements
from virtuals_acp.constants import X402_AUTHORIZATION_TYPES, VERIFYING_CONTRACT_ADDRESS
from virtuals_acp.abis.flat_token_v2_abi import FIAT_TOKEN_V2_ABI
from virtuals_acp.utils import safe_base64_encode
from eth_account.messages import encode_defunct
from eth_utils.crypto import keccak

class ACPContractClient(BaseAcpContractClient):
    def __init__(
        self,
        wallet_private_key: str,
        agent_wallet_address: str,
        entity_id: int,
        config: ACPContractConfig = BASE_MAINNET_CONFIG,
    ):
        super().__init__(agent_wallet_address, config)
        self.account = Account.from_key(wallet_private_key)
        self.entity_id = entity_id
        self.alchemy_kit = AlchemyAccountKit(
            config, agent_wallet_address, entity_id, self.account, config.chain_id
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
            provider_address = Web3.to_checksum_address(provider_address)
            evaluator_address = Web3.to_checksum_address(evaluator_address)
            expire_timestamp = math.floor(expire_at.timestamp())

            data = self._build_user_operation(
                "createJob", [provider_address, evaluator_address, expire_timestamp]
            )
            tx_response = self._send_user_operation(data)
            
            # Handle budget in job offering -> initiate_job
            # self.set_budget_with_payment_token(
            #     job_id, budget_base_unit, payment_token_address
            # )

            return tx_response
        except Exception as e:
            raise ACPError("Failed to create job", e)

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
        secured: bool = True,
    ) -> Dict[str, Any]:
        try:
            token_address = token or self.config.base_fare.contract_address
            data = self._build_user_operation(
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
                ],
            )

            return self._send_user_operation(data)
        except Exception as e:
            raise ACPError("Failed to create payable memo", e)

    def create_job_with_account(
        self,
        account_id: int,
        provider_address: str,
        evaluator_address: str,
        budget_base_unit: int,
        payment_token_address: str,
        expired_at: datetime,
    ) -> Dict[str, Any]:
        raise ACPError("Not Supported")

    def update_account_metadata(self, account_id: int, metadata: str) -> Dict[str, Any]:
        raise ACPError("Not Supported")
    
    def create_job_with_x402(
        self,
        provider_address: str,
        evaluator_address: str,
        expire_at: datetime,
        payment_token_address: str,
        budget_base_unit: int,
        metadata: str,
    ) -> Dict[str, Any]:
        try:
            data = self._build_user_operation(
                "createJobWithX402",
                [
                    Web3.to_checksum_address(provider_address),
                    Web3.to_checksum_address(evaluator_address),
                    math.floor(expire_at.timestamp()),
                ],
            )
            payload = {
                "data": data,
                "contractAddress": self.config.contract_address,
            }
            response = self._send_user_operation(data)
            
            return response
        except Exception as e:
            raise ACPError("Failed to create job", e)

    def get_x402_payment_details(self, job_id: int) -> AcpJobX402PaymentDetails:
        """Get X402 payment details for a job."""
        try:
            # Call the contract function
            result = self.contract.functions.x402PaymentDetails(job_id).call()
            
            return AcpJobX402PaymentDetails(
                is_x402=result[0],
                is_budget_received=result[1]
            )
        except Exception as e:
            raise ACPError("Failed to get X402 payment details", e)
        
    def update_job_x402_nonce(self, job_id: int, nonce: str) -> dict:
        """Update job X402 nonce."""
        try:
            api_url = f"{self.config.acp_api_url}/jobs/{job_id}/x402-nonce"
            message = f"{job_id}-{nonce}"

            # Use eth_account.messages.encode_defunct to encode the message as an EIP-191 message (Ethereum signed message)
            eth_message = encode_defunct(text=message)
            signature = self.account.sign_message(eth_message)
            
            headers = {
                "x-signature": "0x" + signature.signature.hex(),
                "x-nonce": nonce,
                "Content-Type": "application/json",
            }
            
            payload = {
                "data": {
                    "nonce": nonce
                }
            }
            
            response = requests.post(api_url, headers=headers, json=payload)
            
            if not response.ok:
                raise ACPError(
                    "Failed to update job X402 nonce",
                    response.text
                )
            return response.json()
        except Exception as e:
            raise ACPError("Failed to update job X402 nonce", e)
        
    def generate_x402_payment(
        self, 
        payable_request: X402PayableRequest, 
        requirements: X402PayableRequirements
    ) -> X402Payment:
        """Generate X402 payment."""
        try:
            usdc_contract = self.config.base_fare.contract_address
            
            time_now = int(time.time())
            valid_after = str(time_now)
            valid_before = str(time_now + requirements.accepts[0].maxTimeoutSeconds)
            
            # Get token name and version using multicall but python not supported
            usdc_contract_instance = self.w3.eth.contract(
                address=usdc_contract,
                abi=ERC20_ABI
            )
            
            token_name = usdc_contract_instance.functions.name().call()
            
            # Get version from FIAT_TOKEN_V2_ABI
            fiat_token_contract = self.w3.eth.contract(
                address=usdc_contract,
                abi=FIAT_TOKEN_V2_ABI
            )
            token_version = fiat_token_contract.functions.version().call()
            
            # Generate random nonce
            nonce_bytes = secrets.token_bytes(32)
            nonce = "0x" + nonce_bytes.hex()
            
            message = {
                "from": self.agent_wallet_address,
                "to": payable_request.to,
                "value": str(payable_request.value),
                "validAfter": str(valid_after),
                "validBefore": str(valid_before),
                "nonce": nonce,
            }
            
            types = {
                "TransferWithAuthorization": X402_AUTHORIZATION_TYPES,
            }

            domain = {
                "name": str(token_name),
                "version": str(token_version),
                "chainId": int(self.config.chain_id),
                "verifyingContract": str(usdc_contract),
            }

            encoded_typed_data = encode_typed_data(
                    full_message={
                        "types": types,
                        "domain": domain,
                        "message": message,
                        "primaryType": "TransferWithAuthorization",
                    }
                )
            
            typed_data_hash = keccak(b"\x19\x01" + encoded_typed_data.header + encoded_typed_data.body)
            
            replay_safe_typed_data = {
                "domain": {
                    "chainId": int(self.config.chain_id),
                    "verifyingContract": VERIFYING_CONTRACT_ADDRESS,
                    "salt": "0x" + "00" * 12 + self.agent_wallet_address[2:],  # Assuming account_address is '0x...'
                },
                "types": {
                    "ReplaySafeHash": [{"name": "hash", "type": "bytes32"}]
                },
                "message": {
                    "hash": "0x" + typed_data_hash.hex()
                },
                "primaryType": "ReplaySafeHash",
            }
            
            
            signed_msg = self.account.sign_typed_data(
                full_message=replay_safe_typed_data
            )
     
            raw_signature = signed_msg.signature.hex()
            
            if not raw_signature.startswith("0x"):
                raw_signature = "0x" + raw_signature
                
            final_signature = self.pack_1271_eoa_signature(raw_signature, self.entity_id)
            

            payload = {
                "x402Version": requirements.x402Version,
                "scheme": requirements.accepts[0].scheme,
                "network": requirements.accepts[0].network,
                "payload": {                 
                    "signature": final_signature,
                    "authorization": message,
                },
            }
            
            encoded_payment = self.encode_payment(payload)
            
            return X402Payment(
                encodedPayment= encoded_payment,
                nonce=nonce
            )
        except Exception as e:
            raise ACPError("Failed to generate X402 payment", e)
        
        
    def perform_x402_request(self, url: str, budget: Optional[str] = None, signature: Optional[str] = None) -> dict:
        base_url = self.config.x402_config.url if self.config.x402_config else None

        if not base_url:
            raise ACPError("X402 URL not configured")

        headers = {}
        if signature:
            headers["x-payment"] = signature
        if budget:
            headers["x-budget"] = budget
            
        try:
            # Print the equivalent curl command for debugging
            url = f"{base_url}{url}"
            response = requests.get(url, headers=headers)
            if response.status_code == 402:
                try:
                    data = response.json()                    
                except Exception:
                    data = {}
                return {
                    "isPaymentRequired": True,
                    "data": data
                }
            else:
                response.raise_for_status()
                data = response.json()
                return {
                    "isPaymentRequired": False,
                    "data": data
                }
        except Exception as e:
            raise ACPError("Failed to perform X402 request", e)
        
    def encode_payment(self,payment_payload: Any) -> str:
        """Encode a payment payload into a base64 string, handling HexBytes and other non-serializable types."""
        from hexbytes import HexBytes

        def default(obj):
            if isinstance(obj, HexBytes):
                return obj.hex()
            if hasattr(obj, "to_dict"):
                return obj.to_dict()
            if hasattr(obj, "hex"):
                return obj.hex()
            raise TypeError(
                f"Object of type {obj.__class__.__name__} is not JSON serializable"
            )

        return safe_base64_encode(json.dumps(payment_payload, default=default))

    def pack_1271_eoa_signature(self,validation_signature: str, entity_id: int) -> str:
        if not validation_signature.startswith("0x"):
            validation_signature = "0x" + validation_signature

        # Components
        prefix = b"\x00"                         # 0x00
        entity_id_bytes = entity_id.to_bytes(4, "big")  # 4 bytes
        separator = b"\xFF"                      # 0xFF
        eoa_type = b"\x00"                       # 0x00 (EOA type)
        sig_bytes = bytes.fromhex(validation_signature[2:])

        # Concatenate all parts
        packed = prefix + entity_id_bytes + separator + eoa_type + sig_bytes

        return "0x" + packed.hex()