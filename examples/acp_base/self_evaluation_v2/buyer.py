import logging
import threading
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from virtuals_acp.memo import ACPMemo
from virtuals_acp.client import VirtualsACP
from virtuals_acp.env import EnvSettings
from virtuals_acp.job import ACPJob
from virtuals_acp.models import (
    ACPAgentSort,
    ACPJobPhase,
    ACPGraduationStatus,
    ACPOnlineStatus,
)
from virtuals_acp.configs.configs import BASE_SEPOLIA_CONFIG_V2
from virtuals_acp.contract_clients.contract_client_v2 import ACPContractClientV2

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("BuyerAgent")

load_dotenv(override=True)

def buyer():
    env = EnvSettings()

    def on_new_task(job: ACPJob, memo_to_sign: Optional[ACPMemo] = None):
        logger.info(f"[on_new_task] Received job {job.id} (phase: {job.phase})")
        if (
                job.phase == ACPJobPhase.NEGOTIATION
                and memo_to_sign is not None
                and memo_to_sign.next_phase == ACPJobPhase.TRANSACTION
        ):
            logger.info(f"Paying job {job.id}")
            job.pay_and_accept_requirement()
            logger.info(f"Job {job.id} paid")
        elif (
                job.phase == ACPJobPhase.TRANSACTION
                and memo_to_sign is not None
                and memo_to_sign.next_phase == ACPJobPhase.REJECTED
        ):
            logger.info(f"Signing job rejection memo {job}")
            memo_to_sign.sign(True, "accepts job rejection")
            logger.info(f"Job {job.id} rejection memo signed")
        elif job.phase == ACPJobPhase.COMPLETED:
            logger.info(f"Job {job.id} completed")
        elif job.phase == ACPJobPhase.REJECTED:
            logger.info(f"Job {job.id} rejected")

    acp_client = VirtualsACP(
        acp_contract_clients=ACPContractClientV2(
            wallet_private_key=env.WHITELISTED_WALLET_PRIVATE_KEY,
            agent_wallet_address=env.BUYER_AGENT_WALLET_ADDRESS,
            entity_id=env.BUYER_ENTITY_ID,
            config=BASE_SEPOLIA_CONFIG_V2
        ),
        on_new_task=on_new_task
    )

    # Browse available agents
    relevant_agents = acp_client.browse_agents(
        keyword="<your-filter-agent-keyword>",
        sort_by=[ACPAgentSort.SUCCESSFUL_JOB_COUNT],
        top_k=5,
        graduation_status=ACPGraduationStatus.ALL,
        online_status=ACPOnlineStatus.ALL,
    )
    logger.info(f"Relevant agents: {relevant_agents}")

    # Pick the first agent
    chosen_agent = relevant_agents[0]

    # Pick the first job offering
    chosen_job_offering = chosen_agent.job_offerings[0]

    # Initiate job with plain string requirement
    job_id = chosen_job_offering.initiate_job(
        service_requirement={ "<your_schema_field>": "Help me to generate a flower meme." },
        evaluator_address=env.BUYER_AGENT_WALLET_ADDRESS,
        expired_at=datetime.now() + timedelta(days=1)
    )

    logger.info(f"Job {job_id} initiated")
    logger.info("Listening for next steps...")

    # Keep script alive
    threading.Event().wait()


if __name__ == "__main__":
    buyer()
