import threading
from typing import Optional

from dotenv import load_dotenv

from virtuals_acp import ACPMemo
from virtuals_acp.client import VirtualsACP
from virtuals_acp.env import EnvSettings
from virtuals_acp.job import ACPJob
from virtuals_acp.models import ACPJobPhase, IDeliverable
from virtuals_acp.contract_manager import ACPContractManager
from virtuals_acp.configs import BASE_SEPOLIA_CONFIG

load_dotenv(override=True)


def seller():
    env = EnvSettings()

    def on_new_task(job: ACPJob, memo_to_sign: Optional[ACPMemo] = None):
        print(f"[on_new_task] Received job {job.id} (phase: {job.phase})")

        if (
            job.phase == ACPJobPhase.REQUEST
            and memo_to_sign is not None
            and memo_to_sign.next_phase == ACPJobPhase.NEGOTIATION
        ):
            print(f"Responding to job {job.id}")
            job.respond(True)
            print(f"Job {job.id} responded")

        elif (
            job.phase == ACPJobPhase.TRANSACTION
            and memo_to_sign is not None
            and memo_to_sign.next_phase == ACPJobPhase.EVALUATION
        ):
            print(f"Delivering job {job.id}")
            deliverable = IDeliverable(
                type="url",
                value="https://example.com",
            )
            job.deliver(deliverable)
            print(f"Job {job.id} delivered")

        elif job.phase == ACPJobPhase.COMPLETED:
            print(f"Job {job.id} completed")

        elif job.phase == ACPJobPhase.REJECTED:
            print(f"Job {job.id} rejected")

    # Validate required env variables
    for field in [
        "WHITELISTED_WALLET_PRIVATE_KEY",
        "SELLER_ENTITY_ID",
        "SELLER_AGENT_WALLET_ADDRESS",
    ]:
        if getattr(env, field) is None:
            raise Exception(f"{field} is not set")

    # Initialize the ACP client
    acp_client = VirtualsACP(
        acp_contract_client=ACPContractManager(
            wallet_private_key=env.WHITELISTED_WALLET_PRIVATE_KEY,
            agent_wallet_address=env.SELLER_AGENT_WALLET_ADDRESS,
            entity_id=env.SELLER_ENTITY_ID,
            config=BASE_SEPOLIA_CONFIG,
        ),
        on_new_task=on_new_task,
    )

    print("Seller agent is running, waiting for new tasks...")
    threading.Event().wait()


if __name__ == "__main__":
    seller()
