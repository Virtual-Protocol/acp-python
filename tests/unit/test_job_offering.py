import pytest
import json
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
from web3.constants import ADDRESS_ZERO

# Import client first to trigger model_rebuild()
from virtuals_acp.client import VirtualsACP
from virtuals_acp.job_offering import ACPJobOffering, ACPResourceOffering
from virtuals_acp.fare import Fare
from virtuals_acp.models import PriceType, ACPJobPhase, MemoType
from virtuals_acp.configs.configs import (
    BASE_SEPOLIA_CONFIG,
    BASE_MAINNET_CONFIG,
    BASE_SEPOLIA_ACP_X402_CONFIG,
    BASE_MAINNET_ACP_X402_CONFIG
)

TEST_AGENT_ADDRESS = "0x1234567890123456789012345678901234567890"
TEST_PROVIDER_ADDRESS = "0x5555555555555555555555555555555555555555"
TEST_CONTRACT_ADDRESS = "0xABCDEF1234567890123456789012345678901234"
TEST_EVALUATOR_ADDRESS = "0x9999999999999999999999999999999999999999"
TEST_USDC_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"


class TestACPJobOffering:
    """Test suite for ACPJobOffering class"""

    @pytest.fixture
    def mock_acp_client(self):
        """Create a mock VirtualsACP client"""
        client = MagicMock(spec=VirtualsACP)
        return client

    @pytest.fixture
    def mock_contract_client(self):
        """Create a mock contract client"""
        client = MagicMock()
        client.config.base_fare = Fare(
            contract_address=TEST_USDC_ADDRESS,
            decimals=6
        )
        client.config.chain_id = 8453  # Use integer, not string
        client.config.contract_address = TEST_CONTRACT_ADDRESS
        client.agent_wallet_address = TEST_AGENT_ADDRESS
        return client

    @pytest.fixture
    def basic_offering(self, mock_acp_client, mock_contract_client):
        """Create a basic ACPJobOffering instance"""
        # Use model_construct to bypass Pydantic validation for mocks
        return ACPJobOffering.model_construct(
            acp_client=mock_acp_client,
            contract_client=mock_contract_client,
            provider_address=TEST_PROVIDER_ADDRESS,
            name="Test Service",
            price=10.0,
            price_type=PriceType.FIXED,
            requirement=None,
            deliverable=None
        )

    @pytest.fixture
    def offering_with_schema(self, mock_acp_client, mock_contract_client):
        """Create offering with requirement schema"""
        # Use model_construct to bypass Pydantic validation for mocks
        return ACPJobOffering.model_construct(
            acp_client=mock_acp_client,
            contract_client=mock_contract_client,
            provider_address=TEST_PROVIDER_ADDRESS,
            name="Test Service",
            price=10.0,
            price_type=PriceType.FIXED,
            requirement={
                "type": "object",
                "properties": {
                    "task": {"type": "string"},
                    "count": {"type": "number"}
                },
                "required": ["task"]
            },
            deliverable=None
        )

    class TestInitialization:
        """Test ACPJobOffering initialization"""

        def test_should_initialize_with_required_parameters(
            self, mock_acp_client, mock_contract_client
        ):
            """Should initialize with all required parameters"""
            offering = ACPJobOffering.model_construct(
                acp_client=mock_acp_client,
                contract_client=mock_contract_client,
                provider_address=TEST_PROVIDER_ADDRESS,
                name="Test Service",
                price=10.0,
                price_type=PriceType.FIXED,
                requirement=None,
                deliverable=None
            )

            assert offering.acp_client is mock_acp_client
            assert offering.contract_client is mock_contract_client
            assert offering.provider_address == TEST_PROVIDER_ADDRESS
            assert offering.name == "Test Service"
            assert offering.price == 10.0
            assert offering.price_type == PriceType.FIXED
            assert offering.requirement is None
            assert offering.deliverable is None

        def test_should_initialize_with_optional_parameters(
            self, mock_acp_client, mock_contract_client
        ):
            """Should initialize with optional parameters"""
            requirement = {"type": "string"}
            deliverable = {"format": "json"}

            offering = ACPJobOffering.model_construct(
                acp_client=mock_acp_client,
                contract_client=mock_contract_client,
                provider_address=TEST_PROVIDER_ADDRESS,
                name="Test Service",
                price=10.0,
                price_type=PriceType.PERCENTAGE,
                requirement=requirement,
                deliverable=deliverable,
            )

            assert offering.price_type == PriceType.PERCENTAGE
            assert offering.requirement == requirement
            assert offering.deliverable == deliverable

    class TestParseRequirementSchema:
        """Test parse_requirement_schema validator"""

        def test_should_parse_valid_json_string(
            self, mock_acp_client, mock_contract_client
        ):
            """Should parse valid JSON string in requirement"""
            offering = ACPJobOffering.model_construct(
                acp_client=mock_acp_client,
                contract_client=mock_contract_client,
                provider_address=TEST_PROVIDER_ADDRESS,
                name="Test Service",
                price=10.0,
                price_type=PriceType.FIXED,
                requirement='{"type": "string"}',
                deliverable=None
            )

            # The validator wraps strings in json.dumps(json.loads())
            # which effectively keeps valid JSON strings as strings
            assert offering.requirement == '{"type": "string"}'

        def test_should_keep_dict_requirement_as_is(
            self, mock_acp_client, mock_contract_client
        ):
            """Should keep dict requirement unchanged"""
            requirement = {"type": "object", "properties": {}}
            offering = ACPJobOffering.model_construct(
                acp_client=mock_acp_client,
                contract_client=mock_contract_client,
                provider_address=TEST_PROVIDER_ADDRESS,
                name="Test Service",
                price=10.0,
                price_type=PriceType.FIXED,
                requirement=requirement,
                deliverable=None
            )

            assert offering.requirement == requirement

    class TestMagicMethods:
        """Test __str__ and __repr__ methods"""

        def test_should_return_formatted_string(self, basic_offering):
            """Should return formatted string representation"""
            result = str(basic_offering)

            assert "ACPJobOffering" in result
            assert "Test Service" in result
            assert "10.0" in result
            assert TEST_PROVIDER_ADDRESS in result
            # Should exclude acp_client from string
            assert "acp_client" not in result

        def test_should_have_matching_repr_and_str(self, basic_offering):
            """Should have __repr__ match __str__"""
            assert repr(basic_offering) == str(basic_offering)

    class TestInitiateJob:
        """Test initiate_job method"""

        class TestExpiryHandling:
            """Test expiry date handling"""

            def test_should_use_default_expiry_when_none(
                self, basic_offering, mock_contract_client
            ):
                """Should use default 1 day expiry when not provided"""
                mock_contract_client.get_job_id.return_value = 123
                mock_contract_client.handle_operation.return_value = {}
                basic_offering.acp_client.get_by_client_and_provider.return_value = None

                with patch('virtuals_acp.job_offering.datetime') as mock_datetime:
                    mock_now = datetime(2024, 1, 1, 12, 0,
                                        0, tzinfo=timezone.utc)
                    mock_datetime.now.return_value = mock_now
                    mock_datetime.utcnow.return_value = mock_now

                    basic_offering.initiate_job(
                        service_requirement={"task": "test"}
                    )

                    # Check that create_job was called
                    create_call = mock_contract_client.create_job.call_args
                    expired_at = create_call[0][2]  # Third positional arg

                    # Should be 1 day after now
                    expected = mock_now + timedelta(days=1)
                    assert expired_at == expected

            def test_should_use_custom_expiry_when_provided(
                self, basic_offering, mock_contract_client
            ):
                """Should use custom expiry when provided"""
                mock_contract_client.get_job_id.return_value = 123
                mock_contract_client.handle_operation.return_value = {}
                basic_offering.acp_client.get_by_client_and_provider.return_value = None

                custom_expiry = datetime(
                    2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

                basic_offering.initiate_job(
                    service_requirement={"task": "test"},
                    expired_at=custom_expiry
                )

                create_call = mock_contract_client.create_job.call_args
                expired_at = create_call[0][2]

                assert expired_at == custom_expiry

        class TestServiceRequirementValidation:
            """Test service requirement validation"""

            def test_should_validate_against_schema_when_present(
                self, offering_with_schema, mock_contract_client
            ):
                """Should validate service requirement against schema"""
                mock_contract_client.get_job_id.return_value = 123
                mock_contract_client.handle_operation.return_value = {}
                offering_with_schema.acp_client.get_by_client_and_provider.return_value = None

                # Valid requirement matching schema
                valid_requirement = {"task": "Do something", "count": 5}

                result = offering_with_schema.initiate_job(
                    service_requirement=valid_requirement
                )

                assert result == 123

            def test_should_raise_error_on_invalid_schema(
                self, offering_with_schema
            ):
                """Should raise ValueError when requirement doesn't match schema"""
                # Missing required 'task' field
                invalid_requirement = {"count": 5}

                with pytest.raises(ValueError, match="Invalid service requirement"):
                    offering_with_schema.initiate_job(
                        service_requirement=invalid_requirement
                    )

            def test_should_skip_validation_when_no_schema(
                self, basic_offering, mock_contract_client
            ):
                """Should skip validation when no requirement schema"""
                mock_contract_client.get_job_id.return_value = 123
                mock_contract_client.handle_operation.return_value = {}
                basic_offering.acp_client.get_by_client_and_provider.return_value = None

                # Any requirement should work
                result = basic_offering.initiate_job(
                    service_requirement={"anything": "goes"}
                )

                assert result == 123

        class TestPriceTypeHandling:
            """Test price type and fare amount handling"""

            def test_should_use_price_for_fixed_price_type(
                self, basic_offering, mock_contract_client
            ):
                """Should use price value for FIXED price type"""
                mock_contract_client.get_job_id.return_value = 123
                mock_contract_client.handle_operation.return_value = {}
                basic_offering.acp_client.get_by_client_and_provider.return_value = None

                basic_offering.price_type = PriceType.FIXED
                basic_offering.price = 10.0

                basic_offering.initiate_job(
                    service_requirement={"task": "test"})

                # Check FareAmount was created with price
                create_call = mock_contract_client.create_job.call_args
                # 5th positional arg (budget_base_unit)
                budget_base_unit = create_call[0][4]

                # For FIXED, fare amount should be formatted price (10.0 * 10^6 = 10000000)
                assert budget_base_unit == 10000000

            def test_should_use_zero_for_percentage_price_type(
                self, basic_offering, mock_contract_client
            ):
                """Should use 0 for PERCENTAGE price type"""
                mock_contract_client.get_job_id.return_value = 123
                mock_contract_client.handle_operation.return_value = {}
                basic_offering.acp_client.get_by_client_and_provider.return_value = None

                basic_offering.price_type = PriceType.PERCENTAGE
                basic_offering.price = 10.0  # Should be ignored

                basic_offering.initiate_job(
                    service_requirement={"task": "test"})

                create_call = mock_contract_client.create_job.call_args
                # 5th positional arg (budget_base_unit)
                budget_base_unit = create_call[0][4]

                # For PERCENTAGE, fare amount should be 0
                assert budget_base_unit == 0

        class TestEvaluatorAddressResolution:
            """Test evaluator address resolution"""

            def test_should_use_custom_evaluator_when_provided(
                self, basic_offering, mock_contract_client
            ):
                """Should use custom evaluator address when provided"""
                mock_contract_client.get_job_id.return_value = 123
                mock_contract_client.handle_operation.return_value = {}
                basic_offering.acp_client.get_by_client_and_provider.return_value = None

                basic_offering.initiate_job(
                    service_requirement={"task": "test"},
                    evaluator_address=TEST_EVALUATOR_ADDRESS
                )

                create_call = mock_contract_client.create_job.call_args
                evaluator = create_call[0][1]  # 2nd positional arg

                assert evaluator == TEST_EVALUATOR_ADDRESS

            def test_should_use_agent_wallet_as_default_evaluator(
                self, basic_offering, mock_contract_client
            ):
                """Should use agent wallet address as default evaluator"""
                mock_contract_client.get_job_id.return_value = 123
                mock_contract_client.handle_operation.return_value = {}
                basic_offering.acp_client.get_by_client_and_provider.return_value = None

                basic_offering.initiate_job(
                    service_requirement={"task": "test"})

                create_call = mock_contract_client.create_job.call_args
                evaluator = create_call[0][1]

                assert evaluator == TEST_AGENT_ADDRESS

        class TestAccountLookup:
            """Test account lookup logic"""

            def test_should_lookup_account_by_client_and_provider(
                self, basic_offering, mock_contract_client
            ):
                """Should look up existing account between client and provider"""
                mock_contract_client.get_job_id.return_value = 123
                mock_contract_client.handle_operation.return_value = {}

                mock_account = MagicMock()
                mock_account.id = 456
                basic_offering.acp_client.get_by_client_and_provider.return_value = mock_account

                basic_offering.initiate_job(
                    service_requirement={"task": "test"})

                # Verify account lookup was called
                basic_offering.acp_client.get_by_client_and_provider.assert_called_once_with(
                    TEST_AGENT_ADDRESS,
                    TEST_PROVIDER_ADDRESS,
                    mock_contract_client
                )

        class TestJobCreationStrategy:
            """Test job creation strategy selection"""

            def test_should_use_simple_create_for_base_sepolia(
                self, basic_offering, mock_contract_client
            ):
                """Should use create_job for Base Sepolia contract"""
                mock_contract_client.config.contract_address = BASE_SEPOLIA_CONFIG.contract_address
                mock_contract_client.get_job_id.return_value = 123
                mock_contract_client.handle_operation.return_value = {}
                basic_offering.acp_client.get_by_client_and_provider.return_value = MagicMock(
                    id=456)

                basic_offering.initiate_job(
                    service_requirement={"task": "test"})

                # Should use create_job even though account exists
                mock_contract_client.create_job.assert_called_once()
                mock_contract_client.create_job_with_account.assert_not_called()

            def test_should_use_simple_create_for_base_mainnet(
                self, basic_offering, mock_contract_client
            ):
                """Should use create_job for Base Mainnet contract"""
                mock_contract_client.config.contract_address = BASE_MAINNET_CONFIG.contract_address
                mock_contract_client.get_job_id.return_value = 123
                mock_contract_client.handle_operation.return_value = {}
                basic_offering.acp_client.get_by_client_and_provider.return_value = MagicMock(
                    id=456)

                basic_offering.initiate_job(
                    service_requirement={"task": "test"})

                mock_contract_client.create_job.assert_called_once()
                mock_contract_client.create_job_with_account.assert_not_called()

            def test_should_use_simple_create_for_base_sepolia_x402(
                self, basic_offering, mock_contract_client
            ):
                """Should use create_job for Base Sepolia X402 contract"""
                mock_contract_client.config.contract_address = BASE_SEPOLIA_ACP_X402_CONFIG.contract_address
                mock_contract_client.get_job_id.return_value = 123
                mock_contract_client.handle_operation.return_value = {}
                basic_offering.acp_client.get_by_client_and_provider.return_value = MagicMock(
                    id=456)

                basic_offering.initiate_job(
                    service_requirement={"task": "test"})

                mock_contract_client.create_job.assert_called_once()
                mock_contract_client.create_job_with_account.assert_not_called()

            def test_should_use_simple_create_for_base_mainnet_x402(
                self, basic_offering, mock_contract_client
            ):
                """Should use create_job for Base Mainnet X402 contract"""
                mock_contract_client.config.contract_address = BASE_MAINNET_ACP_X402_CONFIG.contract_address
                mock_contract_client.get_job_id.return_value = 123
                mock_contract_client.handle_operation.return_value = {}
                basic_offering.acp_client.get_by_client_and_provider.return_value = MagicMock(
                    id=456)

                basic_offering.initiate_job(
                    service_requirement={"task": "test"})

                mock_contract_client.create_job.assert_called_once()
                mock_contract_client.create_job_with_account.assert_not_called()

            def test_should_use_simple_create_when_no_account_exists(
                self, basic_offering, mock_contract_client
            ):
                """Should use create_job when no account exists"""
                mock_contract_client.get_job_id.return_value = 123
                mock_contract_client.handle_operation.return_value = {}
                basic_offering.acp_client.get_by_client_and_provider.return_value = None

                basic_offering.initiate_job(
                    service_requirement={"task": "test"})

                mock_contract_client.create_job.assert_called_once()
                mock_contract_client.create_job_with_account.assert_not_called()

            def test_should_use_account_create_when_account_exists_and_not_base(
                self, basic_offering, mock_contract_client
            ):
                """Should use create_job_with_account when account exists and not Base contract"""
                # Use a custom contract address (not in Base contracts list)
                mock_contract_client.config.contract_address = TEST_CONTRACT_ADDRESS
                mock_contract_client.get_job_id.return_value = 123
                mock_contract_client.handle_operation.return_value = {}

                mock_account = MagicMock()
                mock_account.id = 456
                basic_offering.acp_client.get_by_client_and_provider.return_value = mock_account

                basic_offering.initiate_job(
                    service_requirement={"task": "test"})

                mock_contract_client.create_job_with_account.assert_called_once()
                mock_contract_client.create_job.assert_not_called()

            def test_should_use_address_zero_for_evaluator_with_account_path(
                self, basic_offering, mock_contract_client
            ):
                """Should use ADDRESS_ZERO for evaluator when using account path and no evaluator provided"""
                mock_contract_client.config.contract_address = TEST_CONTRACT_ADDRESS
                mock_contract_client.get_job_id.return_value = 123
                mock_contract_client.handle_operation.return_value = {}

                mock_account = MagicMock()
                mock_account.id = 456
                basic_offering.acp_client.get_by_client_and_provider.return_value = mock_account

                basic_offering.initiate_job(
                    service_requirement={"task": "test"})

                # Check the evaluator_address parameter in create_job_with_account
                call_args = mock_contract_client.create_job_with_account.call_args
                evaluator = call_args[0][1]  # 2nd positional arg

                assert evaluator == ADDRESS_ZERO

        class TestX402FlagLogic:
            """Test X402 flag detection logic"""

            def test_should_set_x402_flag_when_usdc_and_x402_config(
                self, basic_offering, mock_contract_client
            ):
                """Should set is_x402_job=True when USDC is used and x402_config exists"""
                mock_contract_client.config.x402_config = MagicMock()
                mock_contract_client.config.base_fare.contract_address = TEST_USDC_ADDRESS
                mock_contract_client.get_job_id.return_value = 123
                mock_contract_client.handle_operation.return_value = {}
                basic_offering.acp_client.get_by_client_and_provider.return_value = None

                basic_offering.initiate_job(
                    service_requirement={"task": "test"})

                call_args = mock_contract_client.create_job.call_args
                is_x402_job = call_args[1]['is_x402_job']

                assert is_x402_job is True

            def test_should_not_set_x402_flag_when_no_x402_config(
                self, basic_offering, mock_contract_client
            ):
                """Should set is_x402_job=False when no x402_config"""
                mock_contract_client.config.x402_config = None
                mock_contract_client.config.base_fare.contract_address = TEST_USDC_ADDRESS
                mock_contract_client.get_job_id.return_value = 123
                mock_contract_client.handle_operation.return_value = {}
                basic_offering.acp_client.get_by_client_and_provider.return_value = None

                basic_offering.initiate_job(
                    service_requirement={"task": "test"})

                call_args = mock_contract_client.create_job.call_args
                is_x402_job = call_args[1]['is_x402_job']

                assert is_x402_job is False

            def test_should_not_set_x402_flag_when_not_usdc(
                self, basic_offering, mock_contract_client
            ):
                """Should set is_x402_job=False when payment token is not USDC"""
                mock_contract_client.config.x402_config = MagicMock()
                mock_contract_client.config.base_fare.contract_address = "0xDifferentToken"
                mock_contract_client.get_job_id.return_value = 123
                mock_contract_client.handle_operation.return_value = {}
                basic_offering.acp_client.get_by_client_and_provider.return_value = None

                basic_offering.initiate_job(
                    service_requirement={"task": "test"})

                call_args = mock_contract_client.create_job.call_args
                is_x402_job = call_args[1]['is_x402_job']

                assert is_x402_job is False

        class TestPostCreationOperations:
            """Test post-creation operations (budget, memo)"""

            def test_should_extract_job_id_from_response(
                self, basic_offering, mock_contract_client
            ):
                """Should extract job ID from transaction response"""
                mock_contract_client.get_job_id.return_value = 999
                mock_contract_client.handle_operation.return_value = {
                    "receipt": "data"}
                basic_offering.acp_client.get_by_client_and_provider.return_value = None

                result = basic_offering.initiate_job(
                    service_requirement={"task": "test"})

                mock_contract_client.get_job_id.assert_called_once_with(
                    {"receipt": "data"},
                    TEST_AGENT_ADDRESS,
                    TEST_PROVIDER_ADDRESS
                )
                assert result == 999

            def test_should_set_budget_with_payment_token(
                self, basic_offering, mock_contract_client
            ):
                """Should set budget with payment token"""
                mock_contract_client.get_job_id.return_value = 123
                mock_contract_client.handle_operation.return_value = {}
                mock_contract_client.set_budget_with_payment_token.return_value = MagicMock()
                basic_offering.acp_client.get_by_client_and_provider.return_value = None

                basic_offering.initiate_job(
                    service_requirement={"task": "test"})

                mock_contract_client.set_budget_with_payment_token.assert_called_once()
                call_args = mock_contract_client.set_budget_with_payment_token.call_args

                job_id = call_args[0][0]
                fare_amount = call_args[0][1]
                token_address = call_args[0][2]

                assert job_id == 123
                assert fare_amount == 10000000  # 10.0 * 10^6
                assert token_address == TEST_USDC_ADDRESS

            def test_should_skip_budget_when_operation_is_none(
                self, basic_offering, mock_contract_client
            ):
                """Should skip budget operation when it returns None"""
                mock_contract_client.get_job_id.return_value = 123
                mock_contract_client.handle_operation.return_value = {}
                mock_contract_client.set_budget_with_payment_token.return_value = None
                basic_offering.acp_client.get_by_client_and_provider.return_value = None

                basic_offering.initiate_job(
                    service_requirement={"task": "test"})

                # Should still succeed
                # Verify handle_operation was called twice (once for create, once for memo only)
                assert mock_contract_client.handle_operation.call_count == 2

            def test_should_create_negotiation_memo_with_service_requirement(
                self, basic_offering, mock_contract_client
            ):
                """Should create negotiation memo with service requirement"""
                mock_contract_client.get_job_id.return_value = 123
                mock_contract_client.handle_operation.return_value = {}
                basic_offering.acp_client.get_by_client_and_provider.return_value = None

                service_req = {"task": "do something", "params": {"count": 5}}
                basic_offering.initiate_job(service_requirement=service_req)

                mock_contract_client.create_memo.assert_called_once()
                call_args = mock_contract_client.create_memo.call_args

                job_id = call_args[0][0]
                content = call_args[0][1]
                memo_type = call_args[0][2]
                is_secured = call_args[0][3]
                phase = call_args[0][4]

                assert job_id == 123

                # Content should be JSON with name, requirement, priceValue, priceType
                parsed_content = json.loads(content)
                assert parsed_content["name"] == "Test Service"
                assert parsed_content["requirement"] == service_req
                assert parsed_content["priceValue"] == 10.0
                assert parsed_content["priceType"] == PriceType.FIXED

                assert memo_type == MemoType.MESSAGE
                assert is_secured is True
                assert phase == ACPJobPhase.NEGOTIATION

            def test_should_return_job_id(
                self, basic_offering, mock_contract_client
            ):
                """Should return the created job ID"""
                mock_contract_client.get_job_id.return_value = 12345
                mock_contract_client.handle_operation.return_value = {}
                basic_offering.acp_client.get_by_client_and_provider.return_value = None

                result = basic_offering.initiate_job(
                    service_requirement={"task": "test"})

                assert result == 12345
                assert isinstance(result, int)


class TestACPResourceOffering:
    """Test suite for ACPResourceOffering class"""

    class TestInitialization:
        """Test ACPResourceOffering initialization"""

        def test_should_initialize_with_all_parameters(self):
            """Should initialize with all parameters"""
            mock_client = MagicMock(spec=VirtualsACP)
            params = {"key": "value", "timeout": 30}

            offering = ACPResourceOffering(
                acp_client=mock_client,
                name="API Resource",
                description="Test API endpoint",
                url="https://api.example.com/resource",
                parameters=params,
                id=42
            )

            assert offering.acp_client is mock_client
            assert offering.name == "API Resource"
            assert offering.description == "Test API endpoint"
            assert offering.url == "https://api.example.com/resource"
            assert offering.parameters == params
            assert offering.id == 42

        def test_should_initialize_with_optional_none_parameters(self):
            """Should initialize with None for optional parameters"""
            mock_client = MagicMock(spec=VirtualsACP)

            offering = ACPResourceOffering(
                acp_client=mock_client,
                name="API Resource",
                description="Test API endpoint",
                url="https://api.example.com/resource",
                parameters=None,
                id=42
            )

            assert offering.parameters is None
