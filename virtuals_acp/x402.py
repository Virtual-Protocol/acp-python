import time
import requests
import base64
import json
import secrets
from typing import Any, Dict, Optional
from eth_account.messages import encode_defunct


from virtuals_acp.constants import VERIFYING_CONTRACT_ADDRESS, X402_AUTHORIZATION_TYPES
from virtuals_acp.models import (
    X402PayableRequest,
    X402PayableRequirements,
    X402Payment,
    OffChainJob,
)
from virtuals_acp.exceptions import ACPError
from virtuals_acp.configs.configs import ACPContractConfig
from virtuals_acp.abis.erc20_abi import ERC20_ABI
from virtuals_acp.abis.flat_token_v2_abi import FIAT_TOKEN_V2_ABI
from eth_account.messages import encode_typed_data
from eth_utils.crypto import keccak

from virtuals_acp.utils import safe_base64_encode



class ACPX402:
    def __init__(self, config: ACPContractConfig, session_key_client, public_client):
        """
        config: ACPContractConfig
        session_key_client: a client capable of signing messages and typed data
        public_client: web3 client able to read from contracts
        """
        self.config = config
        self.session_key_client = session_key_client
        self.public_client = public_client

    def sign_update_job_nonce_message(self, job_id: int, nonce: str) -> str:
        message = f"{job_id}-{nonce}"
        try:
            signature = self.session_key_client.sign_message(encode_defunct(text=message))
            return signature
        except Exception as e:
            raise ACPError("Failed to sign update job X402 nonce message", e)

    def update_job_nonce(self, job_id: int, nonce: str) -> OffChainJob:
        try:
            api_url = f"{self.config.acp_api_url}/api/jobs/{job_id}/x402-nonce"
            signature = self.sign_update_job_nonce_message(job_id, nonce)

            headers = {
                "x-signature": signature,
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
                raise ACPError("Failed to update job X402 nonce", response.text)

            acp_job = response.json()
            
            return acp_job
        except Exception as error:
            raise ACPError("Failed to update job X402 nonce", error)

    def generate_payment(self, payable_request: X402PayableRequest, requirements: X402PayableRequirements) -> X402Payment:
        try:
            usdc_contract = self.config.base_fare.contract_address
            time_now = int(time.time())
            valid_after = str(time_now)
            valid_before = str(time_now + requirements.accepts[0].maxTimeoutSeconds)

            # Get token name and version using multicall but python not supported
            usdc_contract_instance = self.public_client.eth.contract(
                address=usdc_contract,
                abi=ERC20_ABI
            )
            
            token_name = usdc_contract_instance.functions.name().call()
            
            # Get version from FIAT_TOKEN_V2_ABI
            fiat_token_contract = self.public_client.eth.contract(
                address=usdc_contract,
                abi=FIAT_TOKEN_V2_ABI
            )
            token_version = fiat_token_contract.functions.version().call()

            nonce_bytes = secrets.token_bytes(32)
            nonce = "0x" + nonce_bytes.hex()

            message = {
                "from": self.session_key_client.agent_wallet_address,
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

            typed_data_hash = keccak(b"\x19\x01" + encoded_typed_data.header + encoded_typed_data.body)

            replay_safe_typed_data = {
                "domain": {
                    "chainId": int(self.config.chain_id),
                    "verifyingContract": VERIFYING_CONTRACT_ADDRESS,
                    "salt": "0x" + "00" * 12 + self.session_key_client.agent_wallet_address[2:],  # Assuming account_address is '0x...'
                },
                "types": {
                    "ReplaySafeHash": [{"name": "hash", "type": "bytes32"}]
                },
                "message": {
                    "hash": "0x" + typed_data_hash.hex()
                },
                "primaryType": "ReplaySafeHash",
            }
            
            signed_msg = self.session_key_client.sign_typed_data(
                full_message=replay_safe_typed_data
            )
            
            raw_signature = signed_msg.signature.hex()
            
            if not raw_signature.startswith("0x"):
                raw_signature = "0x" + raw_signature
                
            final_signature = self.pack_1271_eoa_signature(raw_signature, self.session_key_client.entity_id)


            payload = {
                "x402Version": requirements.x402Version,
                "scheme": requirements.accepts[0].scheme,
                "network": requirements.accepts[0].network,
                "payload": {
                    "signature": final_signature,
                    "authorization": message
                }
            }

            encoded_payment = self.encode_payment(payload)

            return X402Payment(
                encodedPayment=encoded_payment,
                nonce=nonce
            )

        except Exception as error:
            raise ACPError("Failed to generate X402 payment", error)

    def perform_request(self, url: str, budget: Optional[str] = None, signature: Optional[str] = None) -> dict:
        base_url = self.config.x402_config.url if self.config.x402_config else None

        if not base_url or not getattr(base_url, "url", None):
            raise ACPError("X402 URL not configured")
        
        try:
            headers = {}
            if signature:
                headers["x-payment"] = signature
            if budget:
                headers["x-budget"] = str(budget)

            res = requests.get(f"{base_url}{url}", headers=headers)
            if res.status_code == 402:
                try:
                    data = res.json()                    
                except Exception:
                    data = {}
                return {
                    "isPaymentRequired": True,
                    "data": data
                }
            else :
                res.raise_for_status()
                data = res.json()
                return {
                    "isPaymentRequired": False,
                    "data": data
                }
        except Exception as error:
            raise ACPError("Failed to perform X402 request", error)
        
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