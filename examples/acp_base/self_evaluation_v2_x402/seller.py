import logging
import threading
from typing import Optional

from dotenv import load_dotenv

from virtuals_acp.contract_clients.contract_client_v2 import ACPContractClientV2
from virtuals_acp.memo import ACPMemo
from virtuals_acp.client import VirtualsACP
from virtuals_acp.env import EnvSettings
from virtuals_acp.job import ACPJob
from virtuals_acp.models import ACPJobPhase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("SellerAgent")

load_dotenv(override=True)


def seller():
    env = EnvSettings()

    def on_new_task(job: ACPJob, memo_to_sign: Optional[ACPMemo] = None):
        logger.info(f"[on_new_task] Received job {job.id} (phase: {job.phase})")
        if (
            job.phase == ACPJobPhase.REQUEST
            and memo_to_sign is not None
            and memo_to_sign.next_phase == ACPJobPhase.NEGOTIATION
        ):
            job.respond(True)
        elif (
            job.phase == ACPJobPhase.TRANSACTION
            and memo_to_sign is not None
            and memo_to_sign.next_phase == ACPJobPhase.EVALUATION
        ):
            logger.info(f"Delivering job {job.id}")
            deliverable = {"type": "url", "value": "https://example.com"}
            job.deliver(deliverable)
        elif job.phase == ACPJobPhase.COMPLETED:
            logger.info("Job completed", job)
        elif job.phase == ACPJobPhase.REJECTED:
            logger.info("Job rejected", job)

    if env.WHITELISTED_WALLET_PRIVATE_KEY is None:
        raise Exception("WHITELISTED_WALLET_PRIVATE_KEY is not set")
    if env.SELLER_ENTITY_ID is None:
        raise Exception("SELLER_ENTITY_ID is not set")
    if env.SELLER_AGENT_WALLET_ADDRESS is None:
        raise Exception("SELLER_AGENT_WALLET_ADDRESS is not set")

    # Initialize the ACP client

    acp_client = VirtualsACP(
        acp_contract_clients=ACPContractClientV2(
            wallet_private_key=env.WHITELISTED_WALLET_PRIVATE_KEY,
            agent_wallet_address=env.SELLER_AGENT_WALLET_ADDRESS,
            entity_id=env.SELLER_ENTITY_ID
        ),
        on_new_task=on_new_task,
    )

    logger.info("Waiting for new task...")
    # Keep the script running to listen for new tasks
    threading.Event().wait()


if __name__ == "__main__":
    seller()
