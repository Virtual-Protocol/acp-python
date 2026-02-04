import pytest
from unittest.mock import Mock, MagicMock, patch
from virtuals_acp.contract_clients.contract_client_v2 import ACPContractClientV2
from virtuals_acp.exceptions import ACPError
from virtuals_acp.models import AcpJobX402PaymentDetails


class TestAcpContractClientV2:
    """Unit tests for ACP Contract Client V2"""

    @pytest.fixture
    def contract_client(self):
        """
        Pytest fixture - equivalent to Jest's beforeEach()
        Creates a mock contract client before each test
        """
        # Create a minimal mock client that only has the methods we need to test
        client = Mock(spec=ACPContractClientV2)

        # Bind actual methods we want to test (not mocked)
        client._get_random_nonce = ACPContractClientV2._get_random_nonce.__get__(
            client, ACPContractClientV2)
        client.get_job_id = ACPContractClientV2.get_job_id.__get__(
            client, ACPContractClientV2)
        client.update_job_x402_nonce = ACPContractClientV2.update_job_x402_nonce.__get__(
            client, ACPContractClientV2)
        client.generate_x402_payment = ACPContractClientV2.generate_x402_payment.__get__(
            client, ACPContractClientV2)
        client.perform_x402_request = ACPContractClientV2.perform_x402_request.__get__(
            client, ACPContractClientV2)
        client.get_x402_payment_details = ACPContractClientV2.get_x402_payment_details.__get__(
            client, ACPContractClientV2)

        return client

    class TestRandomNonceGeneration:
        def test_should_return_a_bigint(self, contract_client):
            nonce = contract_client._get_random_nonce(152)

            # In Python, int is equivalent to TypeScript's bigint
            assert isinstance(nonce, int)

        def test_should_generate_unique_nonces(self, contract_client):
            first_nonce = contract_client._get_random_nonce(152)
            second_nonce = contract_client._get_random_nonce(152)

            assert first_nonce != second_nonce

        def test_should_use_152_as_default_bit_size(self, contract_client):
            nonce = contract_client._get_random_nonce()

            assert nonce < 2 ** 152
            assert nonce >= 0

        def test_should_handle_custom_bit_sizes(self, contract_client):
            nonce = contract_client._get_random_nonce(8)  # 8 bits = 1 byte

            assert isinstance(nonce, int)
            assert nonce < 2 ** 8  # Less than 256
            assert nonce >= 0

    class TestGetJobId:
        def test_should_return_job_id_from_transaction_receipt(self, contract_client):
            mock_client_address = "0xclient123"
            mock_provider_address = "0xprovider456"
            mock_job_id = 42

            contract_client.job_created_event_signature_hex = "0xjobcreatedevent"

            mock_contract = MagicMock()
            mock_event = MagicMock()

            mock_event.process_log.return_value = {
                "args": {
                    "jobId": mock_job_id,
                    "client": mock_client_address,
                    "provider": mock_provider_address,
                }
            }

            mock_contract.events.JobCreated.return_value = mock_event
            contract_client.contract = mock_contract

            mock_response = {
                "receipts": [{
                    "logs": [
                        {
                            "topics": ["0xjobcreatedevent"],
                            "data": "0xdata",
                            "address": "0xcontract",
                        }
                    ]
                }]
            }

            result = contract_client.get_job_id(
                mock_response,
                mock_client_address,
                mock_provider_address
            )

            assert result == mock_job_id
            assert isinstance(result, int)

        def test_should_raise_error_when_no_logs_found(self, contract_client):
            contract_client.job_created_event_signature_hex = "0xjobcreatedevent"

            mock_response = {
                "receipts": [{
                    "logs": []
                }]
            }

            with pytest.raises(Exception, match="No logs found for JobCreated event"):
                contract_client.get_job_id(
                    mock_response,
                    "0xclient",
                    "0xprovider"
                )

        def test_should_raise_error_when_no_matching_provider_client(self, contract_client):
            contract_client.job_created_event_signature_hex = "0xjobcreatedevent"

            mock_contract = MagicMock()
            mock_event = MagicMock()

            # Return log with different addresses
            mock_event.process_log.return_value = {
                "args": {
                    "jobId": 42,
                    "client": "0xwrongclient",
                    "provider": "0xwrongprovider",
                }
            }
            mock_contract.events.JobCreated.return_value = mock_event
            contract_client.contract = mock_contract

            mock_response = {
                "receipts": [{
                    "logs": [
                        {
                            "topics": ["0xjobcreatedevent"],
                            "data": "0xdata",
                            "address": "0xcontract",
                        }
                    ]
                }]
            }

            with pytest.raises(Exception, match="No logs found for JobCreated event with provider and client addresses"):
                contract_client.get_job_id(
                    mock_response,
                    "0xclient",
                    "0xprovider"
                )

    class TestX402Methods:
        def test_update_job_x402_nonce_should_delegate_to_x402(self, contract_client):
            mock_job_id = 1
            mock_nonce = "test_nonce_123"
            mock_response = {"status": "success"}

            # Mock the x402 object
            contract_client.x402 = MagicMock()
            contract_client.x402.update_job_nonce.return_value = mock_response

            # Call the method
            result = contract_client.update_job_x402_nonce(
                mock_job_id, mock_nonce)

            # Verify delegation
            contract_client.x402.update_job_nonce.assert_called_once_with(
                mock_job_id, mock_nonce)
            assert result == mock_response

        def test_update_job_x402_nonce_should_raise_acp_error_on_failure(self, contract_client):
            contract_client.x402 = MagicMock()
            contract_client.x402.update_job_nonce.side_effect = Exception(
                "X402 API failed")

            # Should raise ACPError
            with pytest.raises(ACPError, match="Failed to update job X402 nonce"):
                contract_client.update_job_x402_nonce(1, "nonce")

        def test_generate_x402_payment_should_delegate_to_x402(self, contract_client):
            mock_request = {"job_id": 1}
            mock_requirements = {"amount": 100}
            mock_payment = {"signature": "0xsig"}

            contract_client.x402 = MagicMock()
            contract_client.x402.generate_payment.return_value = mock_payment

            # Call the method
            result = contract_client.generate_x402_payment(
                mock_request, mock_requirements)

            # Verify delegation
            contract_client.x402.generate_payment.assert_called_once_with(
                mock_request, mock_requirements)
            assert result == mock_payment

        def test_generate_x402_payment_should_raise_acp_error_on_failure(self, contract_client):
            contract_client.x402 = MagicMock()
            contract_client.x402.generate_payment.side_effect = Exception(
                "Payment generation failed")

            # Should raise ACPError
            with pytest.raises(ACPError, match="Failed to generate X402 payment"):
                contract_client.generate_x402_payment({}, {})

        def test_perform_x402_request_should_delegate_to_x402(self, contract_client):
            """Should delegate to x402.perform_request"""
            mock_url = "https://example.com"
            mock_version = "v2"
            mock_budget = "100"
            mock_signature = "0xsig"
            mock_response = {"status": "success"}

            contract_client.x402 = MagicMock()
            contract_client.x402.perform_request.return_value = mock_response

            # Call the method
            result = contract_client.perform_x402_request(
                mock_url, mock_version, mock_budget, mock_signature
            )

            # Verify delegation
            contract_client.x402.perform_request.assert_called_once_with(
                mock_url, mock_version, mock_budget, mock_signature
            )
            assert result == mock_response

        def test_perform_x402_request_should_raise_acp_error_on_failure(self, contract_client):
            """Should raise ACPError when x402.perform_request fails"""
            contract_client.x402 = MagicMock()
            contract_client.x402.perform_request.side_effect = Exception(
                "Request failed")

            # Should raise ACPError
            with pytest.raises(ACPError, match="Failed to perform X402 request"):
                contract_client.perform_x402_request("url", "v2")

        def test_get_x402_payment_details_should_return_false_when_no_config(self, contract_client):
            """Should return is_x402=False when no x402 config"""
            # Mock config without x402_config
            contract_client.config = MagicMock()
            contract_client.config.x402_config = None

            result = contract_client.get_x402_payment_details(1)

            assert isinstance(result, AcpJobX402PaymentDetails)
            assert result.is_x402 is False
            assert result.is_budget_received is False

        def test_get_x402_payment_details_should_call_contract_and_return_details(self, contract_client):
            """Should call contract and return payment details"""
            mock_job_id = 123

            # Setup mocks
            contract_client.config = MagicMock()
            contract_client.config.x402_config = MagicMock()
            contract_client.config.x402_config.url = "https://x402.example.com"
            contract_client.job_manager_address = "0xjobmanager"

            # Mock Web3 and contract
            with patch('virtuals_acp.contract_clients.contract_client_v2.Web3') as mock_web3:
                mock_web3.to_checksum_address.return_value = "0xjobmanager"

                # Mock the contract call
                mock_contract = MagicMock()
                mock_contract.functions.x402PaymentDetails.return_value.call.return_value = [
                    True, False]

                contract_client.w3 = MagicMock()
                contract_client.w3.eth.contract.return_value = mock_contract

                result = contract_client.get_x402_payment_details(mock_job_id)

                # Verify contract was called with correct job_id
                mock_contract.functions.x402PaymentDetails.assert_called_once_with(
                    mock_job_id)

                # Verify result
                assert isinstance(result, AcpJobX402PaymentDetails)
                assert result.is_x402 is True
                assert result.is_budget_received is False

        def test_get_x402_payment_details_should_raise_acp_error_on_failure(self, contract_client):
            """Should raise ACPError when contract call fails"""
            contract_client.config = MagicMock()
            contract_client.config.x402_config = MagicMock()
            contract_client.config.x402_config.url = "https://x402.example.com"
            contract_client.job_manager_address = "0xjobmanager"

            # Mock contract to raise error
            contract_client.w3 = MagicMock()
            contract_client.w3.eth.contract.side_effect = Exception(
                "Contract call failed")

            # Should raise ACPError
            with pytest.raises(ACPError, match="Failed to get X402 payment details"):
                contract_client.get_x402_payment_details(1)
