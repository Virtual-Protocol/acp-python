import pytest
import os
from virtuals_acp.client import VirtualsACP
from virtuals_acp.contract_clients.contract_client_v2 import ACPContractClientV2
from virtuals_acp.configs.configs import BASE_MAINNET_CONFIG_V2
from virtuals_acp.models import ACPAgentSort


@pytest.mark.integration
class TestClientIntegration:
    @pytest.fixture(scope="class")
    def acp_client(self):
        """Create a real VirtualsACP client for integration testing"""
        wallet_private_key = os.getenv("WHITELISTED_WALLET_PRIVATE_KEY")
        agent_wallet_address = os.getenv("SELLER_AGENT_WALLET_ADDRESS")
        entity_id_str = os.getenv("SELLER_ENTITY_ID")

        if not all([wallet_private_key, agent_wallet_address, entity_id_str]):
            pytest.skip("Integration test environment variables not set")

        entity_id = int(entity_id_str)

        contract_client = ACPContractClientV2(
            agent_wallet_address=agent_wallet_address,
            wallet_private_key=wallet_private_key,
            entity_id=entity_id,
            config=BASE_MAINNET_CONFIG_V2,
        )

        client = VirtualsACP(acp_contract_clients=contract_client)
        yield client

        if hasattr(client, 'sio') and client.sio:
            client.sio.disconnect()

    class TestBrowseAgents:
        """Integration tests for browse_agents method"""

        def test_should_browse_agents_with_keyword(self, acp_client):
            """Should successfully browse agents with keyword search"""
            agents = acp_client.browse_agents(keyword="Trading Agent", top_k=5)

            # Verify we got results
            assert isinstance(agents, list)
            assert len(agents) >= 0

            # If we got agents, verify their structure
            if len(agents) > 0:
                agent = agents[0]
                assert hasattr(agent, 'id')
                assert hasattr(agent, 'wallet_address')
                assert hasattr(agent, 'job_offerings')

        def test_should_filter_out_self(self, acp_client):
            """Should exclude self from agent search results"""
            agents = acp_client.browse_agents(
                keyword="Trading Agent", top_k=10)

            # Verify none of the agents are the client itself
            for agent in agents:
                assert agent.wallet_address.lower() != acp_client.agent_address.lower()

        def test_should_respect_top_k_parameter(self, acp_client):
            """Should respect the top_k parameter for result limiting"""
            top_k = 3
            agents = acp_client.browse_agents(keyword="", top_k=top_k)

            # Result count should be <= top_k
            assert len(agents) <= top_k

        def test_should_handle_sort_by_parameter(self, acp_client):
            """Should handle sort_by parameter without errors"""
            # This should not raise an error
            agents = acp_client.browse_agents(
                keyword="",
                sort_by=[ACPAgentSort.SUCCESSFUL_JOB_COUNT],
                top_k=5
            )

            assert isinstance(agents, list)

        def test_should_search_with_keyword(self, acp_client):
            """Should search agents with specific keyword"""
            # Search for something generic
            agents = acp_client.browse_agents(keyword="ai", top_k=5)

            assert isinstance(agents, list)
            # Even if no results, should return empty list, not error

    class TestGetAgent:
        """Integration tests for get_agent method"""

        def test_should_get_own_agent_info(self, acp_client):
            """Should successfully retrieve own agent information"""
            agent = acp_client.get_agent(acp_client.agent_address)

            # Should return the agent or None
            # If the agent exists
            if agent:
                assert agent.wallet_address.lower() == acp_client.agent_address.lower()
                assert hasattr(agent, 'id')
                assert hasattr(agent, 'job_offerings')
                assert hasattr(agent, 'name')

        def test_should_return_none_for_nonexistent_agent(self, acp_client):
            """Should return None for non-existent agent"""
            # Use a random address that likely doesn't exist
            fake_address = "0x0000000000000000000000000000000000000001"
            agent = acp_client.get_agent(fake_address)

            assert agent is None

        def test_should_handle_valid_agent_address(self, acp_client):
            """Should handle valid agent address without errors"""
            # First browse to find a real agent
            agents = acp_client.browse_agents(keyword="", top_k=1)

            if len(agents) > 0:
                # Get the first agent's details
                agent_address = agents[0].wallet_address
                agent = acp_client.get_agent(agent_address)

                # Should return agent info or None
                if agent:
                    assert agent.wallet_address.lower() == agent_address.lower()

    class TestJobFetching:
        """Integration tests for job fetching methods"""

        def test_should_fetch_active_jobs(self, acp_client):
            """Should successfully fetch active jobs"""
            jobs = acp_client.get_active_jobs(page=1, page_size=5)

            assert isinstance(jobs, list)
            # Should return a list (could be empty)

        def test_should_fetch_pending_memo_jobs(self, acp_client):
            """Should successfully fetch pending memo jobs"""
            jobs = acp_client.get_pending_memo_jobs(page=1, page_size=5)

            assert isinstance(jobs, list)

        def test_should_fetch_completed_jobs(self, acp_client):
            """Should successfully fetch completed jobs"""
            jobs = acp_client.get_completed_jobs(page=1, page_size=5)

            assert isinstance(jobs, list)

        def test_should_fetch_cancelled_jobs(self, acp_client):
            """Should successfully fetch cancelled jobs"""
            jobs = acp_client.get_cancelled_jobs(page=1, page_size=5)

            assert isinstance(jobs, list)

    class TestAccountMethods:
        """Integration tests for account-related methods"""

        def test_get_by_client_and_provider_should_handle_no_account(self, acp_client):
            """Should handle case when no account exists between client and provider"""
            # Use a random provider address that likely doesn't have an account
            fake_provider = "0x0000000000000000000000000000000000000001"

            account = acp_client.get_by_client_and_provider(
                acp_client.agent_address,
                fake_provider
            )

            # Should return None for non-existent account
            assert account is None
