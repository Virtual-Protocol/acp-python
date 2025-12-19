import logging
import time
from typing import List

from dotenv import load_dotenv

from virtuals_acp.client import VirtualsACP
from virtuals_acp.contract_clients.contract_client_v2 import ACPContractClientV2
from virtuals_acp.env import EnvSettings
from virtuals_acp.job import ACPJob
from virtuals_acp.models import ACPJobPhase, DeliverablePayload

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

REJECT_JOB_IN_REQUEST_PHASE = False
REJECT_JOB_IN_OTHER_PHASE = False


def seller():
    env = EnvSettings()

    acp_client = VirtualsACP(
        acp_contract_clients=ACPContractClientV2(
            wallet_private_key=env.WHITELISTED_WALLET_PRIVATE_KEY,
            agent_wallet_address=env.SELLER_AGENT_WALLET_ADDRESS,
            entity_id=env.SELLER_ENTITY_ID,
        ),
    )

    while True:
        logger.info(
            f"\nPolling for active jobs for {acp_client.agent_address}."
        )
        active_jobs_list: List[ACPJob] = acp_client.get_active_jobs()

        if not active_jobs_list:
            logger.info("No active jobs found in this poll.")
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        for job in active_jobs_list:
            # Ensure this job is for the current seller
            if job.provider_address != acp_client.agent_address:
                continue

            try:
                # Fetch full details to get current phase and memos
                logger.info(
                    f"Checking job {job.id}. Current Phase: {job.phase.name}"
                )

                # 1. Respond to Job Request (if not already responded)
                if job.phase == ACPJobPhase.REQUEST:
                    logger.info(
                        f"Job {job.id} is in REQUEST phase. Responding to buyer's request."
                    )
                    if REJECT_JOB_IN_REQUEST_PHASE:
                        job.reject("Job requirement does not meet agent capability")
                    else:
                        job.accept("Job requirement matches agent capability")
                        job.create_requirement(f"Job {job.id} accepted, please make payment to proceed")

                    logger.info(
                        f"{"Rejected" if REJECT_JOB_IN_REQUEST_PHASE else "Accepted"} job {job.id}. Job phase should move to {ACPJobPhase(job.phase + 1).name}."
                    )
                # 2. Submit Deliverable (if job is paid and not yet delivered)
                elif job.phase == ACPJobPhase.TRANSACTION:
                    # Buyer has paid, job is in TRANSACTION. Seller needs to deliver.
                    logger.info(
                        f"Job {job.id} is PAID (TRANSACTION phase). Submitting deliverable."
                    )
                    deliverable: DeliverablePayload = {
                        "type": "url",
                        "value": "https://example.com"
                    }
                    job.deliver(deliverable)
                    logger.info(
                        f"Deliverable submitted for job {job.id}. Job should move to {ACPJobPhase(job.phase + 1).name}."
                    )

                elif job.phase in [
                    ACPJobPhase.EVALUATION,
                    ACPJobPhase.COMPLETED,
                    ACPJobPhase.REJECTED,
                ]:
                    logger.info(
                        f"Job {job.id} is in {job.phase.name}. No further action for seller."
                    )

            except Exception as e:
                logger.error(f"Error processing job {job.id}: {e}")

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    seller()
