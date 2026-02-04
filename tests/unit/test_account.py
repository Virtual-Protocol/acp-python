import pytest
import json
from unittest.mock import MagicMock
from virtuals_acp.account import ACPAccount
from virtuals_acp.models import OperationPayload

TEST_AGENT_ADDRESS = "0x1234567890123456789012345678901234567890"
TEST_PROVIDER_ADDRESS = "0x5555555555555555555555555555555555555555"


class TestACPAccount:
    @pytest.fixture
    def mock_contract_client(self):
        """Create a mock contract client"""
        return MagicMock()

    @pytest.fixture
    def sample_metadata(self):
        """Sample metadata for testing"""
        return {
            "service_name": "AI Trading Bot",
            "category": "trading",
            "tags": ["ai", "trading", "defi"]
        }

    @pytest.fixture
    def account(self, mock_contract_client, sample_metadata):
        """Create an ACPAccount instance for testing"""
        return ACPAccount(
            contract_client=mock_contract_client,
            id=123,
            client_address=TEST_AGENT_ADDRESS,
            provider_address=TEST_PROVIDER_ADDRESS,
            metadata=sample_metadata
        )

    class TestInitialization:
        """Test account initialization"""

        def test_should_initialize_with_all_parameters(
            self, mock_contract_client, sample_metadata
        ):
            """Should correctly initialize account with all parameters"""
            account = ACPAccount(
                contract_client=mock_contract_client,
                id=456,
                client_address=TEST_AGENT_ADDRESS,
                provider_address=TEST_PROVIDER_ADDRESS,
                metadata=sample_metadata
            )

            assert account.contract_client == mock_contract_client
            assert account.id == 456
            assert account.client_address == TEST_AGENT_ADDRESS
            assert account.provider_address == TEST_PROVIDER_ADDRESS
            assert account.metadata == sample_metadata

        def test_should_initialize_with_empty_metadata(self, mock_contract_client):
            """Should initialize with empty metadata dictionary"""
            account = ACPAccount(
                contract_client=mock_contract_client,
                id=789,
                client_address=TEST_AGENT_ADDRESS,
                provider_address=TEST_PROVIDER_ADDRESS,
                metadata={}
            )

            assert account.metadata == {}

        def test_should_store_metadata_reference(self, mock_contract_client):
            """Should store reference to metadata dictionary"""
            metadata = {"key": "value"}
            account = ACPAccount(
                contract_client=mock_contract_client,
                id=111,
                client_address=TEST_AGENT_ADDRESS,
                provider_address=TEST_PROVIDER_ADDRESS,
                metadata=metadata
            )

            assert account.metadata == {"key": "value"}

    class TestUpdateMetadata:
        """Test update_metadata method"""

        def test_should_call_contract_client_with_json_string(
            self, account, mock_contract_client
        ):
            """Should call contract client's update_account_metadata with JSON string"""
            new_metadata = {"updated": "data", "version": 2}
            mock_operation = MagicMock(spec=OperationPayload)
            mock_contract_client.update_account_metadata.return_value = mock_operation

            result = account.update_metadata(new_metadata)

            # Verify contract client was called with correct parameters
            mock_contract_client.update_account_metadata.assert_called_once_with(
                123,  # account.id
                json.dumps(new_metadata)
            )

            # Verify operation payload was returned
            assert result == mock_operation

        def test_should_serialize_complex_metadata_to_json(
            self, account, mock_contract_client
        ):
            """Should properly serialize complex metadata structures to JSON"""
            complex_metadata = {
                "name": "Test Service",
                "tags": ["tag1", "tag2"],
                "config": {
                    "nested": {
                        "value": 123,
                        "enabled": True
                    }
                }
            }
            mock_contract_client.update_account_metadata.return_value = MagicMock()

            account.update_metadata(complex_metadata)

            # Verify the JSON string is properly formatted
            call_args = mock_contract_client.update_account_metadata.call_args[0]
            assert call_args[0] == 123
            assert call_args[1] == json.dumps(complex_metadata)

            # Verify JSON is valid by parsing it back
            parsed = json.loads(call_args[1])
            assert parsed == complex_metadata

        def test_should_handle_empty_metadata_update(
            self, account, mock_contract_client
        ):
            """Should handle updating with empty metadata"""
            mock_contract_client.update_account_metadata.return_value = MagicMock()

            account.update_metadata({})

            mock_contract_client.update_account_metadata.assert_called_once_with(
                123,
                "{}"
            )

        def test_should_update_different_account_ids(self, mock_contract_client):
            """Should use correct account ID for different accounts"""
            account1 = ACPAccount(
                contract_client=mock_contract_client,
                id=111,
                client_address=TEST_AGENT_ADDRESS,
                provider_address=TEST_PROVIDER_ADDRESS,
                metadata={}
            )
            account2 = ACPAccount(
                contract_client=mock_contract_client,
                id=222,
                client_address=TEST_AGENT_ADDRESS,
                provider_address=TEST_PROVIDER_ADDRESS,
                metadata={}
            )

            mock_contract_client.update_account_metadata.return_value = MagicMock()

            account1.update_metadata({"account": 1})
            account2.update_metadata({"account": 2})

            # Verify first call used account1's ID
            first_call = mock_contract_client.update_account_metadata.call_args_list[0]
            assert first_call[0][0] == 111

            # Verify second call used account2's ID
            second_call = mock_contract_client.update_account_metadata.call_args_list[1]
            assert second_call[0][0] == 222

        def test_should_not_modify_original_metadata_property(
            self, account, mock_contract_client
        ):
            """Should not modify the account's metadata property when updating"""
            original_metadata = account.metadata.copy()
            mock_contract_client.update_account_metadata.return_value = MagicMock()

            new_metadata = {"completely": "different"}
            account.update_metadata(new_metadata)

            # Original metadata should remain unchanged
            assert account.metadata == original_metadata

        def test_should_return_operation_payload_from_contract_client(
            self, account, mock_contract_client
        ):
            """Should return the operation payload from contract client"""
            mock_operation = MagicMock(spec=OperationPayload)
            mock_operation.target = "0xContractAddress"
            mock_operation.data = "0xEncodedData"
            mock_operation.value = 0

            mock_contract_client.update_account_metadata.return_value = mock_operation

            result = account.update_metadata({"test": "data"})

            assert result is mock_operation
            assert result.target == "0xContractAddress"
            assert result.data == "0xEncodedData"
