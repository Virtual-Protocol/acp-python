import logging
import threading
from typing import Optional

from dotenv import load_dotenv

from virtuals_acp.memo import ACPMemo
from virtuals_acp.client import VirtualsACP
from virtuals_acp.env import EnvSettings
from virtuals_acp.job import ACPJob
from virtuals_acp.models import ACPJobPhase
from virtuals_acp.contract_clients.contract_client_v2 import ACPContractClientV2

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("SellerAgent")

load_dotenv(override=True)

REJECT_JOB = False

def seller():
    env = EnvSettings()

    def on_new_task(job: ACPJob, memo_to_sign: Optional[ACPMemo] = None):
        logger.info(f"[on_new_task] Received job {job.id} (phase: {job.phase})")

        if (
            job.phase == ACPJobPhase.REQUEST
            and memo_to_sign is not None
            and memo_to_sign.next_phase == ACPJobPhase.NEGOTIATION
        ):
            response = True
            logger.info(f"Responding to job {job.id} with requirement {job.requirement}")
            job.respond(response)
            logger.info(f"Job {job.id} responded with {response}")

        elif (
            job.phase == ACPJobPhase.TRANSACTION
            and memo_to_sign is not None
            and memo_to_sign.next_phase == ACPJobPhase.EVALUATION
        ):
            # to cater cases where agent decide to reject job after payment has been made
            if REJECT_JOB: # conditional check for job rejection logic
                reason = "Job requirement does not meet agent capability"
                logger.info(f"Rejecting job {job.id} with reason: {reason}")
                job.respond(False, reason=reason)
                logger.info(f"Job {job.id} rejected")
                return

            deliverable = {
                "type": "url",
                "value": "https://example.com"
            }
            logger.info(f"Delivering job {job.id} with deliverable {deliverable}")
            job.deliver(deliverable)
            logger.info(f"Job {job.id} delivered")
            return

        elif job.phase == ACPJobPhase.COMPLETED:
            logger.info(f"Job {job.id} completed")

        elif job.phase == ACPJobPhase.REJECTED:
            logger.info(f"Job {job.id} rejected")

    VirtualsACP(
        acp_contract_clients=ACPContractClientV2(
            wallet_private_key=env.WHITELISTED_WALLET_PRIVATE_KEY,
            agent_wallet_address=env.SELLER_AGENT_WALLET_ADDRESS,
            entity_id=env.SELLER_ENTITY_ID
        ),
        on_new_task=on_new_task
    )

    logger.info("Seller agent is running, waiting for new tasks...")
    threading.Event().wait()


if __name__ == "__main__":
    seller()
