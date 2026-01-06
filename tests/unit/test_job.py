import pytest
import json
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
# Import client first to trigger model_rebuild()
from virtuals_acp.client import VirtualsACP
from virtuals_acp.job import ACPJob
from virtuals_acp.memo import ACPMemo
from virtuals_acp.models import (
    ACPJobPhase,
    MemoType,
    ACPMemoStatus,
    PriceType,
    DeliverablePayload,
    FeeType,
    OperationPayload,
)
from virtuals_acp.fare import Fare, FareAmount

TEST_AGENT_ADDRESS = "0x1234567890123456789012345678901234567890"
TEST_PROVIDER_ADDRESS = "0x5555555555555555555555555555555555555555"
TEST_CONTRACT_ADDRESS = "0xABCDEF1234567890123456789012345678901234"
TEST_EVALUATOR_ADDRESS = "0x9999999999999999999999999999999999999999"


class TestACPJob:
    @pytest.fixture
    def mock_acp_client(self):
        """Create a mock VirtualsACP client"""
        client = MagicMock()
        base_fare = Fare(
            contract_address="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            decimals=6
        )
        client.config.base_fare = base_fare
        client.contract_client.config.base_fare = base_fare
        # Mock format_amount to return the value directly (for testing)
        client.contract_client_by_address.return_value.config.base_fare.format_amount = lambda x: int(
            x)
        return client

    @pytest.fixture
    def mock_contract_client(self):
        """Create a mock contract client"""
        client = MagicMock()
        client.config.base_fare = Fare(
            contract_address="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            decimals=6
        )
        return client

    @pytest.fixture
    def sample_job_data(self, mock_acp_client):
        """Sample job data for testing"""
        return {
            "acp_client": mock_acp_client,
            "id": 123,
            "client_address": TEST_AGENT_ADDRESS,
            "provider_address": TEST_PROVIDER_ADDRESS,
            "evaluator_address": TEST_EVALUATOR_ADDRESS,
            "price": 100.0,
            "price_token_address": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            "memos": [],
            "phase": ACPJobPhase.REQUEST,
            "context": {"task": "test"},
            "contract_address": TEST_CONTRACT_ADDRESS,
            "net_payable_amount": 95.0
        }

    @pytest.fixture
    def basic_job(self, sample_job_data):
        """Create a basic ACPJob instance for testing"""
        # Use model_construct to bypass Pydantic validation for mocks
        return ACPJob.model_construct(**sample_job_data)

    @pytest.fixture
    def complete_x402_response(self):
        """Provide complete X402PayableRequirements mock data"""
        return {
            "isPaymentRequired": True,
            "data": {
                "x402Version": 1,
                "error": "",
                "accepts": [{
                    "scheme": "eip-3009",
                    "network": "base",
                    "resource": "0x1111111111111111111111111111111111111111",
                    "description": "Payment for AI service",
                    "mimeType": "application/json",
                    "payTo": "0x1111111111111111111111111111111111111111",
                    "maxAmountRequired": "1000000",
                    "maxTimeoutSeconds": 300,
                    "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                    "extra": {
                        "name": "AI Service Payment",
                        "version": "1.0.0"
                    },
                    "outputSchema": {}
                }]
            }
        }

    class TestInitialization:
        """Test job initialization and model_post_init"""

        def test_should_initialize_with_all_parameters(self, sample_job_data):
            """Should correctly initialize job with all parameters"""
            job = ACPJob.model_construct(**sample_job_data)

            assert job.id == 123
            assert job.client_address == TEST_AGENT_ADDRESS
            assert job.provider_address == TEST_PROVIDER_ADDRESS
            assert job.evaluator_address == TEST_EVALUATOR_ADDRESS
            assert job.price == 100.0
            assert job.phase == ACPJobPhase.REQUEST
            assert job.context == {"task": "test"}
            assert job.contract_address == TEST_CONTRACT_ADDRESS

        def test_should_set_base_fare_from_acp_client_config(self, sample_job_data):
            """Should set _base_fare from acp_client config during init"""
            job = ACPJob.model_construct(**sample_job_data)

            assert job._base_fare is not None
            assert job._base_fare.decimals == 6

        def test_should_parse_negotiation_memo_content(self, sample_job_data, mock_contract_client):
            """Should parse requirement from NEGOTIATION memo during init"""
            negotiation_memo = MagicMock(spec=ACPMemo)
            negotiation_memo.next_phase = ACPJobPhase.NEGOTIATION
            negotiation_memo.content = json.dumps({
                "service_requirement": "Build an AI agent",
                "service_name": "AI Development",
                "price_type": "FIXED",
                "price_value": 500.0
            })

            sample_job_data["memos"] = [negotiation_memo]

            with patch('virtuals_acp.job.try_parse_json_model') as mock_parse:
                from virtuals_acp.models import RequestPayload
                mock_payload = MagicMock()
                mock_payload.service_requirement = "Build an AI agent"
                mock_payload.service_name = "AI Development"
                mock_payload.price_type = PriceType.FIXED
                mock_payload.price_value = 10.0
                mock_parse.return_value = mock_payload

                job = ACPJob.model_construct(**sample_job_data)

                assert job._requirement == "Build an AI agent"
                assert job._name == "AI Development"
                assert job._price_type == PriceType.FIXED
                assert job._price_value == 10.0

        def test_should_handle_missing_negotiation_memo(self, sample_job_data):
            """Should handle case when no NEGOTIATION memo exists"""
            job = ACPJob.model_construct(**sample_job_data)

            # Should not crash and defaults should be set
            assert job._requirement is None
            assert job._name is None
            assert job._price_type == PriceType.FIXED
            assert job._price_value == 0.0

        def test_should_handle_empty_memo_content(self, sample_job_data):
            """Should handle NEGOTIATION memo with empty content"""
            negotiation_memo = MagicMock(spec=ACPMemo)
            negotiation_memo.next_phase = ACPJobPhase.NEGOTIATION
            negotiation_memo.content = None

            sample_job_data["memos"] = [negotiation_memo]
            job = ACPJob.model_construct(**sample_job_data)

            assert job._requirement is None
            assert job._name is None

        def test_should_handle_unparseable_memo_content(self, sample_job_data):
            """Should handle NEGOTIATION memo with unparseable content"""
            negotiation_memo = MagicMock(spec=ACPMemo)
            negotiation_memo.next_phase = ACPJobPhase.NEGOTIATION
            negotiation_memo.content = "{invalid json}"

            sample_job_data["memos"] = [negotiation_memo]

            with patch('virtuals_acp.job.try_parse_json_model', return_value=None):
                job = ACPJob.model_construct(**sample_job_data)

                assert job._requirement is None
                assert job._name is None

    class TestProperties:
        """Test property accessors"""

        def test_requirement_should_return_private_attribute(self, basic_job):
            """Should return _requirement via property"""
            basic_job._requirement = "Test requirement"
            assert basic_job.requirement == "Test requirement"

        def test_name_should_return_private_attribute(self, basic_job):
            """Should return _name via property"""
            basic_job._name = "Test Job"
            assert basic_job.name == "Test Job"

        def test_price_type_should_return_private_attribute(self, basic_job):
            """Should return _price_type via property"""
            basic_job._price_type = PriceType.PERCENTAGE
            assert basic_job.price_type == PriceType.PERCENTAGE

        def test_price_value_should_return_private_attribute(self, basic_job):
            """Should return _price_value via property"""
            basic_job._price_value = 250.0
            assert basic_job.price_value == 250.0

        def test_acp_contract_client_should_return_default_client_when_no_contract_address(
            self, basic_job, mock_acp_client
        ):
            """Should return default contract client when no contract_address"""
            basic_job.contract_address = None

            result = basic_job.acp_contract_client

            assert result == mock_acp_client.contract_client

        def test_acp_contract_client_should_find_client_by_address(
            self, basic_job, mock_acp_client
        ):
            """Should find contract client by address when contract_address is set"""
            specific_client = MagicMock()
            mock_acp_client.contract_client_by_address.return_value = specific_client

            result = basic_job.acp_contract_client

            mock_acp_client.contract_client_by_address.assert_called_once_with(
                TEST_CONTRACT_ADDRESS
            )
            assert result == specific_client

        def test_config_should_return_contract_client_config(self, basic_job, mock_acp_client):
            """Should return config from acp_contract_client"""
            mock_config = MagicMock()
            mock_acp_client.contract_client_by_address.return_value.config = mock_config

            result = basic_job.config

            assert result == mock_config

        def test_base_fare_should_return_config_base_fare(self, basic_job, mock_acp_client):
            """Should return base_fare from contract client config"""
            mock_fare = Fare(
                contract_address="0x1111111111111111111111111111111111111111", decimals=18)
            mock_acp_client.contract_client_by_address.return_value.config.base_fare = mock_fare

            result = basic_job.base_fare

            assert result == mock_fare

        def test_account_should_fetch_account_by_job_id(self, basic_job, mock_acp_client):
            """Should fetch account using acp_client.get_account_by_job_id"""
            mock_account = MagicMock()
            mock_acp_client.get_account_by_job_id.return_value = mock_account

            result = basic_job.account

            mock_acp_client.get_account_by_job_id.assert_called_once_with(
                123,  # job.id
                mock_acp_client.contract_client_by_address.return_value
            )
            assert result == mock_account

        def test_deliverable_should_return_completed_memo_content(self, basic_job):
            """Should return content from COMPLETED memo"""
            memo1 = MagicMock(spec=ACPMemo)
            memo1.next_phase = ACPJobPhase.NEGOTIATION
            memo1.content = "Request"

            memo2 = MagicMock(spec=ACPMemo)
            memo2.next_phase = ACPJobPhase.COMPLETED
            memo2.content = "Deliverable result"

            basic_job.memos = [memo1, memo2]

            assert basic_job.deliverable == "Deliverable result"

        def test_deliverable_should_return_none_when_no_completed_memo(self, basic_job):
            """Should return None when no COMPLETED memo exists"""
            memo = MagicMock(spec=ACPMemo)
            memo.next_phase = ACPJobPhase.NEGOTIATION
            basic_job.memos = [memo]

            assert basic_job.deliverable is None

        def test_rejection_reason_should_return_none_when_not_rejected(self, basic_job):
            """Should return None when job phase is not REJECTED"""
            basic_job.phase = ACPJobPhase.REQUEST

            assert basic_job.rejection_reason is None

        def test_rejection_reason_should_return_signed_reason_from_request_memo(
            self, basic_job
        ):
            """Should return signed_reason from NEGOTIATION memo when rejected"""
            basic_job.phase = ACPJobPhase.REJECTED

            memo = MagicMock(spec=ACPMemo)
            memo.next_phase = ACPJobPhase.NEGOTIATION
            memo.signed_reason = "Not acceptable"

            basic_job.memos = [memo]

            assert basic_job.rejection_reason == "Not acceptable"

        def test_rejection_reason_should_fallback_to_rejected_memo_content(
            self, basic_job
        ):
            """Should return content from REJECTED memo as fallback"""
            basic_job.phase = ACPJobPhase.REJECTED

            memo = MagicMock(spec=ACPMemo)
            memo.next_phase = ACPJobPhase.REJECTED
            memo.content = "Fallback reason"

            basic_job.memos = [memo]

            assert basic_job.rejection_reason == "Fallback reason"

        def test_provider_agent_should_fetch_agent_by_provider_address(
            self, basic_job, mock_acp_client
        ):
            """Should fetch provider agent using get_agent"""
            mock_agent = MagicMock()
            mock_acp_client.get_agent.return_value = mock_agent

            result = basic_job.provider_agent

            mock_acp_client.get_agent.assert_called_once_with(
                TEST_PROVIDER_ADDRESS)
            assert result == mock_agent

        def test_client_agent_should_fetch_agent_by_client_address(
            self, basic_job, mock_acp_client
        ):
            """Should fetch client agent using get_agent"""
            mock_agent = MagicMock()
            mock_acp_client.get_agent.return_value = mock_agent

            result = basic_job.client_agent

            mock_acp_client.get_agent.assert_called_once_with(
                TEST_AGENT_ADDRESS)
            assert result == mock_agent

        def test_evaluator_agent_should_fetch_agent_by_evaluator_address(
            self, basic_job, mock_acp_client
        ):
            """Should fetch evaluator agent using get_agent"""
            mock_agent = MagicMock()
            mock_acp_client.get_agent.return_value = mock_agent

            result = basic_job.evaluator_agent

            mock_acp_client.get_agent.assert_called_once_with(
                TEST_EVALUATOR_ADDRESS)
            assert result == mock_agent

        def test_latest_memo_should_return_last_memo(self, basic_job):
            """Should return the last memo in the list"""
            memo1 = MagicMock(spec=ACPMemo)
            memo2 = MagicMock(spec=ACPMemo)
            memo3 = MagicMock(spec=ACPMemo)

            basic_job.memos = [memo1, memo2, memo3]

            assert basic_job.latest_memo == memo3

        def test_latest_memo_should_return_none_when_no_memos(self, basic_job):
            """Should return None when memos list is empty"""
            basic_job.memos = []

            assert basic_job.latest_memo is None

    class TestGetMemoById:
        """Test _get_memo_by_id method"""

        def test_should_return_memo_with_matching_id(self, basic_job):
            """Should return memo that matches the ID"""
            memo1 = MagicMock(spec=ACPMemo)
            memo1.id = "1"

            memo2 = MagicMock(spec=ACPMemo)
            memo2.id = "2"

            memo3 = MagicMock(spec=ACPMemo)
            memo3.id = "3"

            basic_job.memos = [memo1, memo2, memo3]

            result = basic_job._get_memo_by_id("2")

            assert result == memo2

        def test_should_return_none_when_no_match(self, basic_job):
            """Should return None when no memo matches the ID"""
            memo = MagicMock(spec=ACPMemo)
            memo.id = "1"

            basic_job.memos = [memo]

            result = basic_job._get_memo_by_id("999")

            assert result is None

    class TestStr:
        """Test __str__ method"""

        def test_should_return_formatted_string(self, basic_job):
            """Should return properly formatted job string representation"""
            result = str(basic_job)

            assert "AcpJob(" in result
            assert "id=123" in result
            assert f"client_address='{TEST_AGENT_ADDRESS}'" in result
            assert f"provider_address='{TEST_PROVIDER_ADDRESS}'" in result
            assert "price=100.0" in result
            assert "phase=" in result
            assert "context=" in result

    class TestCreateRequirement:
        """Test create_requirement method"""

        def test_should_create_memo_and_return_txn_hash(
            self, basic_job, mock_acp_client
        ):
            """Should create MESSAGE memo with TRANSACTION phase"""
            mock_operation = MagicMock(spec=OperationPayload)
            mock_contract_client = mock_acp_client.contract_client_by_address.return_value
            mock_contract_client.create_memo.return_value = mock_operation
            mock_contract_client.handle_operation.return_value = {
                "hash": "0xabc123"}

            with patch('virtuals_acp.job.get_txn_hash_from_response', return_value="0xabc123"):
                result = basic_job.create_requirement("Test requirement")

            # Verify create_memo was called correctly
            mock_contract_client.create_memo.assert_called_once_with(
                job_id=123,
                content="Test requirement",
                memo_type=MemoType.MESSAGE,
                is_secured=False,
                next_phase=ACPJobPhase.TRANSACTION
            )

            # Verify operation was handled
            mock_contract_client.handle_operation.assert_called_once_with([
                                                                          mock_operation])

            assert result == "0xabc123"

    class TestAccept:
        """Test accept method"""

        def test_should_sign_latest_memo_with_accept(self, basic_job):
            """Should sign the latest NEGOTIATION memo with True"""
            mock_memo = MagicMock(spec=ACPMemo)
            mock_memo.next_phase = ACPJobPhase.NEGOTIATION
            mock_memo.sign.return_value = "0xtxhash"

            basic_job.memos = [mock_memo]

            result = basic_job.accept("Looks good")

            mock_memo.sign.assert_called_once_with(
                True,
                "Job 123 accepted. Looks good"
            )
            assert result == "0xtxhash"

        def test_should_raise_error_when_no_negotiation_memo(self, basic_job):
            """Should raise ValueError when no NEGOTIATION memo found"""
            mock_memo = MagicMock(spec=ACPMemo)
            mock_memo.next_phase = ACPJobPhase.TRANSACTION

            basic_job.memos = [mock_memo]

            with pytest.raises(ValueError, match="No request memo found"):
                basic_job.accept("Test")

        def test_should_raise_error_when_no_memos(self, basic_job):
            """Should raise ValueError when memos list is empty"""
            basic_job.memos = []

            with pytest.raises(ValueError, match="No request memo found"):
                basic_job.accept("Test")

    class TestReject:
        """Test reject method"""

        def test_should_sign_latest_memo_when_in_request_phase(self, basic_job):
            """Should sign memo with False when in REQUEST phase"""
            basic_job.phase = ACPJobPhase.REQUEST

            mock_memo = MagicMock(spec=ACPMemo)
            mock_memo.next_phase = ACPJobPhase.NEGOTIATION
            mock_memo.sign.return_value = "0xtxhash"

            basic_job.memos = [mock_memo]

            result = basic_job.reject("Not interested")

            mock_memo.sign.assert_called_once_with(
                False,
                "Job 123 rejected. Not interested"
            )
            assert result == "0xtxhash"

        def test_should_create_rejected_memo_when_not_in_request_phase(
            self, basic_job, mock_acp_client
        ):
            """Should create new REJECTED memo when not in REQUEST phase"""
            basic_job.phase = ACPJobPhase.TRANSACTION

            mock_operation = MagicMock(spec=OperationPayload)
            mock_contract_client = mock_acp_client.contract_client_by_address.return_value
            mock_contract_client.create_memo.return_value = mock_operation
            mock_contract_client.handle_operation.return_value = {
                "hash": "0xdef456"}

            mock_memo = MagicMock(spec=ACPMemo)
            mock_memo.next_phase = ACPJobPhase.TRANSACTION
            basic_job.memos = [mock_memo]

            with patch('virtuals_acp.job.get_txn_hash_from_response', return_value="0xdef456"):
                result = basic_job.reject("Failed")

            mock_contract_client.create_memo.assert_called_once_with(
                job_id=123,
                content="Job 123 rejected. Failed",
                memo_type=MemoType.MESSAGE,
                is_secured=True,
                next_phase=ACPJobPhase.REJECTED
            )

            assert result == "0xdef456"

    class TestDeliver:
        """Test deliver method"""

        def test_should_create_completed_memo_with_deliverable(
            self, basic_job, mock_acp_client
        ):
            """Should create COMPLETED memo with deliverable payload"""
            mock_memo = MagicMock(spec=ACPMemo)
            mock_memo.next_phase = ACPJobPhase.EVALUATION
            basic_job.memos = [mock_memo]

            mock_operation = MagicMock(spec=OperationPayload)
            mock_contract_client = mock_acp_client.contract_client_by_address.return_value
            mock_contract_client.create_memo.return_value = mock_operation
            mock_contract_client.handle_operation.return_value = {
                "hash": "0xdelivery"}

            # DeliverablePayload is Union[str, Dict], so just use a dict
            deliverable = {"result": "Task completed successfully"}

            with patch('virtuals_acp.job.prepare_payload', return_value='{"result": "Task completed successfully"}'):
                with patch('virtuals_acp.job.get_txn_hash_from_response', return_value="0xdelivery"):
                    result = basic_job.deliver(deliverable)

            mock_contract_client.create_memo.assert_called_once()
            assert result == "0xdelivery"

        def test_should_raise_error_when_no_evaluation_memo(self, basic_job):
            """Should raise ValueError when latest memo is not EVALUATION phase"""
            mock_memo = MagicMock(spec=ACPMemo)
            mock_memo.next_phase = ACPJobPhase.TRANSACTION
            basic_job.memos = [mock_memo]

            # DeliverablePayload is Union[str, Dict], so just use a string
            deliverable = "Test deliverable"

            with pytest.raises(ValueError, match="No transaction memo found"):
                basic_job.deliver(deliverable)

    class TestEvaluate:
        """Test evaluate method"""

        def test_should_sign_latest_completed_memo_with_accept(self, basic_job):
            """Should sign COMPLETED memo with True when accepting"""
            mock_memo = MagicMock(spec=ACPMemo)
            mock_memo.next_phase = ACPJobPhase.COMPLETED
            mock_memo.sign.return_value = "0xeval"

            basic_job.memos = [mock_memo]

            result = basic_job.evaluate(True, "Great work")

            mock_memo.sign.assert_called_once_with(True, "Great work")
            assert result == "0xeval"

        def test_should_use_default_reason_when_not_provided(self, basic_job):
            """Should use default reason when none provided"""
            mock_memo = MagicMock(spec=ACPMemo)
            mock_memo.next_phase = ACPJobPhase.COMPLETED
            mock_memo.sign.return_value = "0xeval"

            basic_job.memos = [mock_memo]

            basic_job.evaluate(False)

            call_args = mock_memo.sign.call_args[0]
            assert call_args[0] is False
            assert "rejected" in call_args[1]

        def test_should_raise_error_when_no_completed_memo(self, basic_job):
            """Should raise ValueError when no COMPLETED memo found"""
            mock_memo = MagicMock(spec=ACPMemo)
            mock_memo.next_phase = ACPJobPhase.EVALUATION
            basic_job.memos = [mock_memo]

            with pytest.raises(ValueError, match="No evaluation memo found"):
                basic_job.evaluate(True)

    class TestCreateNotification:
        """Test create_notification method"""

        def test_should_create_notification_memo(self, basic_job, mock_acp_client):
            """Should create NOTIFICATION memo with COMPLETED phase"""
            mock_operation = MagicMock(spec=OperationPayload)
            mock_contract_client = mock_acp_client.contract_client_by_address.return_value
            mock_contract_client.create_memo.return_value = mock_operation
            mock_contract_client.handle_operation.return_value = {
                "hash": "0xnotif"}

            with patch('virtuals_acp.job.get_txn_hash_from_response', return_value="0xnotif"):
                result = basic_job.create_notification("Job started")

            mock_contract_client.create_memo.assert_called_once_with(
                job_id=123,
                content="Job started",
                memo_type=MemoType.NOTIFICATION,
                is_secured=True,
                next_phase=ACPJobPhase.COMPLETED
            )

            assert result == "0xnotif"

    class TestCreatePayableRequirement:
        """Test create_payable_requirement method"""

        def test_should_create_payable_request_with_percentage_fee(
            self, basic_job, mock_acp_client
        ):
            """Should create PAYABLE_REQUEST with percentage fee"""
            basic_job._price_type = PriceType.PERCENTAGE
            basic_job._price_value = 0.05  # 5%

            mock_memo = MagicMock(spec=ACPMemo)
            mock_memo.id = 999
            mock_contract_client = mock_acp_client.contract_client_by_address.return_value
            mock_contract_client.create_payable_memo.return_value = mock_memo
            mock_contract_client.handle_operation.return_value = {
                "hash": "0xpayable"}

            fare = FareAmount(1000000, basic_job.base_fare)  # 1 USDC

            with patch('virtuals_acp.job.get_txn_hash_from_response', return_value="0xpayable"):
                result = basic_job.create_payable_requirement(
                    "Payment request",
                    MemoType.PAYABLE_REQUEST,
                    fare,
                    "0x7777777777777777777777777777777777777777"
                )

            # Verify percentage fee was calculated (5% = 500 basis points)
            call_args = mock_contract_client.create_payable_memo.call_args[1]
            assert call_args['fee_amount_base_unit'] == int(0.05 * 10000)
            assert call_args['fee_type'] == FeeType.PERCENTAGE_FEE
            assert result == "0xpayable"

        def test_should_create_payable_transfer_escrow_with_approval(
            self, basic_job, mock_acp_client
        ):
            """Should create PAYABLE_TRANSFER_ESCROW with token approval"""
            mock_approve_op = MagicMock(spec=OperationPayload)
            mock_payable_memo = MagicMock(spec=ACPMemo)
            mock_payable_memo.id = 999
            mock_contract_client = mock_acp_client.contract_client_by_address.return_value
            mock_contract_client.approve_allowance.return_value = mock_approve_op
            mock_contract_client.create_payable_memo.return_value = mock_payable_memo
            mock_contract_client.handle_operation.return_value = {
                "hash": "0xescrow"}

            fare = FareAmount(5000000, basic_job.base_fare)  # 5 USDC

            with patch('virtuals_acp.job.get_txn_hash_from_response', return_value="0xEscrow"):
                result = basic_job.create_payable_requirement(
                    "Escrow payment",
                    MemoType.PAYABLE_TRANSFER_ESCROW,
                    fare,
                    "0x7777777777777777777777777777777777777777"
                )

            # Verify approval was called first
            mock_contract_client.approve_allowance.assert_called_once_with(
                5000000,
                fare.fare.contract_address
            )

            # Verify handle_operation was called with both operations
            operations = mock_contract_client.handle_operation.call_args[0][0]
            assert len(operations) == 2
            assert result == "0xEscrow"

        def test_should_use_default_expiry_when_not_provided(
            self, basic_job, mock_acp_client
        ):
            """Should set expiry to 5 minutes from now if not provided"""
            from datetime import datetime, timezone, timedelta

            mock_memo = MagicMock(spec=ACPMemo)
            mock_memo.id = 999
            mock_contract_client = mock_acp_client.contract_client_by_address.return_value
            mock_contract_client.create_payable_memo.return_value = mock_memo
            mock_contract_client.handle_operation.return_value = {
                "hash": "0xtx"}

            fare = FareAmount(1000000, basic_job.base_fare)

            before = datetime.now(timezone.utc) + timedelta(minutes=5)

            with patch('virtuals_acp.job.get_txn_hash_from_response', return_value="0xtx"):
                basic_job.create_payable_requirement(
                    "Test",
                    MemoType.PAYABLE_REQUEST,
                    fare,
                    "0x7777777777777777777777777777777777777777"
                    # Note: no expired_at provided
                )

            after = datetime.now(timezone.utc) + timedelta(minutes=5)

            # Verify expired_at is around 5 minutes from now
            call_args = mock_contract_client.create_payable_memo.call_args[1]
            expired_at = call_args['expired_at']
            assert before <= expired_at <= after

    class TestPayAndAcceptRequirement:
        """Test pay_and_accept_requirement method"""

        def test_should_approve_and_sign_memo(self, basic_job, mock_acp_client):
            """Should approve allowance and sign memo"""
            # Setup transaction memo
            mock_memo = MagicMock(spec=ACPMemo)
            mock_memo.id = 999
            mock_memo.next_phase = ACPJobPhase.TRANSACTION
            mock_memo.payable_details = None
            basic_job.memos = [mock_memo]

            mock_approve_op = MagicMock(spec=OperationPayload)
            mock_sign_op = MagicMock(spec=OperationPayload)
            mock_create_op = MagicMock(spec=OperationPayload)

            mock_contract_client = mock_acp_client.contract_client_by_address.return_value
            mock_contract_client.approve_allowance.return_value = mock_approve_op
            mock_contract_client.sign_memo.return_value = mock_sign_op
            mock_contract_client.create_memo.return_value = mock_create_op
            mock_contract_client.handle_operation.return_value = {
                "hash": "0xpay"}

            # Mock x402 check
            mock_x402_details = MagicMock()
            mock_x402_details.is_x402 = False
            mock_contract_client.get_x402_payment_details.return_value = mock_x402_details

            with patch('virtuals_acp.job.get_txn_hash_from_response', return_value="0xpay"):
                result = basic_job.pay_and_accept_requirement("Payment made")

            # Verify approval, sign, and memo creation
            assert mock_contract_client.approve_allowance.called
            assert mock_contract_client.sign_memo.called
            assert mock_contract_client.create_memo.called
            assert result == "0xpay"

        def test_should_handle_payable_details_with_different_token(
            self, basic_job, mock_acp_client
        ):
            """Should approve both tokens when payable uses different token"""
            # Setup transaction memo with payable details in different token
            mock_memo = MagicMock(spec=ACPMemo)
            mock_memo.id = 999
            mock_memo.next_phase = ACPJobPhase.TRANSACTION
            mock_memo.payable_details = {
                "amount": "2000000",  # 2 USDC
                "token": "0x9999999999999999999999999999999999999999"  # Different token
            }
            basic_job.memos = [mock_memo]

            mock_contract_client = mock_acp_client.contract_client_by_address.return_value
            mock_contract_client.approve_allowance.return_value = MagicMock()
            mock_contract_client.sign_memo.return_value = MagicMock()
            mock_contract_client.create_memo.return_value = MagicMock()
            mock_contract_client.handle_operation.return_value = {
                "hash": "0xpay"}

            mock_x402_details = MagicMock()
            mock_x402_details.is_x402 = False
            mock_contract_client.get_x402_payment_details.return_value = mock_x402_details

            # Mock FareAmountBase.from_contract_address to return proper value
            mock_transfer_amount = MagicMock()
            mock_transfer_amount.amount = 2000000
            mock_transfer_fare = Fare(
                contract_address="0x9999999999999999999999999999999999999999", decimals=6)
            mock_transfer_amount.fare = mock_transfer_fare

            with patch('virtuals_acp.job.FareAmountBase.from_contract_address', return_value=mock_transfer_amount):
                with patch('virtuals_acp.job.get_txn_hash_from_response', return_value="0xpay"):
                    basic_job.pay_and_accept_requirement()

            # Verify two approvals (base fare + transfer amount)
            assert mock_contract_client.approve_allowance.call_count == 2

        def test_should_perform_x402_payment_when_is_x402_job(
            self, basic_job, mock_acp_client, complete_x402_response
        ):
            """Should call perform_x402_payment when job is x402"""
            mock_memo = MagicMock(spec=ACPMemo)
            mock_memo.id = 999
            mock_memo.next_phase = ACPJobPhase.TRANSACTION
            mock_memo.payable_details = None
            basic_job.memos = [mock_memo]

            mock_contract_client = mock_acp_client.contract_client_by_address.return_value
            mock_contract_client.approve_allowance.return_value = MagicMock()
            mock_contract_client.sign_memo.return_value = MagicMock()
            mock_contract_client.create_memo.return_value = MagicMock()
            mock_contract_client.handle_operation.return_value = {
                "hash": "0xpay"}

            # Mock x402 job - setup all dependencies
            mock_x402_details = MagicMock()
            mock_x402_details.is_x402 = True
            mock_contract_client.get_x402_payment_details.return_value = mock_x402_details

            # Mock x402 payment flow
            mock_contract_client.get_acp_version.return_value = "1.0.0"
            mock_contract_client.perform_x402_request.return_value = complete_x402_response

            mock_x402_payment = MagicMock()
            mock_x402_payment.encodedPayment = "0xencodedpayment"
            mock_x402_payment.signature = "0xsignature"
            mock_x402_payment.message = {
                "from": "0xfrom",
                "to": "0xto",
                "value": "1000000",
                "validAfter": 0,
                "validBefore": 9999999999,
                "nonce": "123456"
            }
            mock_contract_client.generate_x402_payment.return_value = mock_x402_payment
            mock_contract_client.submit_transfer_with_authorization.return_value = [
                MagicMock()]

            # Mock polling - budget received immediately
            mock_payment_details = MagicMock()
            mock_payment_details.is_budget_received = True
            mock_contract_client.get_x402_payment_details.return_value = mock_payment_details

            with patch('virtuals_acp.job.get_txn_hash_from_response', return_value="0xpay"):
                with patch('time.sleep'):  # Don't actually sleep
                    basic_job.pay_and_accept_requirement()

            # Verify x402 methods were called
            assert mock_contract_client.perform_x402_request.called
            assert mock_contract_client.generate_x402_payment.called

        def test_should_raise_error_when_no_transaction_memo(self, basic_job):
            """Should raise exception when no TRANSACTION memo found"""
            basic_job.memos = []

            with pytest.raises(Exception, match="No negotiation memo found"):
                basic_job.pay_and_accept_requirement()

    class TestRejectPayable:
        """Test reject_payable method"""

        def test_should_create_payable_rejection_with_refund(
            self, basic_job, mock_acp_client
        ):
            """Should create PAYABLE_TRANSFER for refund with NO_FEE"""
            mock_approve_op = MagicMock(spec=OperationPayload)
            mock_payable_op = MagicMock(spec=OperationPayload)

            mock_contract_client = mock_acp_client.contract_client_by_address.return_value
            mock_contract_client.approve_allowance.return_value = mock_approve_op
            mock_contract_client.create_payable_memo.return_value = mock_payable_op
            mock_contract_client.handle_operation.return_value = {
                "hash": "0xrefund"}

            fare = FareAmount(3000000, basic_job.base_fare)

            with patch('virtuals_acp.job.get_txn_hash_from_response', return_value="0xrefund"):
                result = basic_job.reject_payable(
                    "Rejecting with refund",
                    fare
                )

            # Verify approval and payable memo creation
            mock_contract_client.approve_allowance.assert_called_once()

            call_args = mock_contract_client.create_payable_memo.call_args[1]
            assert call_args['next_phase'] == ACPJobPhase.REJECTED
            assert call_args['memo_type'] == MemoType.PAYABLE_TRANSFER
            assert call_args['fee_type'] == FeeType.NO_FEE
            assert call_args['recipient'] == basic_job.client_address
            assert result == "0xrefund"

    class TestDeliverPayable:
        """Test deliver_payable method"""

        def test_should_create_payable_delivery_with_percentage_fee(
            self, basic_job, mock_acp_client
        ):
            """Should create PAYABLE_TRANSFER with percentage fee when applicable"""
            basic_job._price_type = PriceType.PERCENTAGE
            basic_job._price_value = 0.10  # 10%

            mock_memo = MagicMock(spec=ACPMemo)
            mock_memo.next_phase = ACPJobPhase.EVALUATION
            basic_job.memos = [mock_memo]

            mock_contract_client = mock_acp_client.contract_client_by_address.return_value
            mock_contract_client.approve_allowance.return_value = MagicMock()
            mock_contract_client.create_payable_memo.return_value = MagicMock()
            mock_contract_client.handle_operation.return_value = {
                "hash": "0xdeliver"}

            fare = FareAmount(10000000, basic_job.base_fare)

            with patch('virtuals_acp.job.prepare_payload', return_value='{"result": "done"}'):
                with patch('virtuals_acp.job.get_txn_hash_from_response', return_value="0xdeliver"):
                    result = basic_job.deliver_payable(
                        {"result": "done"},
                        fare
                    )

            # Verify percentage fee (10% = 1000 basis points)
            call_args = mock_contract_client.create_payable_memo.call_args[1]
            assert call_args['fee_amount_base_unit'] == int(0.10 * 10000)
            assert call_args['fee_type'] == FeeType.PERCENTAGE_FEE
            assert result == "0xdeliver"

        def test_should_skip_fee_when_requested(self, basic_job, mock_acp_client):
            """Should use NO_FEE when skip_fee is True"""
            basic_job._price_type = PriceType.PERCENTAGE
            basic_job._price_value = 0.10

            mock_memo = MagicMock(spec=ACPMemo)
            mock_memo.next_phase = ACPJobPhase.EVALUATION
            basic_job.memos = [mock_memo]

            mock_contract_client = mock_acp_client.contract_client_by_address.return_value
            mock_contract_client.approve_allowance.return_value = MagicMock()
            mock_contract_client.create_payable_memo.return_value = MagicMock()
            mock_contract_client.handle_operation.return_value = {
                "hash": "0xdeliver"}

            fare = FareAmount(10000000, basic_job.base_fare)

            with patch('virtuals_acp.job.prepare_payload', return_value='{}'):
                with patch('virtuals_acp.job.get_txn_hash_from_response', return_value="0xdeliver"):
                    basic_job.deliver_payable(
                        {},
                        fare,
                        skip_fee=True
                    )

            # Verify NO_FEE was used
            call_args = mock_contract_client.create_payable_memo.call_args[1]
            assert call_args['fee_type'] == FeeType.NO_FEE

        def test_should_raise_error_when_no_evaluation_memo(self, basic_job):
            """Should raise ValueError when not in EVALUATION phase"""
            mock_memo = MagicMock(spec=ACPMemo)
            mock_memo.next_phase = ACPJobPhase.TRANSACTION
            basic_job.memos = [mock_memo]

            fare = FareAmount(1000000, basic_job.base_fare)

            with pytest.raises(ValueError, match="No transaction memo found"):
                basic_job.deliver_payable({}, fare)

    class TestCreatePayableNotification:
        """Test create_payable_notification method"""

        def test_should_create_payable_notification_with_fee(
            self, basic_job, mock_acp_client
        ):
            """Should create PAYABLE_NOTIFICATION with appropriate fee"""
            basic_job._price_type = PriceType.PERCENTAGE
            basic_job._price_value = 0.03

            mock_contract_client = mock_acp_client.contract_client_by_address.return_value
            mock_contract_client.approve_allowance.return_value = MagicMock()
            mock_contract_client.create_payable_memo.return_value = MagicMock()
            mock_contract_client.handle_operation.return_value = {
                "hash": "0xnotif"}

            fare = FareAmount(2000000, basic_job.base_fare)

            with patch('virtuals_acp.job.get_txn_hash_from_response', return_value="0xnotif"):
                result = basic_job.create_payable_notification(
                    "Milestone reached",
                    fare
                )

            call_args = mock_contract_client.create_payable_memo.call_args[1]
            assert call_args['memo_type'] == MemoType.PAYABLE_NOTIFICATION
            assert call_args['next_phase'] == ACPJobPhase.COMPLETED
            assert result == "0xnotif"

    class TestPerformX402Payment:
        """Test perform_x402_payment method"""

        def test_should_skip_when_payment_not_required(
            self, basic_job, mock_acp_client
        ):
            """Should return early when isPaymentRequired is False"""
            mock_contract_client = mock_acp_client.contract_client_by_address.return_value
            mock_contract_client.perform_x402_request.return_value = {
                "isPaymentRequired": False
            }
            mock_contract_client.get_acp_version.return_value = "1.0.0"

            # Should complete without error
            basic_job.perform_x402_payment(100.0)

            # Verify only one API call was made
            assert mock_contract_client.perform_x402_request.call_count == 1

        def test_should_perform_x402_payment_flow(
            self, basic_job, mock_acp_client, complete_x402_response
        ):
            """Should perform full x402 payment flow"""
            mock_contract_client = mock_acp_client.contract_client_by_address.return_value
            mock_contract_client.get_acp_version.return_value = "1.0.0"

            # First request returns payment required
            mock_contract_client.perform_x402_request.side_effect = [
                complete_x402_response,
                {
                    "isPaymentRequired": True  # Still requires payment after auth
                }
            ]

            # Mock x402 payment generation
            mock_x402_payment = MagicMock()
            mock_x402_payment.encodedPayment = "0xencodedpayment"
            mock_x402_payment.signature = "0xsignature"
            mock_x402_payment.message = {
                "from": "0xfrom",
                "to": "0xto",
                "value": "1000000",
                "validAfter": 0,
                "validBefore": 9999999999,
                "nonce": "123456"
            }
            mock_contract_client.generate_x402_payment.return_value = mock_x402_payment

            # Mock operations
            mock_contract_client.submit_transfer_with_authorization.return_value = [
                MagicMock()]
            mock_contract_client.handle_operation.return_value = {
                "hash": "0xtx"}

            # Mock polling - budget received on first check
            mock_payment_details = MagicMock()
            mock_payment_details.is_budget_received = True
            mock_contract_client.get_x402_payment_details.return_value = mock_payment_details

            with patch('time.sleep'):  # Don't actually sleep
                basic_job.perform_x402_payment(100.0)

            # Verify nonce was updated
            mock_contract_client.update_job_x402_nonce.assert_called_once_with(
                basic_job.id,
                "123456"
            )

            # Verify transfer was submitted
            mock_contract_client.submit_transfer_with_authorization.assert_called_once()
            mock_contract_client.handle_operation.assert_called_once()

        def test_should_poll_until_budget_received(
            self, basic_job, mock_acp_client, complete_x402_response
        ):
            """Should poll multiple times until budget is received"""
            mock_contract_client = mock_acp_client.contract_client_by_address.return_value
            mock_contract_client.get_acp_version.return_value = "1.0.0"

            mock_contract_client.perform_x402_request.side_effect = [
                complete_x402_response,
                {"isPaymentRequired": False}  # Payment successful
            ]

            mock_x402_payment = MagicMock()
            mock_x402_payment.encodedPayment = "0xencodedpayment"
            mock_x402_payment.signature = "0xsignature"
            mock_x402_payment.message = {"nonce": "123456"}
            mock_contract_client.generate_x402_payment.return_value = mock_x402_payment

            # Mock polling - not received, not received, then received
            mock_payment_details_not_received = MagicMock()
            mock_payment_details_not_received.is_budget_received = False

            mock_payment_details_received = MagicMock()
            mock_payment_details_received.is_budget_received = True

            mock_contract_client.get_x402_payment_details.side_effect = [
                mock_payment_details_not_received,
                mock_payment_details_not_received,
                mock_payment_details_received
            ]

            with patch('time.sleep') as mock_sleep:
                basic_job.perform_x402_payment(100.0)

            # Verify polling happened multiple times
            assert mock_contract_client.get_x402_payment_details.call_count == 3
            # Verify sleep was called (exponential backoff)
            assert mock_sleep.call_count == 2

        def test_should_timeout_after_max_iterations(
            self, basic_job, mock_acp_client, complete_x402_response
        ):
            """Should raise exception after max polling iterations"""
            mock_contract_client = mock_acp_client.contract_client_by_address.return_value
            mock_contract_client.get_acp_version.return_value = "1.0.0"

            mock_contract_client.perform_x402_request.side_effect = [
                complete_x402_response,
                {"isPaymentRequired": False}
            ]

            mock_x402_payment = MagicMock()
            mock_x402_payment.encodedPayment = "0xencodedpayment"
            mock_x402_payment.signature = "0xsignature"
            mock_x402_payment.message = {"nonce": "123456"}
            mock_contract_client.generate_x402_payment.return_value = mock_x402_payment

            # Mock polling - never receives budget
            mock_payment_details = MagicMock()
            mock_payment_details.is_budget_received = False
            mock_contract_client.get_x402_payment_details.return_value = mock_payment_details

            with patch('time.sleep'):
                with pytest.raises(Exception, match="X402 payment timed out"):
                    basic_job.perform_x402_payment(100.0)

        def test_should_raise_error_when_no_accepts(
            self, basic_job, mock_acp_client
        ):
            """Should raise exception when no payment requirements"""
            mock_contract_client = mock_acp_client.contract_client_by_address.return_value
            mock_contract_client.get_acp_version.return_value = "1.0.0"

            mock_contract_client.perform_x402_request.return_value = {
                "isPaymentRequired": True,
                "data": {
                    "accepts": []  # No payment methods
                }
            }

            with pytest.raises(Exception, match="No X402 payment requirements found"):
                basic_job.perform_x402_payment(100.0)

        def test_should_raise_error_when_no_nonce(
            self, basic_job, mock_acp_client, complete_x402_response
        ):
            """Should raise exception when nonce is missing"""
            mock_contract_client = mock_acp_client.contract_client_by_address.return_value
            mock_contract_client.get_acp_version.return_value = "1.0.0"

            mock_contract_client.perform_x402_request.return_value = complete_x402_response

            mock_x402_payment = MagicMock()
            mock_x402_payment.encodedPayment = "0xencodedpayment"
            mock_x402_payment.signature = "0xsignature"
            mock_x402_payment.message = None  # No message/nonce
            mock_contract_client.generate_x402_payment.return_value = mock_x402_payment

            with pytest.raises(Exception, match="No nonce found in X402 message"):
                basic_job.perform_x402_payment(100.0)

    class TestRespond:
        """Test respond method"""

        def test_should_accept_and_create_requirement_when_true(
            self, basic_job, mock_acp_client
        ):
            """Should call accept and create_requirement when accept=True"""
            mock_memo = MagicMock(spec=ACPMemo)
            mock_memo.next_phase = ACPJobPhase.NEGOTIATION
            mock_memo.sign.return_value = "0xaccept"
            basic_job.memos = [mock_memo]

            # Mock the contract client for create_requirement
            mock_operation = MagicMock(spec=OperationPayload)
            mock_contract_client = mock_acp_client.contract_client_by_address.return_value
            mock_contract_client.create_memo.return_value = mock_operation
            mock_contract_client.handle_operation.return_value = {
                "hash": "0xreq"}

            with patch('virtuals_acp.job.get_txn_hash_from_response', return_value="0xreq"):
                result = basic_job.respond(True, "Good")

            # Verify memo.sign was called (from accept)
            # Note: respond() creates "Job 123 accepted. Good" and passes it to accept()
            # which prepends "Job 123 accepted." again
            mock_memo.sign.assert_called_once_with(
                True, "Job 123 accepted. Job 123 accepted. Good")

            # Verify create_memo was called (from create_requirement)
            mock_contract_client.create_memo.assert_called_once()

            assert result == "0xreq"

        def test_should_reject_when_false(self, basic_job):
            """Should call reject when accept=False"""
            basic_job.phase = ACPJobPhase.REQUEST
            mock_memo = MagicMock(spec=ACPMemo)
            mock_memo.next_phase = ACPJobPhase.NEGOTIATION
            mock_memo.sign.return_value = "0xreject"
            basic_job.memos = [mock_memo]

            result = basic_job.respond(False, "Not interested")

            # Verify memo.sign was called with False
            # Note: respond() creates "Job 123 rejected. Not interested" and passes it to reject()
            # which prepends "Job 123 rejected." again
            mock_memo.sign.assert_called_once_with(
                False, "Job 123 rejected. Job 123 rejected. Not interested")
            assert result == "0xreject"
