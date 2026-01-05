import pytest
import json
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone
from virtuals_acp.client import VirtualsACP
from virtuals_acp.exceptions import ACPError, ACPApiError
from virtuals_acp.models import ACPJobPhase, ACPMemoStatus, MemoType

# Valid Ethereum addresses for testing
TEST_AGENT_ADDRESS = "0x1234567890123456789012345678901234567890"
TEST_CONTRACT_ADDRESS = "0xABCDEF1234567890123456789012345678901234"
TEST_PROVIDER_ADDRESS = "0x5555555555555555555555555555555555555555"


class TestAcpClient:
    @pytest.fixture
    def mock_contract_client(self):
        """Create a mock contract client"""
        client = MagicMock()
        client.agent_wallet_address = TEST_AGENT_ADDRESS
        client.config.acp_api_url = "https://api.example.com"
        client.config.contract_address = TEST_CONTRACT_ADDRESS
        client.config.chain_id = 8453  # Base Mainnet chain ID
        client.config.x402_config = None  # Not an x402 contract
        client.contract_address = TEST_CONTRACT_ADDRESS
        return client

    @pytest.fixture
    def acp_client(self, mock_contract_client):
        """Create a VirtualsACP client with mocked dependencies"""
        with patch('virtuals_acp.client.socketio.Client'):
            client = VirtualsACP(acp_contract_clients=mock_contract_client)
            return client

    class TestFetchJobList:
        """Test _fetch_job_list helper method (network layer)"""

        @patch('virtuals_acp.client.requests.get')
        def test_should_fetch_jobs_successfully(self, mock_get, acp_client):
            """Should successfully fetch job list from API"""
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "data": [
                    {"id": 123, "clientAddress": TEST_AGENT_ADDRESS},
                    {"id": 456, "providerAddress": TEST_PROVIDER_ADDRESS}
                ]
            }
            mock_get.return_value = mock_response

            url = "https://api.example.com/jobs/active?pagination[page]=1&pagination[pageSize]=10"
            jobs = acp_client._fetch_job_list(url)

            # Verify API call
            mock_get.assert_called_once_with(
                url,
                headers={"wallet-address": TEST_AGENT_ADDRESS}
            )
            mock_response.raise_for_status.assert_called_once()

            # Verify data extraction
            assert len(jobs) == 2
            assert jobs[0]["id"] == 123
            assert jobs[1]["id"] == 456

        @patch('virtuals_acp.client.requests.get')
        def test_should_return_empty_list_when_no_data(self, mock_get, acp_client):
            """Should return empty list when API returns no data"""
            mock_response = MagicMock()
            mock_response.json.return_value = {"data": []}
            mock_get.return_value = mock_response

            url = "https://api.example.com/jobs/active"
            jobs = acp_client._fetch_job_list(url)

            assert isinstance(jobs, list)
            assert len(jobs) == 0

        @patch('virtuals_acp.client.requests.get')
        def test_should_raise_error_on_network_failure(self, mock_get, acp_client):
            """Should raise ACPApiError when network request fails"""
            import requests
            mock_get.side_effect = requests.RequestException(
                "Connection failed")

            url = "https://api.example.com/jobs/active"
            with pytest.raises(ACPApiError, match="Failed to fetch ACP jobs"):
                acp_client._fetch_job_list(url)

        @patch('virtuals_acp.client.requests.get')
        def test_should_raise_error_on_http_error(self, mock_get, acp_client):
            """Should raise error when HTTP request returns error status"""
            import requests
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = requests.HTTPError(
                "404 Not Found")
            mock_get.return_value = mock_response

            url = "https://api.example.com/jobs/active"
            with pytest.raises(ACPApiError, match="Failed to fetch ACP jobs"):
                acp_client._fetch_job_list(url)

        @patch('virtuals_acp.client.requests.get')
        def test_should_raise_error_on_invalid_json(self, mock_get, acp_client):
            """Should raise ACPApiError when response is not valid JSON"""
            mock_response = MagicMock()
            mock_response.json.side_effect = ValueError("Invalid JSON")
            mock_get.return_value = mock_response

            url = "https://api.example.com/jobs/active"
            with pytest.raises(ACPApiError, match="Failed to parse ACP jobs response"):
                acp_client._fetch_job_list(url)

        @patch('virtuals_acp.client.requests.get')
        def test_should_raise_error_when_api_returns_error(self, mock_get, acp_client):
            """Should raise ACPApiError when API response contains error"""
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "error": {
                    "message": "Authentication failed"
                }
            }
            mock_get.return_value = mock_response

            url = "https://api.example.com/jobs/active"
            with pytest.raises(ACPApiError, match="Authentication failed"):
                acp_client._fetch_job_list(url)

    class TestHydrateJobs:
        """Test _hydrate_jobs helper method (data transformation layer)"""

        @patch('virtuals_acp.client.ACPJob')
        @patch('virtuals_acp.client.ACPMemo')
        def test_should_hydrate_jobs_successfully(
            self, mock_memo_class, mock_job_class, acp_client
        ):
            """Should successfully hydrate raw job data into ACPJob objects"""
            mock_job = MagicMock()
            mock_job_class.return_value = mock_job

            raw_jobs = [
                {
                    "id": 123,
                    "clientAddress": TEST_AGENT_ADDRESS,
                    "providerAddress": TEST_PROVIDER_ADDRESS,
                    "evaluatorAddress": TEST_AGENT_ADDRESS,
                    "price": "100",
                    "priceTokenAddress": TEST_CONTRACT_ADDRESS,
                    "phase": 1,
                    "context": '{"key": "value"}',
                    "contractAddress": TEST_CONTRACT_ADDRESS,
                    "netPayableAmount": "90",
                    "memos": []
                }
            ]

            jobs = acp_client._hydrate_jobs(raw_jobs, log_prefix="Test jobs")

            assert len(jobs) == 1
            assert jobs[0] == mock_job
            assert mock_job_class.call_count == 1

        @patch('virtuals_acp.client.ACPJob')
        @patch('virtuals_acp.client.ACPMemo')
        def test_should_hydrate_jobs_with_memos(
            self, mock_memo_class, mock_job_class, acp_client
        ):
            """Should properly hydrate jobs with their memos"""
            mock_memo = MagicMock()
            mock_memo_class.return_value = mock_memo
            mock_job = MagicMock()
            mock_job_class.return_value = mock_job

            raw_jobs = [
                {
                    "id": 123,
                    "clientAddress": TEST_AGENT_ADDRESS,
                    "providerAddress": TEST_PROVIDER_ADDRESS,
                    "evaluatorAddress": TEST_AGENT_ADDRESS,
                    "price": "100",
                    "priceTokenAddress": TEST_CONTRACT_ADDRESS,
                    "phase": 1,
                    "context": '{"key": "value"}',
                    "contractAddress": TEST_CONTRACT_ADDRESS,
                    "netPayableAmount": "90",
                    "memos": [
                        {
                            "id": 1,
                            "memoType": 1,
                            "content": "Test memo",
                            "nextPhase": 2,
                            "status": "PENDING",
                            "signedReason": None,
                            "expiry": None,
                            "payableDetails": None,
                            "txHash": None,
                            "signedTxHash": None
                        }
                    ]
                }
            ]

            jobs = acp_client._hydrate_jobs(raw_jobs)

            # Verify memo was created
            assert mock_memo_class.call_count == 1
            # Verify job was created
            assert mock_job_class.call_count == 1

        @patch('virtuals_acp.client.ACPJob')
        def test_should_parse_json_context(self, mock_job_class, acp_client):
            """Should parse JSON context string into dict"""
            mock_job = MagicMock()
            mock_job_class.return_value = mock_job

            raw_jobs = [
                {
                    "id": 123,
                    "clientAddress": TEST_AGENT_ADDRESS,
                    "providerAddress": TEST_PROVIDER_ADDRESS,
                    "evaluatorAddress": TEST_AGENT_ADDRESS,
                    "price": "100",
                    "priceTokenAddress": TEST_CONTRACT_ADDRESS,
                    "phase": 1,
                    "context": '{"task": "test", "value": 42}',
                    "contractAddress": TEST_CONTRACT_ADDRESS,
                    "netPayableAmount": "90",
                    "memos": []
                }
            ]

            jobs = acp_client._hydrate_jobs(raw_jobs)

            # Verify ACPJob was called with parsed context
            call_args = mock_job_class.call_args[1]
            assert call_args["context"] == {"task": "test", "value": 42}

        @patch('virtuals_acp.client.ACPJob')
        def test_should_handle_invalid_json_context(self, mock_job_class, acp_client):
            """Should set context to None when JSON parsing fails"""
            mock_job = MagicMock()
            mock_job_class.return_value = mock_job

            raw_jobs = [
                {
                    "id": 123,
                    "clientAddress": TEST_AGENT_ADDRESS,
                    "providerAddress": TEST_PROVIDER_ADDRESS,
                    "evaluatorAddress": TEST_AGENT_ADDRESS,
                    "price": "100",
                    "priceTokenAddress": TEST_CONTRACT_ADDRESS,
                    "phase": 1,
                    "context": "invalid json{{{",
                    "contractAddress": TEST_CONTRACT_ADDRESS,
                    "netPayableAmount": "90",
                    "memos": []
                }
            ]

            jobs = acp_client._hydrate_jobs(raw_jobs)

            # Verify ACPJob was called with None context
            call_args = mock_job_class.call_args[1]
            assert call_args["context"] is None

        @patch('virtuals_acp.client.ACPJob')
        def test_should_skip_malformed_jobs(self, mock_job_class, acp_client):
            """Should skip jobs that fail to hydrate and continue with valid ones"""
            # First call raises error, second succeeds
            mock_job_class.side_effect = [
                Exception("Invalid job"), MagicMock()]

            raw_jobs = [
                {
                    "id": 123,
                    # Missing required fields - will fail hydration
                },
                {
                    "id": 456,
                    "clientAddress": TEST_AGENT_ADDRESS,
                    "providerAddress": TEST_PROVIDER_ADDRESS,
                    "evaluatorAddress": TEST_AGENT_ADDRESS,
                    "price": "100",
                    "priceTokenAddress": TEST_CONTRACT_ADDRESS,
                    "phase": 1,
                    "context": None,
                    "contractAddress": TEST_CONTRACT_ADDRESS,
                    "netPayableAmount": "90",
                    "memos": []
                }
            ]

            jobs = acp_client._hydrate_jobs(raw_jobs)

            # Should return only the valid job
            assert len(jobs) == 1

    class TestGetActiveJobs:
        """Test get_active_jobs public method (integration of fetch + hydrate)"""

        @patch('virtuals_acp.client.requests.get')
        @patch('virtuals_acp.client.ACPJob')
        @patch('virtuals_acp.client.ACPMemo')
        def test_should_get_active_jobs_successfully(
            self, mock_memo_class, mock_job_class, mock_get, acp_client
        ):
            """Should successfully retrieve and hydrate active jobs"""
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "data": [
                    {
                        "id": 123,
                        "clientAddress": TEST_AGENT_ADDRESS,
                        "providerAddress": TEST_PROVIDER_ADDRESS,
                        "evaluatorAddress": TEST_AGENT_ADDRESS,
                        "price": "100",
                        "priceTokenAddress": TEST_CONTRACT_ADDRESS,
                        "phase": 1,
                        "context": '{"key": "value"}',
                        "contractAddress": TEST_CONTRACT_ADDRESS,
                        "netPayableAmount": "90",
                        "memos": []
                    }
                ]
            }
            mock_get.return_value = mock_response

            mock_job = MagicMock()
            mock_job_class.return_value = mock_job

            jobs = acp_client.get_active_jobs(page=1, page_size=10)

            # Verify the API was called with correct URL
            expected_url = "https://api.example.com/jobs/active?pagination[page]=1&pagination[pageSize]=10"
            mock_get.assert_called_once_with(
                expected_url,
                headers={"wallet-address": TEST_AGENT_ADDRESS}
            )

            # Verify jobs were returned
            assert isinstance(jobs, list)
            assert len(jobs) == 1

        @patch('virtuals_acp.client.requests.get')
        def test_should_use_default_pagination(self, mock_get, acp_client):
            """Should use default pagination when not specified"""
            mock_response = MagicMock()
            mock_response.json.return_value = {"data": []}
            mock_get.return_value = mock_response

            acp_client.get_active_jobs()

            expected_url = "https://api.example.com/jobs/active?pagination[page]=1&pagination[pageSize]=10"
            mock_get.assert_called_with(
                expected_url,
                headers={"wallet-address": TEST_AGENT_ADDRESS}
            )

        @patch('virtuals_acp.client.requests.get')
        def test_should_handle_custom_pagination(self, mock_get, acp_client):
            """Should correctly pass custom pagination parameters to API"""
            mock_response = MagicMock()
            mock_response.json.return_value = {"data": []}
            mock_get.return_value = mock_response

            acp_client.get_active_jobs(page=3, page_size=25)

            expected_url = "https://api.example.com/jobs/active?pagination[page]=3&pagination[pageSize]=25"
            mock_get.assert_called_with(
                expected_url,
                headers={"wallet-address": TEST_AGENT_ADDRESS}
            )

    class TestGetPendingMemoJobs:
        """Test get_pending_memo_jobs public method (integration of fetch + hydrate)"""

        @patch('virtuals_acp.client.requests.get')
        @patch('virtuals_acp.client.ACPJob')
        @patch('virtuals_acp.client.ACPMemo')
        def test_should_get_pending_memo_jobs_successfully(
            self, mock_memo_class, mock_job_class, mock_get, acp_client
        ):
            """Should successfully retrieve and hydrate pending memo jobs"""
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "data": [
                    {
                        "id": 123,
                        "clientAddress": TEST_AGENT_ADDRESS,
                        "providerAddress": TEST_PROVIDER_ADDRESS,
                        "evaluatorAddress": TEST_AGENT_ADDRESS,
                        "price": "100",
                        "priceTokenAddress": TEST_CONTRACT_ADDRESS,
                        "phase": 1,
                        "context": '{"key": "value"}',
                        "contractAddress": TEST_CONTRACT_ADDRESS,
                        "netPayableAmount": "90",
                        "memos": []
                    }
                ]
            }
            mock_get.return_value = mock_response

            mock_job = MagicMock()
            mock_job_class.return_value = mock_job

            jobs = acp_client.get_pending_memo_jobs(page=1, page_size=10)

            expected_url = "https://api.example.com/jobs/pending-memos?pagination[page]=1&pagination[pageSize]=10"
            mock_get.assert_called_once_with(
                expected_url,
                headers={"wallet-address": TEST_AGENT_ADDRESS}
            )

        @patch('virtuals_acp.client.requests.get')
        def test_should_use_default_pagination(self, mock_get, acp_client):
            """Should use default pagination when not specified"""
            mock_response = MagicMock()
            mock_response.json.return_value = {"data": []}
            mock_get.return_value = mock_response

            acp_client.get_pending_memo_jobs()

            expected_url = "https://api.example.com/jobs/pending-memos?pagination[page]=1&pagination[pageSize]=10"
            mock_get.assert_called_with(
                expected_url,
                headers={"wallet-address": TEST_AGENT_ADDRESS}
            )

        @patch('virtuals_acp.client.requests.get')
        def test_should_handle_custom_pagination(self, mock_get, acp_client):
            """Should correctly pass custom pagination parameters to API"""
            mock_response = MagicMock()
            mock_response.json.return_value = {"data": []}
            mock_get.return_value = mock_response

            acp_client.get_pending_memo_jobs(page=3, page_size=25)

            expected_url = "https://api.example.com/jobs/pending-memos?pagination[page]=3&pagination[pageSize]=25"
            mock_get.assert_called_with(
                expected_url,
                headers={"wallet-address": TEST_AGENT_ADDRESS}
            )

    class TestGetCompletedJobs:
        """Test get_completed_jobs public method (integration of fetch + hydrate)"""

        @patch('virtuals_acp.client.requests.get')
        @patch('virtuals_acp.client.ACPJob')
        @patch('virtuals_acp.client.ACPMemo')
        def test_should_get_completed_jobs_successfully(
            self, mock_memo_class, mock_job_class, mock_get, acp_client
        ):
            """Should successfully retrieve and hydrate completed jobs"""
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "data": [
                    {
                        "id": 123,
                        "clientAddress": TEST_AGENT_ADDRESS,
                        "providerAddress": TEST_PROVIDER_ADDRESS,
                        "evaluatorAddress": TEST_AGENT_ADDRESS,
                        "price": "100",
                        "priceTokenAddress": TEST_CONTRACT_ADDRESS,
                        "phase": 1,
                        "context": '{"key": "value"}',
                        "contractAddress": TEST_CONTRACT_ADDRESS,
                        "netPayableAmount": "90",
                        "memos": []
                    }
                ]
            }
            mock_get.return_value = mock_response

            mock_job = MagicMock()
            mock_job_class.return_value = mock_job

            jobs = acp_client.get_completed_jobs(page=1, page_size=10)

            expected_url = "https://api.example.com/jobs/completed?pagination[page]=1&pagination[pageSize]=10"
            mock_get.assert_called_once_with(
                expected_url,
                headers={"wallet-address": TEST_AGENT_ADDRESS}
            )

        @patch('virtuals_acp.client.requests.get')
        def test_should_use_default_pagination(self, mock_get, acp_client):
            """Should use default pagination when not specified"""
            mock_response = MagicMock()
            mock_response.json.return_value = {"data": []}
            mock_get.return_value = mock_response

            acp_client.get_completed_jobs()

            expected_url = "https://api.example.com/jobs/completed?pagination[page]=1&pagination[pageSize]=10"
            mock_get.assert_called_with(
                expected_url,
                headers={"wallet-address": TEST_AGENT_ADDRESS}
            )

        @patch('virtuals_acp.client.requests.get')
        def test_should_handle_custom_pagination(self, mock_get, acp_client):
            """Should correctly pass custom pagination parameters to API"""
            mock_response = MagicMock()
            mock_response.json.return_value = {"data": []}
            mock_get.return_value = mock_response

            acp_client.get_completed_jobs(page=3, page_size=25)

            expected_url = "https://api.example.com/jobs/completed?pagination[page]=3&pagination[pageSize]=25"
            mock_get.assert_called_with(
                expected_url,
                headers={"wallet-address": TEST_AGENT_ADDRESS}
            )

    class TestGetCancelledJobs:
        """Test get_completed_jobs public method (integration of fetch + hydrate)"""

        @patch('virtuals_acp.client.requests.get')
        @patch('virtuals_acp.client.ACPJob')
        @patch('virtuals_acp.client.ACPMemo')
        def test_should_get_cancelled_jobs_successfully(
            self, mock_memo_class, mock_job_class, mock_get, acp_client
        ):
            """Should successfully retrieve and hydrate cancelled jobs"""
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "data": [
                    {
                        "id": 123,
                        "clientAddress": TEST_AGENT_ADDRESS,
                        "providerAddress": TEST_PROVIDER_ADDRESS,
                        "evaluatorAddress": TEST_AGENT_ADDRESS,
                        "price": "100",
                        "priceTokenAddress": TEST_CONTRACT_ADDRESS,
                        "phase": 1,
                        "context": '{"key": "value"}',
                        "contractAddress": TEST_CONTRACT_ADDRESS,
                        "netPayableAmount": "90",
                        "memos": []
                    }
                ]
            }
            mock_get.return_value = mock_response

            mock_job = MagicMock()
            mock_job_class.return_value = mock_job

            jobs = acp_client.get_cancelled_jobs(page=1, page_size=10)

            expected_url = "https://api.example.com/jobs/cancelled?pagination[page]=1&pagination[pageSize]=10"
            mock_get.assert_called_once_with(
                expected_url,
                headers={"wallet-address": TEST_AGENT_ADDRESS}
            )

        @patch('virtuals_acp.client.requests.get')
        def test_should_use_default_pagination(self, mock_get, acp_client):
            """Should use default pagination when not specified"""
            mock_response = MagicMock()
            mock_response.json.return_value = {"data": []}
            mock_get.return_value = mock_response

            acp_client.get_cancelled_jobs()

            expected_url = "https://api.example.com/jobs/cancelled?pagination[page]=1&pagination[pageSize]=10"
            mock_get.assert_called_with(
                expected_url,
                headers={"wallet-address": TEST_AGENT_ADDRESS}
            )

        @patch('virtuals_acp.client.requests.get')
        def test_should_handle_custom_pagination(self, mock_get, acp_client):
            """Should correctly pass custom pagination parameters to API"""
            mock_response = MagicMock()
            mock_response.json.return_value = {"data": []}
            mock_get.return_value = mock_response

            acp_client.get_cancelled_jobs(page=3, page_size=25)

            expected_url = "https://api.example.com/jobs/cancelled?pagination[page]=3&pagination[pageSize]=25"
            mock_get.assert_called_with(
                expected_url,
                headers={"wallet-address": TEST_AGENT_ADDRESS}
            )

    class TestGetJobByOnchainId:
        """Test get_job_by_onchain_id method"""

        @patch('virtuals_acp.client.requests.get')
        @patch('virtuals_acp.client.ACPJob')
        @patch('virtuals_acp.client.ACPMemo')
        def test_should_get_job_by_onchain_id_successfully(
            self, mock_memo_class, mock_job_class, mock_get, acp_client
        ):
            """Should successfully retrieve job by onchain ID"""
            mock_memo = MagicMock()
            mock_memo_class.return_value = mock_memo

            mock_response = MagicMock()
            mock_response.json.return_value = {
                "data": {
                    "id": 123,
                    "clientAddress": TEST_AGENT_ADDRESS,
                    "providerAddress": TEST_PROVIDER_ADDRESS,
                    "evaluatorAddress": TEST_AGENT_ADDRESS,
                    "price": "100",
                    "priceTokenAddress": TEST_CONTRACT_ADDRESS,
                    "phase": 1,
                    "context": '{"key": "value"}',
                    "contractAddress": TEST_CONTRACT_ADDRESS,
                    "netPayableAmount": "90",
                    "memos": [
                        {
                            "id": 1,
                            "memoType": 1,
                            "content": "Test memo",
                            "nextPhase": 2,
                            "status": "PENDING",
                            "signedReason": None,
                            "expiry": None,
                            "payableDetails": None,
                            "txHash": None,
                            "signedTxHash": None
                        }
                    ]
                }
            }
            mock_get.return_value = mock_response

            mock_job = MagicMock()
            mock_job_class.return_value = mock_job

            job = acp_client.get_job_by_onchain_id(123)

            # Verify API call
            expected_url = "https://api.example.com/jobs/123"
            mock_get.assert_called_once_with(
                expected_url,
                headers={"wallet-address": TEST_AGENT_ADDRESS}
            )

            # Verify job was created
            assert job == mock_job
            assert mock_job_class.call_count == 1

        @patch('virtuals_acp.client.requests.get')
        def test_should_raise_error_on_api_error(self, mock_get, acp_client):
            """Should raise ACPApiError when API returns error"""
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "error": {
                    "message": "Job not found"
                }
            }
            mock_get.return_value = mock_response

            with pytest.raises(ACPApiError, match="Failed to get job by onchain ID"):
                acp_client.get_job_by_onchain_id(999)

        @patch('virtuals_acp.client.requests.get')
        def test_should_raise_error_on_network_failure(self, mock_get, acp_client):
            """Should raise ACPApiError when network request fails"""
            import requests
            mock_get.side_effect = requests.RequestException("Connection failed")

            with pytest.raises(ACPApiError, match="Failed to get job by onchain ID"):
                acp_client.get_job_by_onchain_id(123)

        @patch('virtuals_acp.client.requests.get')
        @patch('virtuals_acp.client.ACPJob')
        def test_should_handle_invalid_json_context(
            self, mock_job_class, mock_get, acp_client
        ):
            """Should handle JSONDecodeError when parsing context"""
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "data": {
                    "id": 123,
                    "clientAddress": TEST_AGENT_ADDRESS,
                    "providerAddress": TEST_PROVIDER_ADDRESS,
                    "evaluatorAddress": TEST_AGENT_ADDRESS,
                    "price": "1000000",
                    "priceTokenAddress": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                    "phase": 0,
                    "context": "{invalid json}",  # Invalid JSON
                    "memos": []
                }
            }
            mock_get.return_value = mock_response

            mock_job = MagicMock()
            mock_job_class.return_value = mock_job

            job = acp_client.get_job_by_onchain_id(123)

            # Verify job was created with context=None
            call_kwargs = mock_job_class.call_args[1]
            assert call_kwargs['context'] is None

    class TestGetMemoById:
        """Test get_memo_by_id method"""

        @patch('virtuals_acp.client.requests.get')
        @patch('virtuals_acp.client.ACPMemo')
        def test_should_get_memo_by_id_successfully(
            self, mock_memo_class, mock_get, acp_client
        ):
            """Should successfully retrieve memo by ID"""
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "data": {
                    "id": 1,
                    "memoType": 1,
                    "content": "Test memo content",
                    "nextPhase": 2,
                    "status": "PENDING",
                    "signedReason": None,
                    "expiry": None,
                    "payableDetails": None,
                    "txHash": None,
                    "signedTxHash": None
                }
            }
            mock_get.return_value = mock_response

            mock_memo = MagicMock()
            mock_memo_class.return_value = mock_memo

            memo = acp_client.get_memo_by_id(onchain_job_id=123, memo_id=1)

            # Verify API call
            expected_url = "https://api.example.com/jobs/123/memos/1"
            mock_get.assert_called_once_with(
                expected_url,
                headers={"wallet-address": TEST_AGENT_ADDRESS}
            )

            # Verify memo was created
            assert memo == mock_memo
            assert mock_memo_class.call_count == 1

        @patch('virtuals_acp.client.requests.get')
        def test_should_raise_error_on_api_error(self, mock_get, acp_client):
            """Should raise ACPApiError when API returns error"""
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "error": {
                    "message": "Memo not found"
                }
            }
            mock_get.return_value = mock_response

            with pytest.raises(ACPApiError, match="Failed to get memo by ID"):
                acp_client.get_memo_by_id(onchain_job_id=123, memo_id=999)

        @patch('virtuals_acp.client.requests.get')
        def test_should_raise_error_on_network_failure(self, mock_get, acp_client):
            """Should raise ACPApiError when network request fails"""
            import requests
            mock_get.side_effect = requests.RequestException("Connection failed")

            with pytest.raises(ACPApiError, match="Failed to get memo by ID"):
                acp_client.get_memo_by_id(onchain_job_id=123, memo_id=1)

    class TestInitialization:
        """Test VirtualsACP initialization"""

        @patch('virtuals_acp.client.socketio.Client')
        def test_should_initialize_with_single_client(self, mock_socketio, mock_contract_client):
            """Should initialize with a single contract client"""
            client = VirtualsACP(acp_contract_clients=mock_contract_client)

            assert client.contract_clients == [mock_contract_client]
            assert client.contract_client == mock_contract_client
            assert client.agent_wallet_address == TEST_AGENT_ADDRESS

        @patch('virtuals_acp.client.socketio.Client')
        def test_should_initialize_with_list_of_clients(self, mock_socketio, mock_contract_client):
            """Should initialize with a list of contract clients"""
            client2 = MagicMock()
            client2.agent_wallet_address = TEST_AGENT_ADDRESS
            client2.config.acp_api_url = "https://api.example.com"
            client2.contract_address = "0x9876543210987654321098765432109876543210"

            client = VirtualsACP(acp_contract_clients=[mock_contract_client, client2])

            assert len(client.contract_clients) == 2
            assert client.contract_client == mock_contract_client

        @patch('virtuals_acp.client.socketio.Client')
        def test_should_raise_error_when_no_clients_provided(self, mock_socketio):
            """Should raise ACPError when no clients provided"""
            with pytest.raises(ACPError, match="ACP contract client is required"):
                VirtualsACP(acp_contract_clients=[])

        @patch('virtuals_acp.client.socketio.Client')
        def test_should_raise_error_when_clients_have_different_addresses(
            self, mock_socketio, mock_contract_client
        ):
            """Should raise error when clients have different agent addresses"""
            client2 = MagicMock()
            client2.agent_wallet_address = "0x9999999999999999999999999999999999999999"
            client2.config.acp_api_url = "https://api.example.com"

            with pytest.raises(
                ACPError,
                match="All contract clients must have the same agent wallet address"
            ):
                VirtualsACP(acp_contract_clients=[mock_contract_client, client2])

    class TestContractClientByAddress:
        """Test contract_client_by_address method"""

        def test_should_return_first_client_when_no_address(self, acp_client, mock_contract_client):
            """Should return first client when no address provided"""
            result = acp_client.contract_client_by_address(None)
            assert result == mock_contract_client

        def test_should_find_client_by_address(self, mock_contract_client):
            """Should find and return client by contract address"""
            client2 = MagicMock()
            client2.agent_wallet_address = TEST_AGENT_ADDRESS
            client2.config.acp_api_url = "https://api.example.com"
            client2.contract_address = "0x9876543210987654321098765432109876543210"

            with patch('virtuals_acp.client.socketio.Client'):
                client = VirtualsACP(acp_contract_clients=[mock_contract_client, client2])

            result = client.contract_client_by_address("0x9876543210987654321098765432109876543210")
            assert result == client2

        def test_should_raise_error_when_client_not_found(self, acp_client):
            """Should raise ACPError when client not found by address"""
            with pytest.raises(ACPError, match="ACP contract client not found"):
                acp_client.contract_client_by_address("0x0000000000000000000000000000000000000000")

    class TestGetByClientAndProvider:
        """Test get_by_client_and_provider method"""

        @patch('virtuals_acp.client.requests.get')
        @patch('virtuals_acp.client.ACPAccount')
        def test_should_get_account_successfully(
            self, mock_account_class, mock_get, acp_client
        ):
            """Should successfully retrieve account by client and provider"""
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "data": {
                    "id": 1,
                    "clientAddress": TEST_AGENT_ADDRESS,
                    "providerAddress": TEST_PROVIDER_ADDRESS,
                    "metadata": "test metadata"
                }
            }
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            mock_account = MagicMock()
            mock_account_class.return_value = mock_account

            account = acp_client.get_by_client_and_provider(
                TEST_AGENT_ADDRESS,
                TEST_PROVIDER_ADDRESS
            )

            # Verify API call
            expected_url = f"https://api.example.com/accounts/client/{TEST_AGENT_ADDRESS}/provider/{TEST_PROVIDER_ADDRESS}"
            mock_get.assert_called_once_with(expected_url)

            # Verify account was created
            assert account == mock_account

        @patch('virtuals_acp.client.requests.get')
        def test_should_return_none_on_404(self, mock_get, acp_client):
            """Should return None when account not found (404)"""
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_get.return_value = mock_response

            account = acp_client.get_by_client_and_provider(
                TEST_AGENT_ADDRESS,
                TEST_PROVIDER_ADDRESS
            )

            assert account is None

        @patch('virtuals_acp.client.requests.get')
        def test_should_raise_error_on_network_failure(self, mock_get, acp_client):
            """Should raise ACPApiError when network request fails"""
            import requests
            mock_get.side_effect = requests.RequestException("Connection failed")

            with pytest.raises(ACPApiError, match="Failed to get account by client and provider"):
                acp_client.get_by_client_and_provider(
                    TEST_AGENT_ADDRESS,
                    TEST_PROVIDER_ADDRESS
                )

        @patch('virtuals_acp.client.requests.get')
        def test_should_return_none_when_no_data(self, mock_get, acp_client):
            """Should return None when API returns empty data"""
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": None}
            mock_get.return_value = mock_response

            result = acp_client.get_by_client_and_provider(
                TEST_AGENT_ADDRESS,
                TEST_PROVIDER_ADDRESS
            )

            assert result is None

        @patch('virtuals_acp.client.requests.get')
        def test_should_handle_generic_exception(self, mock_get, acp_client):
            """Should raise ACPError for generic exceptions"""
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.side_effect = ValueError("Unexpected error")
            mock_get.return_value = mock_response

            with pytest.raises(ACPError, match="An unexpected error occurred while getting account"):
                acp_client.get_by_client_and_provider(
                    TEST_AGENT_ADDRESS,
                    TEST_PROVIDER_ADDRESS
                )

    class TestGetAccountByJobId:
        """Test get_account_by_job_id method"""

        @patch('virtuals_acp.client.requests.get')
        @patch('virtuals_acp.client.ACPAccount')
        def test_should_get_account_successfully(
            self, mock_account_class, mock_get, acp_client
        ):
            """Should successfully retrieve account by job ID"""
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "data": {
                    "id": 1,
                    "clientAddress": TEST_AGENT_ADDRESS,
                    "providerAddress": TEST_PROVIDER_ADDRESS,
                    "metadata": "test metadata"
                }
            }
            mock_get.return_value = mock_response

            mock_account = MagicMock()
            mock_account_class.return_value = mock_account

            account = acp_client.get_account_by_job_id(123)

            # Verify API call
            expected_url = "https://api.example.com/accounts/job/123"
            mock_get.assert_called_once_with(expected_url)

            # Verify account was created
            assert account == mock_account

        @patch('virtuals_acp.client.requests.get')
        def test_should_return_none_when_no_data(self, mock_get, acp_client):
            """Should return None when no data in response"""
            mock_response = MagicMock()
            mock_response.json.return_value = {"data": None}
            mock_get.return_value = mock_response

            account = acp_client.get_account_by_job_id(123)

            assert account is None

        @patch('virtuals_acp.client.requests.get')
        def test_should_raise_error_on_network_failure(self, mock_get, acp_client):
            """Should raise ACPApiError when network request fails"""
            import requests
            mock_get.side_effect = requests.RequestException("Connection failed")

            with pytest.raises(ACPApiError, match="Failed to get account by job id"):
                acp_client.get_account_by_job_id(123)

        @patch('virtuals_acp.client.requests.get')
        def test_should_handle_generic_exception(self, mock_get, acp_client):
            """Should raise ACPError for generic exceptions"""
            mock_response = MagicMock()
            mock_response.json.side_effect = ValueError("Unexpected error")
            mock_get.return_value = mock_response

            with pytest.raises(ACPError, match="An unexpected error occurred while getting account by job id"):
                acp_client.get_account_by_job_id(123)

    class TestInitiateJob:
        """Test initiate_job method"""

        @pytest.fixture
        def mock_fare_amount(self):
            """Create a mock FareAmountBase"""
            fare = MagicMock()
            fare.amount = 100
            fare.fare.contract_address = "0xTokenAddress1234567890123456789012345678"
            return fare

        def test_should_raise_error_when_provider_is_self(self, acp_client, mock_fare_amount):
            """Should raise ACPError when provider address is same as client"""
            with pytest.raises(ACPError, match="Provider address cannot be the same as the client address"):
                acp_client.initiate_job(
                    provider_address=acp_client.agent_address,
                    service_requirement={"task": "test"},
                    fare_amount=mock_fare_amount
                )

        @patch('virtuals_acp.client.VirtualsACP.get_by_client_and_provider')
        def test_should_use_create_job_when_no_account_exists(
            self, mock_get_account, acp_client, mock_fare_amount
        ):
            """Should call create_job when no existing account"""
            # Mock no existing account
            mock_get_account.return_value = None

            # Mock contract client methods
            mock_create_op = MagicMock()
            acp_client.contract_client.create_job = MagicMock(return_value=mock_create_op)
            acp_client.contract_client.handle_operation = MagicMock(return_value="tx_response")
            acp_client.contract_client.get_job_id = MagicMock(return_value=42)

            mock_memo_op = MagicMock()
            acp_client.contract_client.create_memo = MagicMock(return_value=mock_memo_op)

            job_id = acp_client.initiate_job(
                provider_address=TEST_PROVIDER_ADDRESS,
                service_requirement={"task": "test"},
                fare_amount=mock_fare_amount
            )

            # Verify create_job was called (not create_job_with_account)
            acp_client.contract_client.create_job.assert_called_once()
            assert job_id == 42

        @patch('virtuals_acp.client.VirtualsACP.get_by_client_and_provider')
        def test_should_use_create_job_with_account_when_account_exists(
            self, mock_get_account, acp_client, mock_fare_amount
        ):
            """Should call create_job_with_account when account exists"""
            # Mock existing account
            mock_account = MagicMock()
            mock_account.id = 5
            mock_get_account.return_value = mock_account

            # Mock contract client methods
            mock_create_op = MagicMock()
            acp_client.contract_client.create_job_with_account = MagicMock(return_value=mock_create_op)
            acp_client.contract_client.handle_operation = MagicMock(return_value="tx_response")
            acp_client.contract_client.get_job_id = MagicMock(return_value=43)

            mock_memo_op = MagicMock()
            acp_client.contract_client.create_memo = MagicMock(return_value=mock_memo_op)

            # Set config to NOT be a base contract (to trigger account path)
            acp_client.contract_client.config.contract_address = "0xCustomContract123456789012345678901234567"

            job_id = acp_client.initiate_job(
                provider_address=TEST_PROVIDER_ADDRESS,
                service_requirement={"task": "test"},
                fare_amount=mock_fare_amount
            )

            # Verify create_job_with_account was called with account ID
            acp_client.contract_client.create_job_with_account.assert_called_once()
            call_args = acp_client.contract_client.create_job_with_account.call_args[0]
            assert call_args[0] == 5  # account.id
            assert job_id == 43

        @patch('virtuals_acp.client.VirtualsACP.get_by_client_and_provider')
        def test_should_convert_dict_requirement_to_json(
            self, mock_get_account, acp_client, mock_fare_amount
        ):
            """Should convert dictionary service requirement to JSON string"""
            mock_get_account.return_value = None

            mock_create_op = MagicMock()
            acp_client.contract_client.create_job = MagicMock(return_value=mock_create_op)
            acp_client.contract_client.handle_operation = MagicMock(return_value="tx_response")
            acp_client.contract_client.get_job_id = MagicMock(return_value=44)

            mock_memo_op = MagicMock()
            acp_client.contract_client.create_memo = MagicMock(return_value=mock_memo_op)

            requirement_dict = {"task": "translate", "language": "spanish"}

            acp_client.initiate_job(
                provider_address=TEST_PROVIDER_ADDRESS,
                service_requirement=requirement_dict,
                fare_amount=mock_fare_amount
            )

            # Verify create_memo was called with JSON string
            acp_client.contract_client.create_memo.assert_called_once()
            call_args = acp_client.contract_client.create_memo.call_args[0]

            # The second argument should be the JSON-stringified requirement
            import json
            assert json.loads(call_args[1]) == requirement_dict

        @patch('virtuals_acp.client.VirtualsACP.get_by_client_and_provider')
        def test_should_use_string_requirement_as_is(
            self, mock_get_account, acp_client, mock_fare_amount
        ):
            """Should use string service requirement without modification"""
            mock_get_account.return_value = None

            mock_create_op = MagicMock()
            acp_client.contract_client.create_job = MagicMock(return_value=mock_create_op)
            acp_client.contract_client.handle_operation = MagicMock(return_value="tx_response")
            acp_client.contract_client.get_job_id = MagicMock(return_value=45)

            mock_memo_op = MagicMock()
            acp_client.contract_client.create_memo = MagicMock(return_value=mock_memo_op)

            requirement_str = "Please translate this document"

            acp_client.initiate_job(
                provider_address=TEST_PROVIDER_ADDRESS,
                service_requirement=requirement_str,
                fare_amount=mock_fare_amount
            )

            # Verify create_memo was called with the string as-is
            acp_client.contract_client.create_memo.assert_called_once()
            call_args = acp_client.contract_client.create_memo.call_args[0]
            assert call_args[1] == requirement_str

        @patch('virtuals_acp.client.VirtualsACP.get_by_client_and_provider')
        def test_should_use_default_expiry_if_not_provided(
            self, mock_get_account, acp_client, mock_fare_amount
        ):
            """Should set expiry to 1 day from now if not provided"""
            from datetime import datetime, timezone, timedelta

            mock_get_account.return_value = None

            mock_create_op = MagicMock()
            acp_client.contract_client.create_job = MagicMock(return_value=mock_create_op)
            acp_client.contract_client.handle_operation = MagicMock(return_value="tx_response")
            acp_client.contract_client.get_job_id = MagicMock(return_value=46)

            mock_memo_op = MagicMock()
            acp_client.contract_client.create_memo = MagicMock(return_value=mock_memo_op)

            before = datetime.now(timezone.utc) + timedelta(days=1)

            acp_client.initiate_job(
                provider_address=TEST_PROVIDER_ADDRESS,
                service_requirement="test",
                fare_amount=mock_fare_amount
                # Note: no expired_at provided
            )

            after = datetime.now(timezone.utc) + timedelta(days=1)

            # Verify create_job was called with an expiry around 1 day from now
            acp_client.contract_client.create_job.assert_called_once()
            call_args = acp_client.contract_client.create_job.call_args[0]
            expired_at = call_args[2]  # Third argument is expired_at

            # Should be within a few seconds of 1 day from now
            assert before <= expired_at <= after

        @patch('virtuals_acp.client.VirtualsACP.get_by_client_and_provider')
        def test_should_use_custom_evaluator_address(
            self, mock_get_account, acp_client, mock_fare_amount
        ):
            """Should use custom evaluator address if provided"""
            mock_get_account.return_value = None

            mock_create_op = MagicMock()
            acp_client.contract_client.create_job = MagicMock(return_value=mock_create_op)
            acp_client.contract_client.handle_operation = MagicMock(return_value="tx_response")
            acp_client.contract_client.get_job_id = MagicMock(return_value=47)

            mock_memo_op = MagicMock()
            acp_client.contract_client.create_memo = MagicMock(return_value=mock_memo_op)

            custom_evaluator = "0x7777777777777777777777777777777777777777"

            acp_client.initiate_job(
                provider_address=TEST_PROVIDER_ADDRESS,
                service_requirement="test",
                fare_amount=mock_fare_amount,
                evaluator_address=custom_evaluator
            )

            # Verify create_job was called with custom evaluator
            acp_client.contract_client.create_job.assert_called_once()
            call_args = acp_client.contract_client.create_job.call_args[0]

            # Second argument is evaluator address
            from web3 import Web3
            assert call_args[1] == Web3.to_checksum_address(custom_evaluator)

    class TestProperties:
        """Test property accessors"""

        def test_should_access_acp_contract_client_property(self, acp_client):
            """Should access backward compatibility property acp_contract_client"""
            assert acp_client.acp_contract_client == acp_client.contract_clients[0]

    class TestBrowseAgents:
        """Test browse_agents method"""

        @patch('virtuals_acp.client.requests.get')
        def test_should_include_cluster_in_url(self, mock_get, acp_client):
            """Should include cluster parameter in URL when provided"""
            mock_response = MagicMock()
            mock_response.json.return_value = {"data": []}
            mock_get.return_value = mock_response

            acp_client.browse_agents(keyword="test", cluster="ai-agents")

            # Verify URL includes cluster parameter
            called_url = mock_get.call_args[0][0]
            assert "&cluster=ai-agents" in called_url

        @patch('virtuals_acp.client.requests.get')
        def test_should_include_graduation_status_in_url(self, mock_get, acp_client):
            """Should include graduation_status parameter in URL when provided"""
            from virtuals_acp.models import ACPGraduationStatus

            mock_response = MagicMock()
            mock_response.json.return_value = {"data": []}
            mock_get.return_value = mock_response

            acp_client.browse_agents(
                keyword="test",
                graduation_status=ACPGraduationStatus.GRADUATED
            )

            # Verify URL includes graduation status parameter
            called_url = mock_get.call_args[0][0]
            assert f"&graduationStatus={ACPGraduationStatus.GRADUATED.value}" in called_url

        @patch('virtuals_acp.client.requests.get')
        def test_should_include_online_status_in_url(self, mock_get, acp_client):
            """Should include online_status parameter in URL when provided"""
            from virtuals_acp.models import ACPOnlineStatus

            mock_response = MagicMock()
            mock_response.json.return_value = {"data": []}
            mock_get.return_value = mock_response

            acp_client.browse_agents(
                keyword="test",
                online_status=ACPOnlineStatus.ONLINE
            )

            # Verify URL includes online status parameter
            called_url = mock_get.call_args[0][0]
            assert f"&onlineStatus={ACPOnlineStatus.ONLINE.value}" in called_url

        @patch('virtuals_acp.client.requests.get')
        def test_should_include_show_hidden_offerings_in_url(self, mock_get, acp_client):
            """Should include showHiddenOfferings parameter in URL when true"""
            mock_response = MagicMock()
            mock_response.json.return_value = {"data": []}
            mock_get.return_value = mock_response

            acp_client.browse_agents(
                keyword="test",
                show_hidden_offerings=True
            )

            # Verify URL includes showHiddenOfferings parameter
            called_url = mock_get.call_args[0][0]
            assert "&showHiddenOfferings=true" in called_url

        @patch('virtuals_acp.client.requests.get')
        def test_should_handle_generic_exception(self, mock_get, acp_client):
            """Should raise ACPError for generic exceptions in browse_agents"""
            mock_get.side_effect = ValueError("Unexpected error")

            with pytest.raises(ACPError, match="An unexpected error occurred while browsing agents"):
                acp_client.browse_agents(keyword="test")

    class TestGetAgent:
        """Test get_agent method"""

        @patch('virtuals_acp.client.requests.get')
        def test_should_handle_generic_exception(self, mock_get, acp_client):
            """Should raise ACPError for generic exceptions in get_agent"""
            mock_get.side_effect = ValueError("Unexpected error")

            with pytest.raises(ACPError, match="An unexpected error occurred while getting agent"):
                acp_client.get_agent(TEST_AGENT_ADDRESS)
