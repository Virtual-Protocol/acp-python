import logging
import time
from typing import List

from dotenv import load_dotenv

from virtuals_acp import VirtualsACP, ACPJob, ACPJobPhase, BASE_SEPOLIA_CONFIG
from virtuals_acp.contract_manager import ACPContractManager
from virtuals_acp.env import EnvSettings

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


def evaluator():
    env = EnvSettings()

    acp_client = VirtualsACP(
        acp_contract_client=ACPContractManager(
            wallet_private_key=env.WHITELISTED_WALLET_PRIVATE_KEY,
            agent_wallet_address=env.EVALUATOR_AGENT_WALLET_ADDRESS,
            entity_id=env.EVALUATOR_ENTITY_ID,
            config=BASE_SEPOLIA_CONFIG,
        ),
    )
    logger.info(f"Evaluator ACP Initialized. Agent: {acp_client.agent_address}")

    while True:
        logger.info(
            f"\nEvaluator: Polling for jobs assigned to {acp_client.agent_address} requiring evaluation..."
        )
        active_jobs_list: List[ACPJob] = acp_client.get_active_jobs()

        if not active_jobs_list:
            logger.info("Evaluator: No active jobs found in this poll.")
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        for job in active_jobs_list:
            onchain_job_id = job.id

            try:
                job = acp_client.get_job_by_onchain_id(onchain_job_id)
                current_phase = job.phase

                # Ensure this job is for the current evaluator
                if job.evaluator_address != acp_client.agent_address:
                    continue

                if current_phase == ACPJobPhase.EVALUATION:
                    logger.info(f"Evaluator: Found Job {onchain_job_id} in EVALUATION phase.")

                    # Simple evaluation logic: always accept
                    accept_the_delivery = True
                    evaluation_reason = "Deliverable looks great, approved!"

                    logger.info(
                        f"  Job {onchain_job_id}: Evaluating... Accepting: {accept_the_delivery}"
                    )
                    job.evaluate(
                        accept=accept_the_delivery,
                        reason=evaluation_reason,
                    )
                    logger.info(f"  Job {onchain_job_id}: Evaluation submitted.")
                elif current_phase in [ACPJobPhase.REQUEST, ACPJobPhase.NEGOTIATION]:
                    logger.info(
                        f"Evaluator: Job {onchain_job_id} is in {current_phase.name} phase. Waiting for job to be delivered."
                    )
                    continue
                elif current_phase in [ACPJobPhase.COMPLETED, ACPJobPhase.REJECTED]:
                    logger.info(
                        f"Evaluator: Job {onchain_job_id} is already in {current_phase.name}. No action."
                    )

            except Exception as e:
                logger.error(f"Evaluator: Error processing job {onchain_job_id}: {e}")

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    evaluator()
