# ACP Python SDK Testing Guide

> **Purpose**: This guide teaches AI agents and developers how to write tests that match the patterns, conventions, and quality standards used in this project.

---

## Table of Contents

1. [Test Structure & Organization](#test-structure--organization)
2. [When to Write Each Type of Test](#when-to-write-each-type-of-test)
3. [Mocking Patterns](#mocking-patterns)
4. [Domain-Specific Testing](#domain-specific-testing)
5. [Common Test Patterns](#common-test-patterns)
6. [Error Testing](#error-testing)
7. [Async & Timing Patterns](#async--timing-patterns)
8. [Test Data Factories](#test-data-factories)
9. [Coverage Expectations](#coverage-expectations)
10. [Common Pitfalls](#common-pitfalls)

---

## Test Structure & Organization

### Directory Structure

```
tests/
├── unit/                      # Fully mocked, no external dependencies
│   └── test_contract_client_v2.py
├── integration/               # Real network calls, real blockchain interaction
│   └── test_integration_contract_client_v2.py
├── conftest.py               # Shared fixtures and configuration
├── .env.example              # Environment variable template
```

### Test File Naming

- **Unit tests**: `test_<module_name>.py`
- **Integration tests**: `test_<module_name>_integration.py` or `test_integration_<module_name>.py`

### Test Suite Structure

```python
# Imports
import pytest
from unittest.mock import MagicMock, patch
from virtuals_acp.contract_clients.contract_client_v2 import ACPContractClientV2

# Test constants
TEST_AGENT_ADDRESS = "0x1234567890123456789012345678901234567890"
TEST_PROVIDER_ADDRESS = "0x5555555555555555555555555555555555555555"


class TestACPContractClientV2:
    """Test suite for ACPContractClientV2 class"""

    # Shared test fixtures
    @pytest.fixture
    def mock_session_key_client(self):
        """Create a mock session key client"""
        client = MagicMock()
        client.send_user_operation.return_value = {"hash": "0xHash"}
        return client

    @pytest.fixture
    def contract_client(self, mock_session_key_client):
        """Create contract client instance"""
        # Use model_construct for mocked dependencies
        return ACPContractClientV2.model_construct(
            session_key_client=mock_session_key_client,
            agent_wallet_address=TEST_AGENT_ADDRESS
        )

    # Group tests by method/feature
    class TestRandomNonceGeneration:
        """Test random nonce generation"""

        def test_should_return_an_integer(self, contract_client):
            """Should return an integer"""
            nonce = contract_client.get_random_nonce()

            assert isinstance(nonce, int)
            assert nonce > 0

        def test_should_generate_unique_nonces(self, contract_client):
            """Should generate unique nonces"""
            nonce1 = contract_client.get_random_nonce()
            nonce2 = contract_client.get_random_nonce()

            assert nonce1 != nonce2

    class TestGasFeeCalculation:
        """Test gas fee calculation"""

        def test_should_calculate_gas_fees(self, contract_client):
            """Should calculate gas fees correctly"""
            # Test implementation
            pass
```

---

## When to Write Each Type of Test

### Unit Tests

**Write unit tests when:**

- Testing pure logic (calculations, transformations, validations)
- Testing individual methods in isolation
- Testing error conditions and edge cases
- You need fast, reliable tests

**Characteristics:**

- All dependencies are mocked
- No network calls
- No real blockchain interaction
- Fast execution (< 100ms per test)

**Example:**

```python
class TestRandomNonceGeneration:
    """Test random nonce generation"""

    def test_should_use_152_as_default_bit_size(self, contract_client):
        """Should use 152 as default bit size"""
        nonce = contract_client.get_random_nonce()

        # 2^152 max value
        max_value = 2 ** 152
        assert nonce < max_value
        assert nonce >= 0
```

### Integration Tests

**Write integration tests when:**

- Testing real network interaction
- Testing blockchain reads/writes
- Verifying end-to-end flows work in practice
- Testing with real credentials and configuration

**Characteristics:**

- Use real network calls
- Require test environment variables
- Longer timeouts (30-60 seconds)
- May have rate limiting concerns

**Example:**

```python
import pytest

class TestIntegrationACPContractClientV2:
    """Integration tests for ACPContractClientV2"""

    @pytest.mark.integration
    def test_should_build_client_successfully(self):
        """Should build client with real credentials"""
        client = ACPContractClientV2.build(
            os.getenv("WHITELISTED_WALLET_PRIVATE_KEY"),
            int(os.getenv("SELLER_ENTITY_ID")),
            os.getenv("SELLER_AGENT_WALLET_ADDRESS"),
            BASE_MAINNET_CONFIG
        )

        assert client is not None
        assert isinstance(client, ACPContractClientV2)
        # Validate address format
        assert len(client.agent_wallet_address) == 42
        assert client.agent_wallet_address.startswith("0x")
```

---

## Mocking Patterns

### 1. Fixture-Based Mocks

Use fixtures for reusable mocks:

```python
@pytest.fixture
def mock_contract_client():
    """Create a mock contract client"""
    client = MagicMock()
    client.config.base_fare = Fare(
        contract_address="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        decimals=6
    )
    client.config.chain_id = 8453
    client.handle_operation.return_value = {"hash": "0xHash"}
    client.create_memo.return_value = {"type": "CREATE_MEMO"}
    return client


def test_with_mock(mock_contract_client):
    """Test using the mock"""
    result = mock_contract_client.create_memo(123, "content")
    assert result["type"] == "CREATE_MEMO"
```

### 2. Method-Specific Mocks

```python
# Simple mock return value
mock_client.get_job_id = MagicMock(return_value=42)

# Mock with multiple return values (sequence)
mock_operation = MagicMock()
mock_operation.side_effect = [
    Exception("Attempt 1 Failed"),
    Exception("Attempt 2 Failed"),
    {"hash": "0xSuccess"}
]

# Mock with conditional logic
def get_payment_details(job_id):
    if job_id == 123:
        return {"is_x402": True}
    return {"is_x402": False}

mock_client.get_x402_payment_details = MagicMock(side_effect=get_payment_details)
```

### 3. Patching External Dependencies

```python
def test_with_patched_requests(mocker):
    """Test with patched requests"""
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": [{"id": 1}]}
    mock_response.status_code = 200

    mocker.patch('requests.get', return_value=mock_response)

    result = fetch_data_from_api()
    assert len(result) == 1
```

### 4. Context Managers and Patch Decorators

```python
from unittest.mock import patch

@patch('virtuals_acp.client.requests.get')
def test_with_decorator(mock_get):
    """Test with patch decorator"""
    mock_get.return_value.json.return_value = {"data": []}

    result = client.fetch_jobs()
    assert result == []


def test_with_context_manager():
    """Test with context manager"""
    with patch('virtuals_acp.client.requests.get') as mock_get:
        mock_get.return_value.json.return_value = {"data": []}

        result = client.fetch_jobs()
        assert result == []
```

---

## Domain-Specific Testing

### Blockchain Addresses

Always use properly formatted addresses:

```python
# Good: Properly formatted addresses
CLIENT_ADDRESS = "0x1234567890123456789012345678901234567890"
PROVIDER_ADDRESS = "0x5555555555555555555555555555555555555555"

# Good: Consistent test addresses
TEST_ADDRESSES = {
    "client": "0x1111111111111111111111111111111111111111",
    "provider": "0x2222222222222222222222222222222222222222",
    "evaluator": "0x3333333333333333333333333333333333333333",
    "token": "0x4444444444444444444444444444444444444444",
}

# Validate address format in tests
def test_address_format(contract_client):
    """Should have valid address format"""
    address = contract_client.agent_wallet_address
    assert len(address) == 42
    assert address.startswith("0x")
    assert all(c in '0123456789abcdefABCDEF' for c in address[2:])
```

### Token Amounts (No BigInt in Python)

Python uses regular `int` for token amounts:

```python
# Good: Regular integers
eth_amount = 1000000000000000000  # 1 ETH (18 decimals)
usdc_amount = 1000000  # 1 USDC (6 decimals)

# Test amount conversion
def test_fare_amount_formatting():
    """Should format amount correctly"""
    fare = Fare(contract_address="0x1234", decimals=6)
    result = fare.format_amount(1.5)

    # 1.5 USDC = 1,500,000 base units
    assert result == 1500000
    assert isinstance(result, int)
```

### Token Decimals

Test with different decimal precisions:

```python
class TestFare:
    """Test Fare class"""

    def test_should_format_amount_with_18_decimals(self):
        """Should format amount with 18 decimals"""
        fare = Fare(contract_address="0x1234", decimals=18)
        result = fare.format_amount(1)

        assert result == 1000000000000000000  # 1 * 10^18

    def test_should_format_amount_with_6_decimals(self):
        """Should format amount with 6 decimals"""
        fare = Fare(contract_address="0x1234", decimals=6)
        result = fare.format_amount(1)

        assert result == 1000000  # 1 * 10^6
```

### Job Phases & State Transitions

Test the full lifecycle:

```python
from virtuals_acp.models import ACPJobPhase, ACPMemoStatus

class TestJobLifecycle:
    """Test job lifecycle transitions"""

    def test_should_transition_from_negotiation_to_transaction(
        self, mock_contract_client
    ):
        """Should transition from NEGOTIATION to TRANSACTION on accept"""
        job = ACPJob.model_construct(
            id=123,
            phase=ACPJobPhase.NEGOTIATION,
            acp_client=mock_acp_client,
            memos=[negotiation_memo]
        )

        await job.accept("Looks good")

        mock_contract_client.sign_memo.assert_called_once_with(
            memo_id=1,
            is_approved=True,
            reason="Looks good"
        )
```

### Payment Flows

Test different payment scenarios:

```python
class TestPaymentFlows:
    """Test different payment scenarios"""

    def test_should_handle_same_token_payment(self, mock_contract_client):
        """Should combine allowances for same token"""
        # Both base fare and transfer use same token
        base_fare_token = "0xBaseFare"
        transfer_token = "0xBaseFare"  # Same!

        # Should combine allowances into single approval
        mock_contract_client.approve_allowance.assert_called_once()

    def test_should_handle_different_token_payment(self, mock_contract_client):
        """Should approve separately for different tokens"""
        base_fare_token = "0xBaseFare"
        transfer_token = "0xUSDC"  # Different!

        # Should approve separately
        assert mock_contract_client.approve_allowance.call_count == 2
```

---

## Common Test Patterns

### 1. Arrange-Act-Assert Pattern

```python
def test_should_calculate_gas_fees(self, contract_client):
    """Should calculate gas fees correctly"""
    # Arrange: Set up test data
    expected_fee = 41000000

    # Act: Execute the method
    calculated_fee = contract_client.calculate_gas_fees()

    # Assert: Verify results
    assert calculated_fee == expected_fee
    assert isinstance(calculated_fee, int)
```

### 2. Testing Return Values AND Side Effects

```python
def test_should_create_requirement_and_return_hash(
    self, job, mock_contract_client
):
    """Should create requirement and return transaction hash"""
    content = "These are the requirements"
    mock_operation = {"type": "CREATE_MEMO"}
    mock_contract_client.create_memo.return_value = mock_operation

    # Test return value
    result = job.create_requirement(content)
    assert result == {"hash": "0xHash"}

    # Test side effects (method calls)
    mock_contract_client.create_memo.assert_called_once_with(
        123,
        content,
        MemoType.MESSAGE,
        True,
        ACPJobPhase.TRANSACTION
    )
```

### 3. Testing Object Shape & Properties

```python
def test_should_return_agents_with_correct_structure(self, acp_client):
    """Should return agents with correct structure"""
    result = acp_client.browse_agents("keyword", top_k=3)

    if result:
        first_agent = result[0]

        # Test property existence
        assert hasattr(first_agent, 'id')
        assert hasattr(first_agent, 'name')
        assert hasattr(first_agent, 'wallet_address')
        assert hasattr(first_agent, 'job_offerings')

        # Test property types
        assert isinstance(first_agent.id, int)
        assert isinstance(first_agent.name, str)
        assert isinstance(first_agent.job_offerings, list)
```

### 4. Testing Filtering & Data Transformation

```python
def test_should_filter_out_own_wallet_address(self, acp_client, mocker):
    """Should filter out own wallet address from results"""
    mock_agents = [
        {"id": 1, "wallet_address": "0xOther"},
        {"id": 2, "wallet_address": acp_client.agent_wallet_address},
    ]

    mock_response = MagicMock()
    mock_response.json.return_value = {"data": mock_agents}
    mocker.patch('requests.get', return_value=mock_response)

    result = acp_client.browse_agents("keyword", top_k=10)

    # Should exclude own wallet
    assert len(result) == 1
    assert result[0].wallet_address == "0xOther"
```

### 5. Testing Instance Types

```python
def test_should_return_job_offerings_as_instances(self, acp_client):
    """Should return job offerings as ACPJobOffering instances"""
    result = acp_client.browse_agents("keyword", top_k=5)

    agent_with_jobs = next(
        (a for a in result if a.job_offerings),
        None
    )

    if agent_with_jobs:
        job_offering = agent_with_jobs.job_offerings[0]

        assert isinstance(job_offering, ACPJobOffering)
        assert callable(job_offering.initiate_job)
```

### 6. Testing JSON Parsing

```python
class TestMemoConstruct or:
    """Test memo initialization"""

    def test_should_parse_valid_json_content(self, mock_contract_client):
        """Should parse valid JSON to structured_content"""
        payload = {
            "type": "FUND_RESPONSE",
            "data": {"wallet_address": "0xWallet"}
        }

        memo = ACPMemo(
            contract_client=mock_contract_client,
            id=1,
            type=MemoType.MESSAGE,
            content=json.dumps(payload),  # Valid JSON
            next_phase=ACPJobPhase.NEGOTIATION,
            status=ACPMemoStatus.PENDING,
            sender_address="0xSender"
        )

        assert memo.structured_content == payload
        assert memo.structured_content["type"] == "FUND_RESPONSE"

    def test_should_handle_non_json_content(self, mock_contract_client):
        """Should set structured_content to None for non-JSON"""
        memo = ACPMemo(
            contract_client=mock_contract_client,
            id=1,
            type=MemoType.MESSAGE,
            content="Plain text content",  # Not JSON
            next_phase=ACPJobPhase.NEGOTIATION,
            status=ACPMemoStatus.PENDING,
            sender_address="0xSender"
        )

        assert memo.structured_content is None
```

---

## Error Testing

### Always Test Both Error Type AND Message

```python
# ✅ GOOD: Test both type and message
def test_should_raise_acp_error_on_contract_failure(self, contract_client):
    """Should raise ACPError when contract read fails"""
    mock_error = Exception("Contract read failed")
    contract_client.read_contract = MagicMock(side_effect=mock_error)

    with pytest.raises(ACPError) as exc_info:
        contract_client.get_x402_payment_details(123)

    assert "Failed to get X402 payment details" in str(exc_info.value)

# ❌ BAD: Only testing type
def test_should_throw_error(self):
    """Should throw error"""
    with pytest.raises(ACPError):
        some_method()
```

### Test Error Conditions First

```python
class TestGetJobById:
    """Test get job by ID"""

    # Test error cases first
    def test_should_raise_error_when_api_returns_error(self, acp_client, mocker):
        """Should raise ACPError when API returns error"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "error": {"message": "Job Not Found"}
        }
        mocker.patch('requests.get', return_value=mock_response)

        with pytest.raises(ACPError) as exc_info:
            acp_client.get_job_by_id(123)

        assert "Job Not Found" in str(exc_info.value)

    def test_should_raise_error_on_network_failure(self, acp_client, mocker):
        """Should raise ACPError when network fails"""
        mocker.patch('requests.get', side_effect=Exception("Network Fail"))

        with pytest.raises(ACPError) as exc_info:
            acp_client.get_job_by_id(123)

        assert "network error" in str(exc_info.value)

    # Then test success case
    def test_should_get_job_successfully(self, acp_client, mocker):
        """Should get job by ID successfully"""
        # Success test...
        pass
```

### Test Validation Errors

```python
class TestConstructorValidations:
    """Test constructor validations"""

    def test_should_raise_error_when_no_clients_provided(self):
        """Should raise error when no contract clients provided"""
        with pytest.raises(ValueError) as exc_info:
            VirtualsACP(acp_contract_client=[])

        assert "contract client is required" in str(exc_info.value)

    def test_should_raise_error_on_address_mismatch(self):
        """Should raise error when clients have different addresses"""
        client1 = MagicMock()
        client1.agent_wallet_address = "0x1111"
        client2 = MagicMock()
        client2.agent_wallet_address = "0x2222"

        with pytest.raises(ValueError) as exc_info:
            VirtualsACP(acp_contract_client=[client1, client2])

        assert "same agent wallet address" in str(exc_info.value)
```

---

## Async & Timing Patterns

### 1. Testing Async Methods

```python
import pytest

@pytest.mark.asyncio
async def test_async_method(self, client):
    """Test async method"""
    result = await client.fetch_data()
    assert result is not None


class TestAsyncOperations:
    """Test async operations"""

    @pytest.mark.asyncio
    async def test_should_fetch_jobs_async(self, acp_client):
        """Should fetch jobs asynchronously"""
        jobs = await acp_client.get_active_jobs()
        assert isinstance(jobs, list)
```

### 2. Mocking Time-Based Operations

```python
from unittest.mock import patch
from datetime import datetime, timezone

def test_should_use_default_expiry(self, job_offering, mocker):
    """Should use default expiry when not provided"""
    fixed_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    with patch('virtuals_acp.job_offering.datetime') as mock_datetime:
        mock_datetime.now.return_value = fixed_time

        job_offering.initiate_job(service_requirement={"task": "test"})

        # Verify expiry is 1 day from fixed_time
        expected_expiry = fixed_time + timedelta(days=1)
        # Assert on the call arguments...
```

### 3. Testing Retries with side_effect

```python
def test_should_retry_on_failure(self, contract_client):
    """Should retry operation on failure"""
    mock_operation = MagicMock()
    # Fail twice, succeed on third attempt
    mock_operation.side_effect = [
        Exception("Attempt 1 Failed"),
        Exception("Attempt 2 Failed"),
        {"hash": "0xSuccess"}
    ]

    contract_client.send_operation = mock_operation

    result = contract_client.handle_operation([{"type": "TEST"}])

    assert result == {"hash": "0xSuccess"}
    assert mock_operation.call_count == 3
```

---

## Test Data Factories

### Reusable Mock Objects

```python
# Create factory functions for common test data
def create_mock_memo(overrides=None):
    """Create a mock memo with default values"""
    defaults = {
        "id": 1,
        "type": MemoType.MESSAGE,
        "content": "Test content",
        "next_phase": ACPJobPhase.NEGOTIATION,
        "status": ACPMemoStatus.PENDING,
        "sender_address": "0xSender",
    }
    if overrides:
        defaults.update(overrides)
    return ACPMemo.model_construct(**defaults)


def create_mock_job(overrides=None):
    """Create a mock job with default values"""
    defaults = {
        "id": 123,
        "client_address": "0xClient",
        "provider_address": "0xProvider",
        "evaluator_address": "0xEvaluator",
        "price": 100,
        "price_token_address": "0xToken",
        "memos": [create_mock_memo()],
        "phase": ACPJobPhase.REQUEST,
        "context": {},
        "contract_address": "0xContract",
    }
    if overrides:
        defaults.update(overrides)
    return defaults


# Usage in tests
def test_with_factory():
    """Test using factory"""
    job_data = create_mock_job({"id": 999, "price": 200})
    job = ACPJob.model_construct(**job_data)

    assert job.id == 999
    assert job.price == 200
```

### Common Test Addresses

```python
# Define at module level
TEST_ADDRESSES = {
    "client": "0x1111111111111111111111111111111111111111",
    "provider": "0x2222222222222222222222222222222222222222",
    "evaluator": "0x3333333333333333333333333333333333333333",
    "contract": "0x4444444444444444444444444444444444444444",
    "token": "0x5555555555555555555555555555555555555555",
    "base_fare": "0x6666666666666666666666666666666666666666",
}
```

---

## Coverage Expectations

### Target Metrics

- **Statement Coverage**: > 90%
- **Branch Coverage**: > 80%
- **Function Coverage**: 100%
- **Line Coverage**: > 90%

### What to Test

✅ **Must Test:**

- All public methods
- Error conditions and edge cases
- State transitions and phase changes
- Payment flows (payable vs non-payable)
- Data transformations (JSON, int conversions)
- Validation logic

✅ **Should Test:**

- Private methods with complex logic (via public interface or direct access)
- Property getters with logic
- Filtering and data manipulation
- Instance type checks

⚠️ **Can Skip:**

- Simple getters that just return a property
- Trivial one-line methods
- Auto-generated code (Pydantic validators)

### Coverage Reports

```bash
# Generate coverage report
poetry run pytest --cov=virtuals_acp --cov-report=html

# View HTML report
open htmlcov/index.html

# Terminal report with missing lines
poetry run pytest --cov=virtuals_acp --cov-report=term-missing
```

---

## Common Pitfalls

### ❌ Don't Forget to Use Fresh Fixtures

```python
# BAD: Reusing mocks without reset
def test_first(mock_client):
    mock_client.method()
    assert mock_client.method.call_count == 1

def test_second(mock_client):
    # Mock might still have call from test_first!
    assert mock_client.method.call_count == 0  # May fail

# GOOD: Use fresh fixtures
@pytest.fixture
def mock_client():
    """Create fresh mock for each test"""
    return MagicMock()
```

### ❌ Don't Use Actual Addresses in Tests

```python
# BAD: Real addresses in tests
real_address = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"

# GOOD: Consistent test addresses
test_address = "0x1111111111111111111111111111111111111111"
```

### ❌ Don't Forget Async Markers

```python
# BAD: Missing async marker
def test_async_method(client):
    result = await client.fetch()  # Will fail

# GOOD: Use pytest.mark.asyncio
@pytest.mark.asyncio
async def test_async_method(client):
    result = await client.fetch()
    assert result is not None
```

### ❌ Don't Test Multiple Things in One Test

```python
# BAD: Testing too much
def test_everything(job):
    assert job.id == 123
    assert job.price == 100
    assert job.phase == ACPJobPhase.REQUEST
    assert job.memos == []
    # 10 more assertions...

# GOOD: One concept per test
def test_should_have_correct_id(job):
    assert job.id == 123

def test_should_have_correct_price(job):
    assert job.price == 100
```

### ❌ Don't Ignore Integration Test Timeouts

```python
# BAD: Default timeout for network calls
@pytest.mark.integration
def test_network_call():
    # May timeout...
    pass

# GOOD: Use timeout marker or config
@pytest.mark.timeout(60)  # 60 seconds
@pytest.mark.integration
def test_network_call():
    # Won't timeout
    pass
```

---

## Quick Reference Checklist

When writing a test, ask yourself:

- [ ] Did I use fixtures for shared mocks and data?
- [ ] Did I use properly formatted addresses?
- [ ] Did I test both success AND error cases?
- [ ] Did I test error type AND message?
- [ ] Did I use appropriate markers (`@pytest.mark.integration`)?
- [ ] Did I set timeout for integration tests?
- [ ] Did I test return values AND side effects?
- [ ] Did I follow Arrange-Act-Assert pattern?
- [ ] Is my test name descriptive (starts with `test_should_`)?
- [ ] Is my test focused on one concept?
- [ ] Did I avoid testing implementation details?
- [ ] Did I use `model_construct` for Pydantic models with mocks?

---

## Additional Resources

- **Pytest Documentation**: https://docs.pytest.org/
- **pytest-mock**: https://pytest-mock.readthedocs.io/
- **Python Testing Best Practices**: https://docs.python-guide.org/writing/tests/
- **Pydantic Testing**: https://docs.pydantic.dev/latest/concepts/models/#model-construct
- **Project README**: `tests/README.md`

---

**Last Updated**: 2026-02-04

**Questions?** File an issue or reach out to the maintainers.
