"""
Unit tests for virtuals_acp.memo module
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from virtuals_acp.memo import ACPMemo
from virtuals_acp.models import (
    ACPJobPhase,
    MemoType,
    ACPMemoStatus,
    PayloadType,
    GenericPayload,
    OperationPayload,
)


class TestACPMemo:
    """Test suite for ACPMemo class"""

    @pytest.fixture
    def mock_contract_client(self):
        """Create a mock contract client"""
        return MagicMock()

    @pytest.fixture
    def sample_memo_data(self, mock_contract_client):
        """Create sample memo data for testing"""
        return {
            "contract_client": mock_contract_client,
            "id": 1,
            "type": MemoType.MESSAGE,
            "content": "Test memo content",
            "next_phase": ACPJobPhase.NEGOTIATION,
            "status": ACPMemoStatus.PENDING,
            "signed_reason": None,
            "expiry": None,
            "payable_details": None,
            "txn_hash": None,
            "signed_txn_hash": None,
        }

    @pytest.fixture
    def basic_memo(self, sample_memo_data):
        """Create a basic ACPMemo instance for testing"""
        return ACPMemo.model_construct(**sample_memo_data)

    class TestInitialization:
        """Test memo initialization"""

        def test_should_initialize_with_all_parameters(self, sample_memo_data):
            """Should correctly initialize memo with all parameters"""
            memo = ACPMemo.model_construct(**sample_memo_data)

            assert memo.id == 1
            assert memo.type == MemoType.MESSAGE
            assert memo.content == "Test memo content"
            assert memo.next_phase == ACPJobPhase.NEGOTIATION
            assert memo.status == ACPMemoStatus.PENDING
            assert memo.signed_reason is None
            assert memo.expiry is None
            assert memo.payable_details is None
            assert memo.txn_hash is None
            assert memo.signed_txn_hash is None

        def test_should_initialize_with_optional_fields(self, sample_memo_data):
            """Should initialize with optional fields"""
            expiry_time = datetime.now(timezone.utc)
            sample_memo_data["signed_reason"] = "Approved with conditions"
            sample_memo_data["expiry"] = expiry_time
            sample_memo_data["txn_hash"] = "0xabc123"
            sample_memo_data["signed_txn_hash"] = "0xdef456"

            memo = ACPMemo.model_construct(**sample_memo_data)

            assert memo.signed_reason == "Approved with conditions"
            assert memo.expiry == expiry_time
            assert memo.txn_hash == "0xabc123"
            assert memo.signed_txn_hash == "0xdef456"

        def test_should_parse_structured_content_in_post_init(self, sample_memo_data):
            """Should parse structured content from JSON in model_post_init"""
            content_data = {
                "type": "fund_response",
                "data": {"amount": 100.0, "status": "success"}
            }
            sample_memo_data["content"] = json.dumps(content_data)

            with patch('virtuals_acp.memo.try_parse_json_model') as mock_parse:
                mock_payload = MagicMock(spec=GenericPayload)
                mock_payload.type = PayloadType.FUND_RESPONSE
                mock_parse.return_value = mock_payload

                # model_construct automatically calls model_post_init
                memo = ACPMemo.model_construct(**sample_memo_data)

                # Verify it was called with correct parameters
                mock_parse.assert_called_with(sample_memo_data["content"], GenericPayload)
                assert memo.structured_content == mock_payload

        def test_should_handle_unparseable_content(self, sample_memo_data):
            """Should handle content that cannot be parsed as structured content"""
            sample_memo_data["content"] = "Plain text content"

            with patch('virtuals_acp.memo.try_parse_json_model', return_value=None):
                memo = ACPMemo.model_construct(**sample_memo_data)
                memo.model_post_init(None)

                assert memo.structured_content is None

        def test_should_convert_payable_details_amounts(self, sample_memo_data):
            """Should convert amount and feeAmount to int in payable_details"""
            sample_memo_data["payable_details"] = {
                "amount": "1000000",
                "feeAmount": "50000",
                "token": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
            }

            memo = ACPMemo.model_construct(**sample_memo_data)
            memo.model_post_init(None)

            assert memo.payable_details["amount"] == 1000000
            assert memo.payable_details["feeAmount"] == 50000
            assert isinstance(memo.payable_details["amount"], int)
            assert isinstance(memo.payable_details["feeAmount"], int)

        def test_should_skip_payable_conversion_when_none(self, sample_memo_data):
            """Should skip payable_details conversion when None"""
            sample_memo_data["payable_details"] = None

            memo = ACPMemo.model_construct(**sample_memo_data)
            memo.model_post_init(None)

            assert memo.payable_details is None

    class TestStr:
        """Test __str__ method"""

        def test_should_return_formatted_string(self, basic_memo):
            """Should return formatted string representation"""
            # Patch model_dump at class level
            with patch('virtuals_acp.memo.ACPMemo.model_dump') as mock_dump:
                mock_dump.return_value = {
                    "id": 1,
                    "type": MemoType.MESSAGE,
                    "content": "Test memo content",
                    "next_phase": ACPJobPhase.NEGOTIATION,
                    "status": ACPMemoStatus.PENDING,
                }
                result = str(basic_memo)

                # Verify model_dump was called with exclude
                mock_dump.assert_called_once_with(exclude={'payable_details'})
                assert result.startswith("AcpMemo(")

        def test_should_exclude_payable_details_from_string(self, sample_memo_data):
            """Should exclude payable_details from string representation"""
            sample_memo_data["payable_details"] = {
                "amount": 1000000,
                "feeAmount": 50000,
                "token": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
            }

            memo = ACPMemo.model_construct(**sample_memo_data)

            # Patch model_dump at class level
            with patch('virtuals_acp.memo.ACPMemo.model_dump') as mock_dump:
                mock_dump.return_value = {"id": 1, "type": MemoType.MESSAGE}
                str(memo)

                # Verify payable_details was excluded
                mock_dump.assert_called_once_with(exclude={'payable_details'})

    class TestPayloadTypeProperty:
        """Test payload_type property"""

        def test_should_return_payload_type_when_structured_content_exists(
            self, sample_memo_data
        ):
            """Should return payload type from structured content"""
            mock_payload = MagicMock(spec=GenericPayload)
            mock_payload.type = PayloadType.FUND_RESPONSE

            memo = ACPMemo.model_construct(**sample_memo_data)
            memo.structured_content = mock_payload

            assert memo.payload_type == PayloadType.FUND_RESPONSE

        def test_should_return_none_when_no_structured_content(self, basic_memo):
            """Should return None when structured_content is None"""
            basic_memo.structured_content = None

            assert basic_memo.payload_type is None

    class TestCreate:
        """Test create method"""

        def test_should_call_contract_client_create_memo(
            self, basic_memo, mock_contract_client
        ):
            """Should call contract client's create_memo method"""
            mock_operation = MagicMock(spec=OperationPayload)
            mock_contract_client.create_memo.return_value = mock_operation

            result = basic_memo.create(job_id=123, is_secured=True)

            mock_contract_client.create_memo.assert_called_once_with(
                123,  # job_id
                "Test memo content",  # content
                MemoType.MESSAGE,  # type
                True,  # is_secured
                ACPJobPhase.NEGOTIATION,  # next_phase
            )
            assert result == mock_operation

        def test_should_pass_is_secured_false_when_specified(
            self, basic_memo, mock_contract_client
        ):
            """Should pass is_secured=False when specified"""
            mock_operation = MagicMock(spec=OperationPayload)
            mock_contract_client.create_memo.return_value = mock_operation

            basic_memo.create(job_id=456, is_secured=False)

            call_args = mock_contract_client.create_memo.call_args
            assert call_args[0][3] is False  # is_secured parameter

        def test_should_use_default_is_secured_true(
            self, basic_memo, mock_contract_client
        ):
            """Should default is_secured to True"""
            mock_operation = MagicMock(spec=OperationPayload)
            mock_contract_client.create_memo.return_value = mock_operation

            basic_memo.create(job_id=789)

            call_args = mock_contract_client.create_memo.call_args
            assert call_args[0][3] is True  # is_secured parameter

    class TestSign:
        """Test sign method"""

        def test_should_sign_memo_with_approval(
            self, basic_memo, mock_contract_client
        ):
            """Should sign memo with approved=True"""
            mock_operation = MagicMock(spec=OperationPayload)
            mock_contract_client.sign_memo.return_value = mock_operation
            mock_contract_client.handle_operation.return_value = {"hash": "0xsigned"}

            with patch('virtuals_acp.memo.get_txn_hash_from_response', return_value="0xsigned"):
                result = basic_memo.sign(approved=True, reason="Looks good")

            mock_contract_client.sign_memo.assert_called_once_with(
                1,  # memo id
                True,  # approved
                "Looks good"  # reason
            )
            mock_contract_client.handle_operation.assert_called_once_with([mock_operation])
            assert result == "0xsigned"

        def test_should_sign_memo_with_rejection(
            self, basic_memo, mock_contract_client
        ):
            """Should sign memo with approved=False"""
            mock_operation = MagicMock(spec=OperationPayload)
            mock_contract_client.sign_memo.return_value = mock_operation
            mock_contract_client.handle_operation.return_value = {"hash": "0xrejected"}

            with patch('virtuals_acp.memo.get_txn_hash_from_response', return_value="0xrejected"):
                result = basic_memo.sign(approved=False, reason="Not acceptable")

            mock_contract_client.sign_memo.assert_called_once_with(
                1,  # memo id
                False,  # approved
                "Not acceptable"  # reason
            )
            assert result == "0xrejected"

        def test_should_sign_without_reason(
            self, basic_memo, mock_contract_client
        ):
            """Should sign memo without providing a reason"""
            mock_operation = MagicMock(spec=OperationPayload)
            mock_contract_client.sign_memo.return_value = mock_operation
            mock_contract_client.handle_operation.return_value = {"hash": "0xsigned"}

            with patch('virtuals_acp.memo.get_txn_hash_from_response', return_value="0xsigned"):
                result = basic_memo.sign(approved=True)

            call_args = mock_contract_client.sign_memo.call_args
            assert call_args[0][2] is None  # reason parameter

        def test_should_return_none_when_no_hash_in_response(
            self, basic_memo, mock_contract_client
        ):
            """Should return None when response has no transaction hash"""
            mock_operation = MagicMock(spec=OperationPayload)
            mock_contract_client.sign_memo.return_value = mock_operation
            mock_contract_client.handle_operation.return_value = {}

            with patch('virtuals_acp.memo.get_txn_hash_from_response', return_value=None):
                result = basic_memo.sign(approved=True, reason="Test")

            assert result is None

    class TestDifferentMemoTypes:
        """Test different memo types"""

        def test_should_handle_context_url_memo_type(self, sample_memo_data):
            """Should handle CONTEXT_URL memo type"""
            sample_memo_data["type"] = MemoType.CONTEXT_URL
            sample_memo_data["content"] = "https://example.com/context"

            memo = ACPMemo.model_construct(**sample_memo_data)

            assert memo.type == MemoType.CONTEXT_URL
            assert memo.content == "https://example.com/context"

        def test_should_handle_notification_memo_type(self, sample_memo_data):
            """Should handle NOTIFICATION memo type"""
            sample_memo_data["type"] = MemoType.NOTIFICATION
            sample_memo_data["content"] = "Job started successfully"

            memo = ACPMemo.model_construct(**sample_memo_data)

            assert memo.type == MemoType.NOTIFICATION

        def test_should_handle_payable_request_memo_type(self, sample_memo_data):
            """Should handle PAYABLE_REQUEST memo type"""
            sample_memo_data["type"] = MemoType.PAYABLE_REQUEST
            sample_memo_data["payable_details"] = {
                "amount": "5000000",
                "feeAmount": "250000",
                "token": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
            }

            memo = ACPMemo.model_construct(**sample_memo_data)
            memo.model_post_init(None)

            assert memo.type == MemoType.PAYABLE_REQUEST
            assert memo.payable_details["amount"] == 5000000
            assert memo.payable_details["feeAmount"] == 250000

    class TestDifferentMemoStatuses:
        """Test different memo statuses"""

        def test_should_handle_approved_status(self, sample_memo_data):
            """Should handle APPROVED status"""
            sample_memo_data["status"] = ACPMemoStatus.APPROVED
            sample_memo_data["signed_reason"] = "Approved by evaluator"

            memo = ACPMemo.model_construct(**sample_memo_data)

            assert memo.status == ACPMemoStatus.APPROVED
            assert memo.signed_reason == "Approved by evaluator"

        def test_should_handle_rejected_status(self, sample_memo_data):
            """Should handle REJECTED status"""
            sample_memo_data["status"] = ACPMemoStatus.REJECTED
            sample_memo_data["signed_reason"] = "Does not meet requirements"

            memo = ACPMemo.model_construct(**sample_memo_data)

            assert memo.status == ACPMemoStatus.REJECTED

        def test_should_handle_expired_status(self, sample_memo_data):
            """Should handle EXPIRED status"""
            sample_memo_data["status"] = ACPMemoStatus.EXPIRED
            sample_memo_data["expiry"] = datetime.now(timezone.utc)

            memo = ACPMemo.model_construct(**sample_memo_data)

            assert memo.status == ACPMemoStatus.EXPIRED
            assert memo.expiry is not None
