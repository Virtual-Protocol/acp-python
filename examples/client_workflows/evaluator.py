import os
import time
from typing import List
from dotenv import load_dotenv

from virtuals_acp import VirtualsACP, ACPJob, ACPJobPhase
from virtuals_acp.configs import BASE_SEPOLIA_CONFIG

load_dotenv(override=True)

EVALUATOR_PRIVATE_KEY = os.environ.get("WHITELISTED_WALLET_PRIVATE_KEY")
EVALUATOR_WALLET_ADDRESS = os.environ.get("EVALUATOR_AGENT_WALLET_ADDRESS")

POLL_INTERVAL_SECONDS = 20

if not all([EVALUATOR_PRIVATE_KEY, EVALUATOR_WALLET_ADDRESS]):
    print("Error: Ensure EVALUATOR_PRIVATE_KEY and EVALUATOR_WALLET_ADDRESS are set.")
    exit(1)

def main():
    print("--- Evaluator Script (Simplified Direct Client Usage) ---")
    evaluator_acp = VirtualsACP(
        wallet_private_key=EVALUATOR_PRIVATE_KEY,
        agent_wallet_address=EVALUATOR_WALLET_ADDRESS,
        config=BASE_SEPOLIA_CONFIG
    )
    print(f"Evaluator ACP Initialized. Agent: {evaluator_acp.agent_address}")

    evaluated_deliverables = set() # Store (job_id, deliverable_memo_id) to avoid re-evaluation

    while True:
        print(f"\nEvaluator: Polling for jobs assigned to {EVALUATOR_WALLET_ADDRESS} requiring evaluation...")
        active_jobs_list: List[ACPJob] = evaluator_acp.get_active_jobs()

        if not active_jobs_list:
            print("Evaluator: No active jobs found in this poll.")
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        for job_summary in active_jobs_list:
            onchain_job_id = job_summary.id
            
            try:
                job_details = evaluator_acp.get_job_by_onchain_id(onchain_job_id)
                current_phase = job_details.phase
                
                if current_phase == ACPJobPhase.EVALUATION:
                    print(f"Evaluator: Found Job {onchain_job_id} in EVALUATION phase.")
                    
                    # Find the seller's deliverable memo. Its next_phase should be COMPLETED.
                    seller_deliverable_memo_to_sign = None
                    for memo in reversed(job_details.memos): # Check latest first
                        if ACPJobPhase(memo.next_phase) == ACPJobPhase.COMPLETED:
                            seller_deliverable_memo_to_sign = memo
                            break
                    
                    if seller_deliverable_memo_to_sign:
                        deliverable_key = (onchain_job_id, seller_deliverable_memo_to_sign.id)
                        if deliverable_key in evaluated_deliverables:
                            # print(f"Deliverable memo {seller_deliverable_memo_to_sign.id} for job {onchain_job_id} already processed.")
                            continue

                        print(f"  Job {onchain_job_id}: Found deliverable memo {seller_deliverable_memo_to_sign.id} to evaluate.")
                        print(f"  Deliverable Content: {seller_deliverable_memo_to_sign.content}")
                        
                        # Simple evaluation logic: always accept
                        accept_the_delivery = True
                        evaluation_reason = "Deliverable looks great, approved!"
                        
                        print(f"  Job {onchain_job_id}: Evaluating... Accepting: {accept_the_delivery}")
                        evaluator_acp.evaluate_job_delivery(
                            memo_id_of_deliverable=seller_deliverable_memo_to_sign.id,
                            accept=accept_the_delivery,
                            reason=evaluation_reason
                        )
                        print(f"  Job {onchain_job_id}: Evaluation submitted for memo {seller_deliverable_memo_to_sign.id}.")
                        evaluated_deliverables.add(deliverable_key)
                    else:
                        print(f"  Job {onchain_job_id} in EVALUATION, but no deliverable memo (next_phase=COMPLETED) found yet.")
                elif current_phase in [ACPJobPhase.COMPLETED, ACPJobPhase.REJECTED]:
                    print(f"Evaluator: Job {onchain_job_id} is already in {current_phase.name}. No action.")
                    # Potentially add to a "handled" set if not using evaluated_deliverables
            
            except Exception as e:
                print(f"Evaluator: Error processing job {onchain_job_id}: {e}")
        
        time.sleep(POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()