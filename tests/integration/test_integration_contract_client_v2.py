import pytest
import os
from virtuals_acp.contract_clients.contract_client_v2 import ACPContractClientV2


# Skip all integration tests if environment variables are not set
pytestmark = pytest.mark.integration

# Check if we have required environment variables for integration tests
SKIP_INTEGRATION = not all([
    os.getenv("WHITELISTED_WALLET_PRIVATE_KEY"),
    os.getenv("SELLER_AGENT_WALLET_ADDRESS"),
    os.getenv("SELLER_ENTITY_ID"),
])


@pytest.mark.skipif(SKIP_INTEGRATION, reason="Integration test environment variables not set")
class TestIntegrationACPContractClientV2:
    @pytest.fixture(scope="class")
    def integration_client(self):
        wallet_private_key = os.getenv("WHITELISTED_WALLET_PRIVATE_KEY")
        agent_wallet_address = os.getenv("SELLER_AGENT_WALLET_ADDRESS")
        entity_id = int(os.getenv("SELLER_ENTITY_ID", "0"))

        try:
            client = ACPContractClientV2(
                agent_wallet_address=agent_wallet_address,
                wallet_private_key=wallet_private_key,
                entity_id=entity_id,
            )
            yield client
        except Exception as e:
            pytest.fail(f"Failed to initialize integration client: {e}")

    class TestInitialization:
        def test_should_connect_to_mainnet(self, integration_client):
            assert integration_client is not None
            assert integration_client.agent_wallet_address is not None

        def test_should_have_valid_web3_connection(self, integration_client):
            assert integration_client.w3 is not None
            assert integration_client.w3.is_connected()

        def test_should_fetch_manager_addresses(self, integration_client):
            assert integration_client.job_manager_address is not None
            assert integration_client.job_manager_address.startswith("0x")

        def test_should_validate_session_key(self, integration_client):
            # If client initialized, session key validation already passed
            assert integration_client.account is not None
            assert integration_client.entity_id is not None

        def test_should_have_x402_instance(self, integration_client):
            assert integration_client.x402 is not None

        def test_should_have_alchemy_kit_instance(self, integration_client):
            assert integration_client.alchemy_kit is not None
