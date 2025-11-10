import time
import requests
import secrets
from typing import Any, Dict, Optional
from eth_account.messages import encode_defunct


from virtuals_acp.constants import (
    HTTP_STATUS_CODES_X402,
    VERIFYING_CONTRACT_ADDRESS,
    X402_AUTHORIZATION_TYPES,
)
from virtuals_acp.models import (
    X402PayableRequest,
    X402PayableRequirements,
    X402Payment,
    OffChainJob,
    X402PaymentPayload,
)
from virtuals_acp.exceptions import ACPError
from virtuals_acp.configs.configs import ACPContractConfig
from virtuals_acp.abis.erc20_abi import ERC20_ABI
from virtuals_acp.abis.flat_token_v2_abi import FIAT_TOKEN_V2_ABI
from eth_account.messages import encode_typed_data
from eth_utils.crypto import keccak

from virtuals_acp.utils import safe_base64_encode


class ACPX402:
    def __init__(
        self,
        config: ACPContractConfig,
        session_key_client,
        public_client,
        agent_wallet_address: str,
        entity_id: int,
    ):
        """
        config: ACPContractConfig
        session_key_client: a client capable of signing messages and typed data
        public_client: web3 client able to read from contracts
        """
        self.config = config
        self.session_key_client = session_key_client
        self.public_client = public_client
        self.agent_wallet_address = agent_wallet_address
        self.entity_id = entity_id

    def sign_update_job_nonce_message(self, job_id: int, nonce: str) -> str:
        message = f"{job_id}-{nonce}"
        try:
            signature = self.session_key_client.sign_message(
                encode_defunct(text=message)
            )
            return signature
        except Exception as e:
            raise ACPError("Failed to sign update job X402 nonce message", e)

    def update_job_nonce(self, job_id: int, nonce: str) -> OffChainJob:
        """Update job X402 nonce."""
        try:
            api_url = f"{self.config.acp_api_url}/jobs/{job_id}/x402-nonce"
            message = f"{job_id}-{nonce}"

            # Use eth_account.messages.encode_defunct to encode the message as an EIP-191 message (Ethereum signed message)
            eth_message = encode_defunct(text=message)
            signature = self.session_key_client.sign_message(eth_message)

            headers = {
                "x-signature": "0x" + signature.signature.hex(),
                "x-nonce": nonce,
                "Content-Type": "application/json",
            }

            payload = {"data": {"nonce": nonce}}

            response = requests.post(api_url, headers=headers, json=payload)

            if not response.ok:
                raise ACPError("Failed to update job X402 nonce", response.text)
            return response.json()
        except Exception as e:
            raise ACPError("Failed to update job X402 nonce", e)

    def generate_payment(
        self, payable_request: X402PayableRequest, requirements: X402PayableRequirements
    ) -> X402Payment:
        try:
            usdc_contract = self.config.base_fare.contract_address
            time_now = int(time.time())
            valid_after = str(time_now - 15)
            valid_before = str(time_now + requirements.accepts[0].maxTimeoutSeconds)

            # Get token name and version using multicall but python not supported
            usdc_contract_instance = self.public_client.eth.contract(
                address=usdc_contract, abi=ERC20_ABI
            )

            token_name = usdc_contract_instance.functions.name().call()

            # Get version from FIAT_TOKEN_V2_ABI
            fiat_token_contract = self.public_client.eth.contract(
                address=usdc_contract, abi=FIAT_TOKEN_V2_ABI
            )
            token_version = fiat_token_contract.functions.version().call()

            nonce_bytes = secrets.token_bytes(32)
            nonce = "0x" + nonce_bytes.hex()

            message = {
                "from": self.agent_wallet_address,
                "to": payable_request.to,
                "value": str(payable_request.value),
                "validAfter": valid_after,
                "validBefore": valid_before,
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

            typed_data_hash = keccak(
                b"\x19\x01" + encoded_typed_data.header + encoded_typed_data.body
            )

            replay_safe_typed_data = {
                "domain": {
                    "chainId": int(self.config.chain_id),
                    "verifyingContract": VERIFYING_CONTRACT_ADDRESS,
                    "salt": "0x"
                    + "00" * 12
                    + self.agent_wallet_address[
                        2:
                    ],  # Assuming account_address is '0x...'
                },
                "types": {"ReplaySafeHash": [{"name": "hash", "type": "bytes32"}]},
                "message": {"hash": "0x" + typed_data_hash.hex()},
                "primaryType": "ReplaySafeHash",
            }

            signed_msg = self.session_key_client.sign_typed_data(
                full_message=replay_safe_typed_data
            )

            raw_signature = signed_msg.signature.hex()

            if not raw_signature.startswith("0x"):
                raw_signature = "0x" + raw_signature

            final_signature = self.pack_1271_eoa_signature(
                raw_signature, self.entity_id
            )

            payload = X402PaymentPayload(
                x402_version=requirements.x402Version,
                scheme=requirements.accepts[0].scheme,
                network=requirements.accepts[0].network,
                payload={
                    "signature": final_signature,
                    "authorization": message
                }
            )

            encoded_payment = self.encode_payment(payload)

            return X402Payment(
                encodedPayment=encoded_payment,
                message=message,
                signature=final_signature,
            )

        except Exception as error:
            raise ACPError("Failed to generate X402 payment", error)

    def perform_request(
        self, url: str, version: str, budget: Optional[str] = None, signature: Optional[str] = None
    ) -> Dict[str, Any]:
        base_url = self.config.x402_config.url if self.config.x402_config else None

        if not base_url:
            raise ACPError("X402 URL not configured")

        try:
            headers = {}
            if signature:
                headers["x-payment"] = signature
            if budget:
                headers["x-budget"] = str(budget)
                
            headers["x-acp-version"] = version

            res = requests.get(f"{base_url}{url}", headers=headers, timeout=60)
            data = res.json()                    
            
            if not res.ok and res.status_code != HTTP_STATUS_CODES_X402["Payment Required"]:
                raise ACPError("Invalid response status code for X402 request", data)
            
            return {
                "isPaymentRequired": res.status_code == HTTP_STATUS_CODES_X402["Payment Required"],
                "data": data
            }
        except Exception as error:
            raise ACPError("Failed to perform X402 request", error)

    def encode_payment(self, payment_payload: X402PaymentPayload) -> str:
        return safe_base64_encode(payment_payload.model_dump_json())

    def pack_1271_eoa_signature(self, validation_signature: str, entity_id: int) -> str:
        if not validation_signature.startswith("0x"):
            validation_signature = "0x" + validation_signature

        # Components
        prefix = b"\x00"  # 0x00
        entity_id_bytes = entity_id.to_bytes(4, "big")  # 4 bytes
        separator = b"\xff"  # 0xFF
        eoa_type = b"\x00"  # 0x00 (EOA type)
        sig_bytes = bytes.fromhex(validation_signature[2:])

        # Concatenate all parts
        packed = prefix + entity_id_bytes + separator + eoa_type + sig_bytes

        return "0x" + packed.hex()
