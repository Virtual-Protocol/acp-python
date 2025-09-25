import json
import logging
import time
from typing import List

from dotenv import load_dotenv

from virtuals_acp import VirtualsACP, ACPJob, ACPJobPhase, IDeliverable, BASE_SEPOLIA_CONFIG
from virtuals_acp.contract_manager import ACPContractManager
from virtuals_acp.env import EnvSettings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("SellerAgent")

load_dotenv(override=True)

# --- Configuration for the job polling interval ---
POLL_INTERVAL_SECONDS = 20
# --------------------------------------------------


def seller():
    env = EnvSettings()

    acp_client = VirtualsACP(
        acp_contract_client=ACPContractManager(
            wallet_private_key=env.WHITELISTED_WALLET_PRIVATE_KEY,
            agent_wallet_address=env.SELLER_AGENT_WALLET_ADDRESS,
            entity_id=env.SELLER_ENTITY_ID,
            config=BASE_SEPOLIA_CONFIG
        ),
    )
    logger.info(f"Seller ACP Initialized. Agent: {acp_client.agent_address}")

    # Keep track of jobs to avoid reprocessing in this simple loop
    # job_id: {"responded_to_request": bool, "delivered_work": bool}
    processed_job_stages = {}

    while True:
        logger.info(
            f"\nSeller: Polling for active jobs for {env.SELLER_AGENT_WALLET_ADDRESS}..."
        )
        active_jobs_list: List[ACPJob] = acp_client.get_active_jobs()

        if not active_jobs_list:
            logger.info("Seller: No active jobs found in this poll.")
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        for job in active_jobs_list:
            onchain_job_id = job.id

            # Ensure this job is for the current seller
            if job.provider_address != acp_client.agent_address:
                continue

            job_stages = processed_job_stages.get(onchain_job_id, {})

            try:
                # Fetch full details to get current phase and memos
                job_details = acp_client.get_job_by_onchain_id(onchain_job_id)
                current_phase = job_details.phase
                logger.info(
                    f"Seller: Checking job {onchain_job_id}. Current Phase: {current_phase.name}"
                )

                # 1. Respond to Job Request (if not already responded)
                if current_phase == ACPJobPhase.REQUEST and not job_stages.get(
                    "responded_to_request"
                ):
                    logger.info(
                        f"Seller: Job {onchain_job_id} is in REQUEST. Responding to buyer's request..."
                    )
                    job.respond(
                        accept=True,
                        reason=f"Seller accepts the job offer.",
                    )
                    logger.info(
                        f"Seller: Accepted job {onchain_job_id}. Job phase should move to NEGOTIATION."
                    )
                    job_stages["responded_to_request"] = True
                # 2. Submit Deliverable (if job is paid and not yet delivered)
                elif current_phase == ACPJobPhase.TRANSACTION and not job_stages.get(
                    "delivered_work"
                ):
                    # Buyer has paid, job is in TRANSACTION. Seller needs to deliver.
                    logger.info(
                        f"Seller: Job {onchain_job_id} is PAID (TRANSACTION phase). Submitting deliverable..."
                    )
                    deliverable = IDeliverable(type="url", value="https://example.com")
                    job.deliver(deliverable)
                    logger.info(
                        f"Seller: Deliverable submitted for job {onchain_job_id}. Job should move to EVALUATION."
                    )
                    job_stages["delivered_work"] = True

                elif current_phase in [
                    ACPJobPhase.EVALUATION,
                    ACPJobPhase.COMPLETED,
                    ACPJobPhase.REJECTED,
                ]:
                    logger.info(
                        f"Seller: Job {onchain_job_id} is in {current_phase.name}. No further action for seller."
                    )
                    # Mark as fully handled for this script
                    job_stages["responded_to_request"] = True
                    job_stages["delivered_work"] = True

                processed_job_stages[onchain_job_id] = job_stages

            except Exception as e:
                logger.error(f"Seller: Error processing job {onchain_job_id}: {e}")

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    seller()
