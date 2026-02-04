import pytest
from unittest.mock import MagicMock, patch
from eth_account.messages import SignableMessage

from virtuals_acp.x402 import ACPX402
from virtuals_acp.models import (
    X402PayableRequest,
    X402PayableRequirements,
    X402Payment,
    X402PaymentPayload,
)
from virtuals_acp.exceptions import ACPError
from virtuals_acp.configs.configs import ACPContractConfig, X402Config
from virtuals_acp.fare import Fare


class TestACPX402:
    """Test suite for ACPX402 class"""

    @pytest.fixture
    def mock_config(self):
        """Create a mock ACP contract config"""
        config = MagicMock(spec=ACPContractConfig)
        config.base_fare = Fare(
            "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6)
        config.chain_id = "8453"
        config.acp_api_url = "https://api.example.com"
        config.x402_config = X402Config(url="https://x402.example.com")
        return config

    @pytest.fixture
    def mock_session_key_client(self):
        """Create a mock session key client for signing"""
        client = MagicMock()
        mock_signature = MagicMock()
        mock_signature.signature = MagicMock()
        mock_signature.signature.hex.return_value = "abcd1234"
        client.sign_message.return_value = mock_signature
        client.sign_typed_data.return_value = mock_signature
        return client

    @pytest.fixture
    def mock_public_client(self):
        """Create a mock Web3 public client"""
        client = MagicMock()
        return client

    @pytest.fixture
    def x402_instance(self, mock_config, mock_session_key_client, mock_public_client):
        """Create an ACPX402 instance for testing"""
        return ACPX402(
            config=mock_config,
            session_key_client=mock_session_key_client,
            public_client=mock_public_client,
            agent_wallet_address="0x1234567890123456789012345678901234567890",
            entity_id=12345,
        )

    class TestInitialization:
        """Test ACPX402 initialization"""

        def test_should_initialize_with_all_parameters(
            self, mock_config, mock_session_key_client, mock_public_client
        ):
            """Should correctly initialize with all parameters"""
            x402 = ACPX402(
                config=mock_config,
                session_key_client=mock_session_key_client,
                public_client=mock_public_client,
                agent_wallet_address="0x1234567890123456789012345678901234567890",
                entity_id=12345,
            )

            assert x402.config is mock_config
            assert x402.session_key_client is mock_session_key_client
            assert x402.public_client is mock_public_client
            assert x402.agent_wallet_address == "0x1234567890123456789012345678901234567890"
            assert x402.entity_id == 12345

    class TestSignUpdateJobNonceMessage:
        """Test sign_update_job_nonce_message method"""

        def test_should_sign_message_with_job_id_and_nonce(
            self, x402_instance, mock_session_key_client
        ):
            """Should sign message in format 'job_id-nonce'"""
            with patch('virtuals_acp.x402.encode_defunct') as mock_encode:
                mock_signable = MagicMock(spec=SignableMessage)
                mock_encode.return_value = mock_signable

                result = x402_instance.sign_update_job_nonce_message(
                    123, "abc123")

                # Verify encode_defunct was called with correct message
                mock_encode.assert_called_once_with(text="123-abc123")
                # Verify session key client signed the message
                mock_session_key_client.sign_message.assert_called_once_with(
                    mock_signable)
                # Verify signature was returned
                assert result == mock_session_key_client.sign_message.return_value

        def test_should_raise_error_when_signing_fails(
            self, x402_instance, mock_session_key_client
        ):
            """Should raise ACPError when signing fails"""
            mock_session_key_client.sign_message.side_effect = Exception(
                "Signing failed")

            with pytest.raises(ACPError, match="Failed to sign update job X402 nonce message"):
                x402_instance.sign_update_job_nonce_message(123, "abc123")

    class TestUpdateJobNonce:
        """Test update_job_nonce method"""

        def test_should_make_api_call_with_signature(
            self, x402_instance, mock_session_key_client, mock_config
        ):
            """Should make POST request to update job nonce with signature"""
            mock_response = MagicMock()
            mock_response.ok = True
            mock_response.json.return_value = {"id": 123, "nonce": "abc123"}

            with patch('virtuals_acp.x402.requests.post', return_value=mock_response) as mock_post:
                with patch('virtuals_acp.x402.encode_defunct') as mock_encode:
                    mock_signable = MagicMock()
                    mock_encode.return_value = mock_signable

                    result = x402_instance.update_job_nonce(123, "abc123")

                    # Verify API call
                    mock_post.assert_called_once()
                    call_args = mock_post.call_args
                    assert call_args[0][0] == f"{mock_config.acp_api_url}/jobs/123/x402-nonce"

                    # Verify headers
                    headers = call_args[1]['headers']
                    assert 'x-signature' in headers
                    assert headers['x-signature'].startswith('0x')
                    assert headers['x-nonce'] == "abc123"
                    assert headers['Content-Type'] == "application/json"

                    # Verify payload
                    payload = call_args[1]['json']
                    assert payload == {"data": {"nonce": "abc123"}}

                    assert result == {"id": 123, "nonce": "abc123"}

        def test_should_raise_error_when_response_not_ok(
            self, x402_instance, mock_config
        ):
            """Should raise ACPError when API response is not ok"""
            mock_response = MagicMock()
            mock_response.ok = False
            mock_response.text = "Bad request"

            with patch('virtuals_acp.x402.requests.post', return_value=mock_response):
                with patch('virtuals_acp.x402.encode_defunct'):
                    with pytest.raises(ACPError, match="Failed to update job X402 nonce"):
                        x402_instance.update_job_nonce(123, "abc123")

        def test_should_raise_error_when_exception_occurs(self, x402_instance):
            """Should raise ACPError when exception occurs"""
            with patch('virtuals_acp.x402.requests.post', side_effect=Exception("Network error")):
                with patch('virtuals_acp.x402.encode_defunct'):
                    with pytest.raises(ACPError, match="Failed to update job X402 nonce"):
                        x402_instance.update_job_nonce(123, "abc123")

    class TestGeneratePayment:
        """Test generate_payment method"""

        @pytest.fixture
        def mock_payable_request(self):
            """Create a mock payable request"""
            return X402PayableRequest(
                to="0x7777777777777777777777777777777777777777",
                value=1000000,
                maxTimeoutSeconds=300,
                asset="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
            )

        @pytest.fixture
        def mock_requirements(self):
            """Create mock X402 payment requirements"""
            return X402PayableRequirements(
                x402Version=1,
                error="",
                accepts=[{
                    "scheme": "eip-3009",
                    "network": "base",
                    "resource": "0x1111111111111111111111111111111111111111",
                    "description": "Payment for AI service",
                    "mimeType": "application/json",
                    "payTo": "0x1111111111111111111111111111111111111111",
                    "maxAmountRequired": "1000000",
                    "maxTimeoutSeconds": 300,
                    "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                    "extra": {"name": "AI Service Payment", "version": "1.0.0"},
                    "outputSchema": {}
                }]
            )

        def test_should_generate_payment_with_correct_structure(
            self, x402_instance, mock_payable_request, mock_requirements, mock_public_client
        ):
            """Should generate X402 payment with correct structure"""
            # Mock contract calls
            mock_usdc_contract = MagicMock()
            mock_usdc_contract.functions.name().call.return_value = "USD Coin"

            mock_fiat_contract = MagicMock()
            mock_fiat_contract.functions.version().call.return_value = "2"

            mock_public_client.eth.contract.side_effect = [
                mock_usdc_contract, mock_fiat_contract]

            with patch('virtuals_acp.x402.time.time', return_value=1000000):
                with patch('virtuals_acp.x402.secrets.token_bytes', return_value=b'\x00' * 32):
                    with patch('virtuals_acp.x402.encode_typed_data') as mock_encode:
                        mock_encoded = MagicMock()
                        mock_encoded.header = b'\x00' * 32
                        mock_encoded.body = b'\x00' * 32
                        mock_encode.return_value = mock_encoded

                        with patch('virtuals_acp.x402.keccak', return_value=b'\x00' * 32):
                            result = x402_instance.generate_payment(
                                mock_payable_request,
                                mock_requirements
                            )

            assert isinstance(result, X402Payment)
            assert result.encodedPayment is not None
            assert result.message is not None
            assert result.signature is not None
            assert result.message["from"] == x402_instance.agent_wallet_address
            assert result.message["to"] == mock_payable_request.to
            assert result.message["value"] == str(mock_payable_request.value)
            assert "nonce" in result.message

        def test_should_raise_error_when_contract_call_fails(
            self, x402_instance, mock_payable_request, mock_requirements, mock_public_client
        ):
            """Should raise ACPError when contract call fails"""
            mock_public_client.eth.contract.side_effect = Exception(
                "Contract error")

            with pytest.raises(ACPError, match="Failed to generate X402 payment"):
                x402_instance.generate_payment(
                    mock_payable_request, mock_requirements)

    class TestPerformRequest:
        """Test perform_request method"""

        def test_should_make_get_request_with_budget_and_signature(
            self, x402_instance, mock_config
        ):
            """Should make GET request with budget and signature headers"""
            mock_response = MagicMock()
            mock_response.ok = True
            mock_response.status_code = 200
            mock_response.json.return_value = {"result": "success"}

            with patch('virtuals_acp.x402.requests.get', return_value=mock_response) as mock_get:
                result = x402_instance.perform_request(
                    url="/acp-budget",
                    version="1.0.0",
                    budget="100.0",
                    signature="0xabcd1234"
                )

                # Verify request
                mock_get.assert_called_once()
                call_args = mock_get.call_args
                assert call_args[0][0] == f"{mock_config.x402_config.url}/acp-budget"

                # Verify headers
                headers = call_args[1]['headers']
                assert headers['x-payment'] == "0xabcd1234"
                assert headers['x-budget'] == "100.0"
                assert headers['x-acp-version'] == "1.0.0"

                # Verify result
                assert result["isPaymentRequired"] is False
                assert result["data"] == {"result": "success"}

        def test_should_return_payment_required_on_402_status(
            self, x402_instance, mock_config
        ):
            """Should return isPaymentRequired=True on 402 status code"""
            mock_response = MagicMock()
            mock_response.ok = False
            mock_response.status_code = 402
            mock_response.json.return_value = {"accepts": []}

            with patch('virtuals_acp.x402.requests.get', return_value=mock_response):
                result = x402_instance.perform_request(
                    url="/acp-budget",
                    version="1.0.0"
                )

                assert result["isPaymentRequired"] is True
                assert result["data"] == {"accepts": []}

        def test_should_make_request_without_optional_headers(
            self, x402_instance, mock_config
        ):
            """Should make request without budget and signature when not provided"""
            mock_response = MagicMock()
            mock_response.ok = True
            mock_response.status_code = 200
            mock_response.json.return_value = {"result": "success"}

            with patch('virtuals_acp.x402.requests.get', return_value=mock_response) as mock_get:
                x402_instance.perform_request(url="/test", version="1.0.0")

                headers = mock_get.call_args[1]['headers']
                assert 'x-payment' not in headers
                assert 'x-budget' not in headers
                assert 'x-acp-version' in headers

        def test_should_raise_error_when_x402_config_missing(self, x402_instance):
            """Should raise ACPError when X402 config is not set"""
            x402_instance.config.x402_config = None

            with pytest.raises(ACPError, match="X402 URL not configured"):
                x402_instance.perform_request(url="/test", version="1.0.0")

        def test_should_raise_error_on_invalid_status_code(
            self, x402_instance, mock_config
        ):
            """Should raise ACPError on invalid status code (not 2xx or 402)"""
            mock_response = MagicMock()
            mock_response.ok = False
            mock_response.status_code = 500
            mock_response.json.return_value = {
                "error": "Internal server error"}

            with patch('virtuals_acp.x402.requests.get', return_value=mock_response):
                with pytest.raises(ACPError, match="Invalid response status code for X402 request"):
                    x402_instance.perform_request(url="/test", version="1.0.0")

        def test_should_raise_error_on_request_exception(self, x402_instance):
            """Should raise ACPError when request raises exception"""
            with patch('virtuals_acp.x402.requests.get', side_effect=Exception("Network error")):
                with pytest.raises(ACPError, match="Failed to perform X402 request"):
                    x402_instance.perform_request(url="/test", version="1.0.0")

    class TestEncodePayment:
        """Test encode_payment method"""

        def test_should_encode_payment_payload_to_base64(self, x402_instance):
            """Should encode payment payload to base64"""
            payload = X402PaymentPayload(
                x402_version=1,
                scheme="eip-3009",
                network="base",
                payload={"signature": "0xabcd", "authorization": {}}
            )

            with patch('virtuals_acp.x402.safe_base64_encode') as mock_encode:
                mock_encode.return_value = "encoded_payload"

                result = x402_instance.encode_payment(payload)

                # Verify safe_base64_encode was called with JSON string
                mock_encode.assert_called_once()
                call_arg = mock_encode.call_args[0][0]
                # Should be JSON string of payload
                assert isinstance(call_arg, str)

                assert result == "encoded_payload"

    class TestPack1271EoaSignature:
        """Test pack_1271_eoa_signature method"""

        def test_should_pack_signature_with_entity_id(self, x402_instance):
            """Should pack signature with entity ID in correct format"""
            signature = "0xabcd1234"
            entity_id = 12345

            result = x402_instance.pack_1271_eoa_signature(
                signature, entity_id)

            # Result should start with 0x
            assert result.startswith("0x")

            # Result should contain packed components:
            # - 0x00 (prefix)
            # - entity_id (4 bytes)
            # - 0xFF (separator)
            # - 0x00 (EOA type)
            # - signature bytes
            result_bytes = bytes.fromhex(result[2:])

            assert result_bytes[0] == 0x00  # Prefix
            assert int.from_bytes(
                result_bytes[1:5], 'big') == entity_id  # Entity ID
            assert result_bytes[5] == 0xFF  # Separator
            assert result_bytes[6] == 0x00  # EOA type

        def test_should_handle_signature_without_0x_prefix(self, x402_instance):
            """Should handle signature without 0x prefix"""
            signature = "abcd1234"
            entity_id = 12345

            result = x402_instance.pack_1271_eoa_signature(
                signature, entity_id)

            assert result.startswith("0x")
            # Should work correctly even without 0x prefix

        def test_should_pack_with_different_entity_ids(self, x402_instance):
            """Should correctly pack different entity IDs"""
            signature = "0xabcd1234"

            result1 = x402_instance.pack_1271_eoa_signature(signature, 1)
            result2 = x402_instance.pack_1271_eoa_signature(signature, 255)
            result3 = x402_instance.pack_1271_eoa_signature(signature, 65535)

            # Results should be different for different entity IDs
            assert result1 != result2
            assert result2 != result3
            assert result1 != result3

        def test_should_handle_large_entity_id(self, x402_instance):
            """Should handle large entity ID (up to 4 bytes)"""
            signature = "0xabcd1234"
            entity_id = 16777215  # Max 4-byte value

            result = x402_instance.pack_1271_eoa_signature(
                signature, entity_id)

            result_bytes = bytes.fromhex(result[2:])
            packed_entity_id = int.from_bytes(result_bytes[1:5], 'big')
            assert packed_entity_id == entity_id
