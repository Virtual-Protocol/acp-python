# ACP Python SDK Automated Testing

<details>
<summary>📑 Table of Contents</summary>

```
tests/
├── unit/                      # Unit tests (mocked dependencies)
│   ├── test_account.py
│   ├── test_client.py
│   ├── test_contract_client_v2.py
│   ├── test_fare.py
│   ├── test_job.py
│   ├── test_job_offering.py
│   ├── test_memo.py
│   └── test_x402.py
│
├── integration/               # Integration tests (real network calls)
│   ├── test_client_integration.py
│   └── test_integration_contract_client_v2.py
│
├── conftest.py               # Pytest fixtures and configuration
├── .env.example              # Environment variable template
└── .env                      # Environment variables (gitignored)
```

- [Introduction](#introduction)
  - [Purpose](#purpose)
- [Running Tests](#running-tests)
  - [All Tests](#all-tests)
  - [Unit Tests Only](#unit-tests-only)
  - [Integration Tests Only](#integration-tests-only)
  - [Specific Test Files](#specific-test-files)
  - [Generating Coverage Report](#generate-coverage-report)
- [How to Write Tests](#how-to-write-tests)
  - [Unit Tests](#unit-tests)
  - [Integration Tests](#integration-tests)

</details>

## Introduction

### Purpose

This test suite validates the ACP Python SDK's functionality across two levels:

- **Unit Tests** - Verify individual functions and classes in isolation
- **Integration Tests** - Validate end-to-end functionality with real blockchain/API calls

The test suite ensures code quality, prevents regressions, and provides confidence when shipping new features.

## Running Tests

Below are commands to run the test suites.

### All Tests

```bash
poetry run pytest
```

### Unit Tests Only

```bash
poetry run pytest tests/unit
```

### Integration Tests Only

```bash
poetry run pytest tests/integration
```

### Specific Test Files

```bash
poetry run pytest tests/unit/test_job.py
```

### Run Tests with Verbose Output

```bash
poetry run pytest -v
```

### Generate Coverage Report

```bash
# Terminal report with missing lines
poetry run pytest --cov=virtuals_acp --cov-report=term-missing

# HTML report (opens in browser)
poetry run pytest --cov=virtuals_acp --cov-report=html
open htmlcov/index.html
```

### Run Tests by Marker

```bash
# Run only unit tests
poetry run pytest -m unit

# Run only integration tests
poetry run pytest -m integration

# Run tests that don't require network
poetry run pytest -m "not requires_network"
```

## How to Write Tests

### Unit Tests

Unit tests should be **isolated, fast, and deterministic**. These tests don't involve any on-chain activity or external dependencies.

**Location**: `tests/unit/`

**General Guidelines:**

- No network calls
- No blockchain interactions
- External dependencies are mocked using `unittest.mock` or `pytest-mock`
- No `.env` needed

**Example Structure:**

```python
# test_job.py
import pytest
from unittest.mock import MagicMock
from virtuals_acp.job import ACPJob
from virtuals_acp.exceptions import ACPError
from virtuals_acp.models import ACPJobPhase, PriceType

class TestACPJob:
    """Test suite for ACPJob class"""

    @pytest.fixture
    def mock_acp_client(self):
        """Create a mock VirtualsACP client"""
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
            "client_address": "0x1111111111111111111111111111111111111111",
            "provider_address": "0x2222222222222222222222222222222222222222",
            "price": 100.0,
            "memos": [],
            "phase": ACPJobPhase.REQUEST,
        }

    class TestInitialization:
        """Test job initialization"""

        def test_should_initialize_with_all_parameters(self, sample_job_data):
            """Should create a job with valid parameters"""
            job = ACPJob.model_construct(**sample_job_data)

            assert job is not None
            assert job.id == 123
            assert job.phase == ACPJobPhase.REQUEST

        def test_should_raise_error_for_invalid_parameters(self):
            """Should throw error for invalid parameters"""
            with pytest.raises(ACPError):
                ACPJob(invalid_param="value")

# Mocking Examples
def test_with_mocked_api_call(mocker):
    """Example of mocking API calls"""
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": [{"id": 1}]}
    mocker.patch('requests.get', return_value=mock_response)

    result = fetch_jobs()
    assert len(result) == 1

def test_with_mocked_contract_client():
    """Example of mocking contract client"""
    mock_client = MagicMock()
    mock_client.create_job.return_value = {"type": "CREATE_JOB"}

    result = mock_client.create_job("0xProvider", "0xEvaluator")
    assert result["type"] == "CREATE_JOB"
```

**What to Test:**

- Input Validation
- Error Handling
- Edge Cases
- Business Logic
- State Transitions
- Helper Functions

### Integration Tests

Integration tests verify the SDK works correctly with external dependencies/services (blockchain, APIs).

**Location**: `tests/integration/`

**General Guidelines:**

- Require `.env` to be defined
- Make real network & blockchain calls
- Test partial end-to-end functionality
- Use longer timeouts

**Environment Setup**

1. Copy `.env.example` to `.env`:

```bash
cp tests/.env.example tests/.env
```

2. Populate environment variables:

```bash
# tests/.env
# General Variables
WHITELISTED_WALLET_PRIVATE_KEY=0x<PRIVATE_KEY>

# Seller Agent Variables
SELLER_ENTITY_ID=<ENTITY_ID>
SELLER_AGENT_WALLET_ADDRESS=<WALLET_ADDRESS>

# Buyer Agent Variables
BUYER_ENTITY_ID=<ENTITY_ID>
BUYER_AGENT_WALLET_ADDRESS=<WALLET_ADDRESS>
```

**Example Structure:**

```python
# test_integration_contract_client_v2.py
import pytest
import os
from virtuals_acp.contract_clients.contract_client_v2 import ACPContractClientV2
from virtuals_acp.configs.configs import BASE_MAINNET_CONFIG

class TestIntegrationACPContractClientV2:
    """Integration tests for ACPContractClientV2"""

    @pytest.fixture
    def wallet_private_key(self):
        """Get private key from environment"""
        return os.getenv("WHITELISTED_WALLET_PRIVATE_KEY")

    class TestInitialization:
        """Test client initialization with real network"""

        @pytest.mark.integration
        def test_should_initialize_client_successfully(self, wallet_private_key):
            """Should initialize client with real credentials"""
            client = ACPContractClientV2.build(
                wallet_private_key,
                os.getenv("SELLER_ENTITY_ID"),
                os.getenv("SELLER_AGENT_WALLET_ADDRESS"),
                BASE_MAINNET_CONFIG
            )

            assert client is not None
            assert client.agent_wallet_address is not None
            assert client.config.chain_id == 8453
```

**Important Notes:**

- Integration tests load environment variables from `tests/.env`
- If `.env` is missing, integration tests are skipped with a warning
- Ensure test wallets are funded on the corresponding network (testnet/mainnet)
- Use appropriate timeouts for network operations (`timeout = 300` in pytest.ini)

## Test Configuration

### pytest.ini

Key configuration options:

```ini
[pytest]
testpaths = tests              # Where to find tests
python_files = test_*.py       # Test file pattern
python_classes = Test*         # Test class pattern
python_functions = test_*      # Test function pattern

# Markers for organizing tests
markers =
    unit: Unit tests
    integration: Integration tests
    slow: Tests that take a long time
    requires_network: Tests requiring network
    requires_blockchain: Tests requiring blockchain

# Timeout for tests (prevents hanging)
timeout = 300  # 5 minutes

# Coverage options (uncomment to enable)
# addopts = --cov=virtuals_acp --cov-report=html
```

### conftest.py

The `conftest.py` file handles:

- Loading `.env` variables automatically
- Providing warnings if `.env` is missing
- Shared fixtures across test files

## Best Practices

### Test Organization

- **Group related tests** using nested classes
- **Use descriptive test names** starting with `test_should_`
- **One assertion concept per test** (avoid testing too much in one test)
- **Use fixtures** for reusable test data and mocks

### Mocking

- Always use `pytest.fixture` for shared mocks
- Clear mocks between tests using `mocker.reset_mock()` or fresh fixtures
- Mock at the appropriate level (not too deep, not too shallow)

### Coverage

- Aim for >90% statement coverage
- Aim for >80% branch coverage
- 100% function coverage for public methods
- Use `--cov-report=html` to identify uncovered lines

### Running Tests in CI/CD

Tests run automatically on:

- Pull requests (unit tests only)
- Pushes to main (all tests including integration)

See `.github/workflows/ci-test.yml` for CI configuration.

## Troubleshooting

### Integration Tests Skipped

If you see "Integration tests will be skipped", create `tests/.env` from `tests/.env.example`.

### Import Errors

Make sure to install dev dependencies:

```bash
poetry install
```

### Coverage Not Working

Ensure pytest-cov is installed:

```bash
poetry add --group dev pytest-cov
```
