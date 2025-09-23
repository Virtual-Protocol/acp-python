import json
import time
from typing import List

from dotenv import load_dotenv

from virtuals_acp import VirtualsACP, ACPJob, ACPJobPhase, IDeliverable
from virtuals_acp.env import EnvSettings

load_dotenv(override=True)

# --- Configuration for the job polling interval ---
POLL_INTERVAL_SECONDS = 20
# --------------------------------------------------


def seller():
    env = EnvSettings()

    acp = VirtualsACP(
        wallet_private_key=env.WHITELISTED_WALLET_PRIVATE_KEY,
        agent_wallet_address=env.SELLER_AGENT_WALLET_ADDRESS,
        entity_id=env.SELLER_ENTITY_ID,
    )
    print(f"Seller ACP Initialized. Agent: {acp.agent_address}")

    # Keep track of jobs to avoid reprocessing in this simple loop
    # job_id: {"responded_to_request": bool, "delivered_work": bool}
    processed_job_stages = {}

    while True:
        print(
            f"\nSeller: Polling for active jobs for {env.SELLER_AGENT_WALLET_ADDRESS}..."
        )
        active_jobs_list: List[ACPJob] = acp.get_active_jobs()

        if not active_jobs_list:
            print("Seller: No active jobs found in this poll.")
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        for job in active_jobs_list:
            onchain_job_id = job.id

            # Ensure this job is for the current seller
            if job.provider_address != acp.agent_address:
                continue

            job_stages = processed_job_stages.get(onchain_job_id, {})

            try:
                # Fetch full details to get current phase and memos
                job_details = acp.get_job_by_onchain_id(onchain_job_id)
                current_phase = job_details.phase
                print(
                    f"Seller: Checking job {onchain_job_id}. Current Phase: {current_phase.name}"
                )

                # 1. Respond to Job Request (if not already responded)
                if current_phase == ACPJobPhase.REQUEST and not job_stages.get(
                    "responded_to_request"
                ):
                    print(
                        f"Seller: Job {onchain_job_id} is in REQUEST. Responding to buyer's request..."
                    )
                    job.respond(
                        accept=True,
                        reason=f"Seller accepts the job offer.",
                    )
                    print(
                        f"Seller: Accepted job {onchain_job_id}. Job phase should move to NEGOTIATION."
                    )
                    job_stages["responded_to_request"] = True
                # 2. Submit Deliverable (if job is paid and not yet delivered)
                elif current_phase == ACPJobPhase.TRANSACTION and not job_stages.get(
                    "delivered_work"
                ):
                    # Buyer has paid, job is in TRANSACTION. Seller needs to deliver.
                    print(
                        f"Seller: Job {onchain_job_id} is PAID (TRANSACTION phase). Submitting deliverable..."
                    )
                    deliverable = IDeliverable(type="url", value="https://example.com")
                    job.deliver(deliverable)
                    print(
                        f"Seller: Deliverable submitted for job {onchain_job_id}. Job should move to EVALUATION."
                    )
                    job_stages["delivered_work"] = True

                elif current_phase in [
                    ACPJobPhase.EVALUATION,
                    ACPJobPhase.COMPLETED,
                    ACPJobPhase.REJECTED,
                ]:
                    print(
                        f"Seller: Job {onchain_job_id} is in {current_phase.name}. No further action for seller."
                    )
                    # Mark as fully handled for this script
                    job_stages["responded_to_request"] = True
                    job_stages["delivered_work"] = True

                processed_job_stages[onchain_job_id] = job_stages

            except Exception as e:
                print(f"Seller: Error processing job {onchain_job_id}: {e}")

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    seller()
