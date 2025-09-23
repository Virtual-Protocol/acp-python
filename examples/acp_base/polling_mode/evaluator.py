import time
from typing import List

from dotenv import load_dotenv

from virtuals_acp import VirtualsACP, ACPJob, ACPJobPhase
from virtuals_acp.env import EnvSettings

load_dotenv(override=True)

# --- Configuration for the job polling interval ---
POLL_INTERVAL_SECONDS = 20
# --------------------------------------------------


def evaluator():
    env = EnvSettings()

    acp = VirtualsACP(
        wallet_private_key=env.WHITELISTED_WALLET_PRIVATE_KEY,
        agent_wallet_address=env.EVALUATOR_AGENT_WALLET_ADDRESS,
        entity_id=env.EVALUATOR_ENTITY_ID,
    )
    print(f"Evaluator ACP Initialized. Agent: {acp.agent_address}")

    while True:
        print(
            f"\nEvaluator: Polling for jobs assigned to {acp.agent_address} requiring evaluation..."
        )
        active_jobs_list: List[ACPJob] = acp.get_active_jobs()

        if not active_jobs_list:
            print("Evaluator: No active jobs found in this poll.")
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        for job in active_jobs_list:
            onchain_job_id = job.id

            try:
                job = acp.get_job_by_onchain_id(onchain_job_id)
                current_phase = job.phase

                # Ensure this job is for the current evaluator
                if job.evaluator_address != acp.agent_address:
                    continue

                if current_phase == ACPJobPhase.EVALUATION:
                    print(f"Evaluator: Found Job {onchain_job_id} in EVALUATION phase.")

                    # Simple evaluation logic: always accept
                    accept_the_delivery = True
                    evaluation_reason = "Deliverable looks great, approved!"

                    print(
                        f"  Job {onchain_job_id}: Evaluating... Accepting: {accept_the_delivery}"
                    )
                    job.evaluate(
                        accept=accept_the_delivery,
                        reason=evaluation_reason,
                    )
                    print(f"  Job {onchain_job_id}: Evaluation submitted.")
                elif current_phase in [ACPJobPhase.REQUEST, ACPJobPhase.NEGOTIATION]:
                    print(
                        f"Evaluator: Job {onchain_job_id} is in {current_phase.name} phase. Waiting for job to be delivered."
                    )
                    continue
                elif current_phase in [ACPJobPhase.COMPLETED, ACPJobPhase.REJECTED]:
                    print(
                        f"Evaluator: Job {onchain_job_id} is already in {current_phase.name}. No action."
                    )

            except Exception as e:
                print(f"Evaluator: Error processing job {onchain_job_id}: {e}")

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    evaluator()
