import logging
import threading
import os
import sys

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
sys.path.insert(0, project_root)

from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv

from virtuals_acp.client import VirtualsACP
from virtuals_acp.configs.configs import BASE_MAINNET_ACP_X402_CONFIG_V2, BASE_SEPOLIA_ACP_X402_CONFIG_V2
from virtuals_acp.contract_clients.contract_client_v2 import ACPContractClientV2
from virtuals_acp.env import EnvSettings
from virtuals_acp.job import ACPJob
from virtuals_acp.memo import ACPMemo
from virtuals_acp.models import (
    ACPAgentSort,
    ACPJobPhase,
    ACPGraduationStatus,
    ACPOnlineStatus,
    ChainConfig
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("BuyerAgent")

load_dotenv(override=True)

TARGET_CHAIN_ID = 97

config = BASE_SEPOLIA_ACP_X402_CONFIG_V2
config.chains = [
    ChainConfig(
        chain_id=TARGET_CHAIN_ID,
        rpc_url="https://bsc-testnet-dataseed.bnbchain.org"
    )
]


def buyer():
    env = EnvSettings()

    def on_new_task(job: ACPJob, memo_to_sign: Optional[ACPMemo] = None):
        if (
            job.phase == ACPJobPhase.NEGOTIATION
            and memo_to_sign is not None
            and memo_to_sign.next_phase == ACPJobPhase.TRANSACTION
        ):
            logger.info(f"Paying for job {job.id}")
            job.pay_and_accept_requirement()
            logger.info(f"Job {job.id} paid")

        elif (
            job.phase == ACPJobPhase.TRANSACTION
            and memo_to_sign is not None
            and memo_to_sign.next_phase == ACPJobPhase.REJECTED
        ):
            logger.info(f"Signing job {job.id} rejection memo, rejection reason: {memo_to_sign.content}")
            memo_to_sign.sign(True, "Accepts job rejection")
            logger.info(f"Job {job.id} rejection memo signed")

        elif job.phase == ACPJobPhase.COMPLETED:
            logger.info(f"Job {job.id} completed, received deliverable: {job.deliverable}")

        elif job.phase == ACPJobPhase.REJECTED:
            logger.info(f"Job {job.id} rejected by seller")

    acp_client = VirtualsACP(
        acp_contract_clients=ACPContractClientV2(
            wallet_private_key=env.WHITELISTED_WALLET_PRIVATE_KEY,
            agent_wallet_address=env.BUYER_AGENT_WALLET_ADDRESS,
            entity_id=env.BUYER_ENTITY_ID,
            config=config,  # route to x402 for payment, undefined defaulted back to direct transfer
        ),
        on_new_task=on_new_task
    )

    # Browse available agents based on a keyword
    relevant_agents = acp_client.browse_agents(
        keyword="cross chain transfer service",
        sort_by=[ACPAgentSort.SUCCESSFUL_JOB_COUNT],
        top_k=5,
        graduation_status=ACPGraduationStatus.ALL,
        online_status=ACPOnlineStatus.ALL,
        show_hidden_offerings=True,
    )
    logger.info(f"Relevant agents: {relevant_agents}")

    # Pick one of the agents based on your criteria (in this example we just pick the first one)
    chosen_agent = relevant_agents[0]
    # Pick one of the service offerings based on your criteria (in this example we just pick the first one)
    chosen_job_offering = chosen_agent.job_offerings[1]

    job_id = chosen_job_offering.initiate_job(
        service_requirement={},
        expired_at=datetime.now() + timedelta(minutes=5),  # job expiry duration, minimum 3 minutes
    )
    logger.info(f"Job {job_id} initiated")
    logger.info("Listening for next steps...")

    threading.Event().wait()


if __name__ == "__main__":
    buyer()
