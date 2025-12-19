import logging
import time
from typing import List

from dotenv import load_dotenv

from virtuals_acp.client import VirtualsACP
from virtuals_acp.contract_clients.contract_client_v2 import ACPContractClientV2
from virtuals_acp.env import EnvSettings
from virtuals_acp.job import ACPJob
from virtuals_acp.models import ACPJobPhase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("EvaluatorAgent")

load_dotenv(override=True)

# --- Configuration for the job polling interval ---
POLL_INTERVAL_SECONDS = 20
# --------------------------------------------------

ACCEPT_EVALUATION = True


def evaluator():
    env = EnvSettings()

    acp_client = VirtualsACP(
        acp_contract_clients=ACPContractClientV2(
            wallet_private_key=env.WHITELISTED_WALLET_PRIVATE_KEY,
            agent_wallet_address=env.EVALUATOR_AGENT_WALLET_ADDRESS,
            entity_id=env.EVALUATOR_ENTITY_ID,
        ),
    )
    logger.info(f"Evaluator ACP Initialized. Agent: {acp_client.agent_address}")

    while True:
        logger.info(
            f"\nPolling for jobs assigned to {acp_client.agent_address} requiring evaluation."
        )
        active_jobs_list: List[ACPJob] = acp_client.get_active_jobs()

        if not active_jobs_list:
            logger.info("No active jobs found in this poll.")
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        for job in active_jobs_list:

            try:

                # Ensure this job is for the current evaluator
                if job.evaluator_address != acp_client.agent_address:
                    continue

                if job.phase == ACPJobPhase.EVALUATION:
                    logger.info(f"Found Job {job.id} in EVALUATION phase.")
                    logger.info(
                        f"Job {job.id}: Evaluating deliverable: {job.deliverable} with requirement: {job.requirement}"
                    )
                    job.evaluate(
                        accept=ACCEPT_EVALUATION,
                        reason="Deliverable looks great, approved!" if ACCEPT_EVALUATION else "Deliverable not accepted.",
                    )
                    logger.info(f"Job {job.id}: Evaluated with {ACCEPT_EVALUATION}.")
                elif job.phase in [ACPJobPhase.REQUEST, ACPJobPhase.NEGOTIATION]:
                    logger.info(
                        f"Job {job.id} is in {job.phase.name} phase. Waiting for job to be delivered."
                    )
                    continue
                elif job.phase in [ACPJobPhase.COMPLETED, ACPJobPhase.REJECTED]:
                    logger.info(
                        f"Job {job.id} is already in {job.phase.name}. No action."
                    )

            except Exception as e:
                logger.error(f"Error processing job {job.id}: {e}")

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    evaluator()
