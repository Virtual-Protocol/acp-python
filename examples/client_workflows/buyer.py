import os
import time
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

from virtuals_acp import VirtualsACP, ACPJob, ACPJobPhase
from virtuals_acp.configs import BASE_SEPOLIA_CONFIG

load_dotenv(override=True)

BUYER_PRIVATE_KEY = os.environ.get("WHITELISTED_WALLET_PRIVATE_KEY")
BUYER_WALLET_ADDRESS = os.environ.get("BUYER_AGENT_WALLET_ADDRESS")

# --- Configuration for the job ---
POLL_INTERVAL_SECONDS = 10
TARGET_SELLER_WALLET = os.environ.get("SELLER_AGENT_WALLET_ADDRESS")
TARGET_EVALUATOR_WALLET = os.environ.get("EVALUATOR_AGENT_WALLET_ADDRESS")
SERVICE_PRICE = "1"
SERVICE_REQUIREMENT = {
    "prompt": "Create a funny cat meme for a Python SDK example",
    "format": "png"
}
# ----------------------------------

if not all([BUYER_PRIVATE_KEY, BUYER_WALLET_ADDRESS, TARGET_SELLER_WALLET, TARGET_EVALUATOR_WALLET]):
    print("Error: Ensure BUYER_PRIVATE_KEY, BUYER_WALLET_ADDRESS, SELLER_WALLET_ADDRESS, EVALUATOR_WALLET_ADDRESS are set.")
    exit(1)

def main():

    print("--- Buyer Script ---")
    buyer_acp = VirtualsACP(
        wallet_private_key=BUYER_PRIVATE_KEY,
        agent_wallet_address=BUYER_WALLET_ADDRESS,
        config=BASE_SEPOLIA_CONFIG
    )
    print(f"Buyer ACP Initialized. Agent: {buyer_acp.agent_address}")

    # 1. Initiate Job
    print(f"\nInitiating job with Seller: {TARGET_SELLER_WALLET}, Evaluator: {TARGET_EVALUATOR_WALLET}")
    expired_at = datetime.now(timezone.utc) + timedelta(days=1)

    onchain_job_id = buyer_acp.initiate_job(
        provider_address=TARGET_SELLER_WALLET,
        service_requirement=SERVICE_REQUIREMENT, # Already a dict
        expired_at=expired_at,
        evaluator_address=TARGET_EVALUATOR_WALLET,
        amount=float(SERVICE_PRICE) # Pass actual price for API record
    )
    print(f"Job {onchain_job_id} initiated.")

    # 2. Wait for Seller's acceptance memo (which sets next_phase to TRANSACTION)
    print(f"\nWaiting for Seller to accept job {onchain_job_id}...")
    memo_to_sign_for_payment_id = None
    
    while True:
        # wait for some time before checking job again
        time.sleep(POLL_INTERVAL_SECONDS)
        job_details: ACPJob = buyer_acp.get_job_by_onchain_id(onchain_job_id)
        print(f"Polling Job {onchain_job_id}: Current Phase: {job_details.phase.name}")

        if job_details.phase == ACPJobPhase.NEGOTIATION:
            # Seller has responded. Find the memo they created.
            # This memo will have next_phase = TRANSACTION.
            found_seller_memo = False
            for memo in reversed(job_details.memos): # Check latest memo first
                # Find the seller's response memo.
                if ACPJobPhase(memo.next_phase) == ACPJobPhase.TRANSACTION:
                    memo_to_sign_for_payment_id = memo.id
                    print(f"Seller accepted. Buyer will sign seller's memo {memo_to_sign_for_payment_id} for payment.")
                    found_seller_memo = True
                    break 
            if found_seller_memo:
                break # Exit while loop

        elif job_details.phase == ACPJobPhase.REJECTED:
            print(f"Job {onchain_job_id} was rejected by seller.")
            return # Exit main function
        elif job_details.phase == ACPJobPhase.REQUEST:
            print(f"Job {onchain_job_id} still in REQUEST phase. Waiting for seller...")

    if not memo_to_sign_for_payment_id:
        print(f"Could not identify seller's acceptance memo for job {onchain_job_id}. Exiting.")
        return

    # 3. Pay for the Job
    print(f"\nPaying for job {onchain_job_id} (Price: {SERVICE_PRICE}), by signing memo {memo_to_sign_for_payment_id}...")
    try:
        buyer_acp.pay_for_job(
            job_id=onchain_job_id,
            memo_id=memo_to_sign_for_payment_id,
            amount=SERVICE_PRICE,
            reason="Payment for meme generation service."
        )
        print(f"Payment process initiated for job {onchain_job_id}.")
    except Exception as e:
        print(f"Error paying for job {onchain_job_id}: {e}")
        return

    # 4. Wait for Job Completion
    print(f"\nWaiting for job {onchain_job_id} to be completed by evaluator...")
    while True:
        time.sleep(POLL_INTERVAL_SECONDS)
        job_details = buyer_acp.get_job_by_onchain_id(onchain_job_id)
        print(f"Polling Job {onchain_job_id}: Current Phase: {job_details.phase.name}")

        if job_details.phase == ACPJobPhase.COMPLETED:
            print(f"Job {onchain_job_id} successfully COMPLETED!")
            break
        elif job_details.phase == ACPJobPhase.REJECTED:
            print(f"Job {onchain_job_id} was REJECTED during/after evaluation.")
            break
        elif job_details.phase == ACPJobPhase.EVALUATION:
            print(f"Job {onchain_job_id} is in EVALUATION. Waiting for evaluator's decision...")
        elif job_details.phase == ACPJobPhase.TRANSACTION:
             print(f"Job {onchain_job_id} is in TRANSACTION. Waiting for seller to deliver...")
        # else, keep polling for other phases

    print("\n--- Buyer Script Finished ---")

if __name__ == "__main__":
    main()