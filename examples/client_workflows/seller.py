import os
import time
import json
from typing import List
from dotenv import load_dotenv

from virtuals_acp import VirtualsACP, ACPJob, ACPJobPhase
from virtuals_acp.configs import BASE_SEPOLIA_CONFIG

load_dotenv(override=True)

SELLER_PRIVATE_KEY = os.environ.get("WHITELISTED_WALLET_PRIVATE_KEY")
SELLER_WALLET_ADDRESS = os.environ.get("SELLER_AGENT_WALLET_ADDRESS")

if not all([SELLER_PRIVATE_KEY, SELLER_WALLET_ADDRESS]):
    print("Error: Ensure SELLER_PRIVATE_KEY and SELLER_WALLET_ADDRESS are set.")
    exit(1)

DELIVERABLE_CONTENT = {
    "type": "url",
    "value": "https://virtuals.io/delivered_meme.png",
    "notes": "Your meme is ready!"
}

POLL_INTERVAL_SECONDS = 20

def main():
    print("--- Seller Script ---")
    seller_acp = VirtualsACP(
        wallet_private_key=SELLER_PRIVATE_KEY,
        agent_wallet_address=SELLER_WALLET_ADDRESS,
        config=BASE_SEPOLIA_CONFIG
    )
    print(f"Seller ACP Initialized. Agent: {seller_acp.agent_address}")

    # Keep track of jobs to avoid reprocessing in this simple loop
    # job_id: {"responded_to_request": bool, "delivered_work": bool}
    processed_job_stages = {}

    while True:
        print(f"\nSeller: Polling for active jobs for {SELLER_WALLET_ADDRESS}...")
        active_jobs_list: List[ACPJob] = seller_acp.get_active_jobs()

        if not active_jobs_list:
            print("Seller: No active jobs found in this poll.")
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
            
        for job_summary in active_jobs_list:
            onchain_job_id = job_summary.id

            # Ensure this job is for the current seller
            if job_summary.provider_address != seller_acp.agent_address:
                continue

            job_stages = processed_job_stages.get(onchain_job_id, {})

            try:
                # Fetch full details to get current phase and memos
                job_details = seller_acp.get_job_by_onchain_id(onchain_job_id)
                current_phase = job_details.phase
                print(f"Seller: Checking job {onchain_job_id}. Current Phase: {current_phase.name}")

                # 1. Respond to Job Request (if not already responded)
                if current_phase == ACPJobPhase.REQUEST and not job_stages.get("responded_to_request"):
                    # Buyer's initial memo will have next_phase = NEGOTIATION
                    buyers_initial_memo_to_sign = None
                    for memo in reversed(job_details.memos):
                        if ACPJobPhase(memo.next_phase) == ACPJobPhase.NEGOTIATION:
                            buyers_initial_memo_to_sign = memo
                            break
                    
                    if buyers_initial_memo_to_sign:
                        print(f"Seller: Job {onchain_job_id} is in REQUEST. Responding to buyer's memo {buyers_initial_memo_to_sign.id}...")
                        seller_acp.respond_to_job_memo(
                            job_id=onchain_job_id,
                            memo_id=buyers_initial_memo_to_sign.id, # ID of the memo created by Buyer
                            accept=True,
                            reason="Seller accepts the job offer."
                        )
                        print(f"Seller: Accepted job {onchain_job_id}. Job phase should move to NEGOTIATION.")
                        job_stages["responded_to_request"] = True
                    else:
                        print(f"Seller: Job {onchain_job_id} in REQUEST, but could not find buyer's initial memo.")
                
                # 2. Submit Deliverable (if job is paid and not yet delivered)
                elif current_phase == ACPJobPhase.TRANSACTION and not job_stages.get("delivered_work"):
                    # Buyer has paid, job is in TRANSACTION. Seller needs to deliver.
                    # The latest memo from buyer would have next_phase = EVALUATION
                    buyers_payment_confirmation_memo = None
                    for memo in reversed(job_details.memos):
                        if ACPJobPhase(memo.next_phase) == ACPJobPhase.EVALUATION:
                            buyers_payment_confirmation_memo = memo
                            break
                    
                    if buyers_payment_confirmation_memo:
                        print(f"Seller: Job {onchain_job_id} is PAID (TRANSACTION phase). Submitting deliverable...")
                        seller_acp.submit_job_deliverable(
                            job_id=onchain_job_id,
                            deliverable_content=json.dumps(DELIVERABLE_CONTENT)
                        )
                        print(f"Seller: Deliverable submitted for job {onchain_job_id}. Job should move to EVALUATION.")
                        job_stages["delivered_work"] = True
                    else:
                        print(f"Seller: Job {onchain_job_id} in TRANSACTION, but couldn't find buyer's payment memo to confirm.")

                elif current_phase in [ACPJobPhase.EVALUATION, ACPJobPhase.COMPLETED, ACPJobPhase.REJECTED]:
                    print(f"Seller: Job {onchain_job_id} is in {current_phase.name}. No further action for seller.")
                    # Mark as fully handled for this script
                    job_stages["responded_to_request"] = True
                    job_stages["delivered_work"] = True
                
                processed_job_stages[onchain_job_id] = job_stages

            except Exception as e:
                print(f"Seller: Error processing job {onchain_job_id}: {e}")
        
        time.sleep(POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()