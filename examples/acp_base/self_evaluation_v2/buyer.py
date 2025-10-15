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
    ACPOnlineStatus
)
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
        ),
        on_new_task=on_new_task
    )

    # Browse available agents based on a keyword
    relevant_agents = acp_client.browse_agents(
        keyword="<your-filter-agent-keyword>",
        sort_by=[ACPAgentSort.SUCCESSFUL_JOB_COUNT],
        top_k=5,
        graduation_status=ACPGraduationStatus.ALL,
        online_status=ACPOnlineStatus.ALL,
    )
    logger.info(f"Relevant agents: {relevant_agents}")

    # Pick one of the agents based on your criteria (in this example we just pick the first one)
    chosen_agent = relevant_agents[0]
    # Pick one of the service offerings based on your criteria (in this example we just pick the first one)
    chosen_job_offering = chosen_agent.job_offerings[0]

    job_id = chosen_job_offering.initiate_job(
        service_requirement={ "<your_schema_field>": "<your_schema_value>" },
        evaluator_address=env.BUYER_AGENT_WALLET_ADDRESS, # evaluator address
        expired_at=datetime.now() + timedelta(days=1), # expiredAt
    )
    logger.info(f"Job {job_id} initiated")
    logger.info("Listening for next steps...")

    threading.Event().wait()


if __name__ == "__main__":
    buyer()
