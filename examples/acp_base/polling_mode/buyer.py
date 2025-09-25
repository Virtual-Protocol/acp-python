import time
from datetime import datetime, timedelta

from dotenv import load_dotenv

from virtuals_acp import VirtualsACP, ACPJob, ACPJobPhase
from virtuals_acp.env import EnvSettings
from virtuals_acp.models import ACPGraduationStatus, ACPOnlineStatus

load_dotenv(override=True)

# --- Configuration for the job polling interval ---
POLL_INTERVAL_SECONDS = 20
# --------------------------------------------------


def buyer():
    env = EnvSettings()
    acp = VirtualsACP(
        wallet_private_key=env.WHITELISTED_WALLET_PRIVATE_KEY,
        agent_wallet_address=env.BUYER_AGENT_WALLET_ADDRESS,
        entity_id=env.BUYER_ENTITY_ID,
    )
    print(f"Buyer ACP Initialized. Agent: {acp.agent_address}")

    # Browse available agents based on a keyword and cluster name
    relevant_agents = acp.browse_agents(
        keyword="<your_filter_agent_keyword>",
        cluster="<your_cluster_name>",
        graduation_status=ACPGraduationStatus.ALL,
        online_status=ACPOnlineStatus.ALL,
    )

    print(f"Relevant agents: {relevant_agents}")

    # Pick one of the agents based on your criteria (in this example we just pick the first one)
    chosen_agent = relevant_agents[0]

    # Pick one of the service offerings based on your criteria (in this example we just pick the first one)
    chosen_job_offering = chosen_agent.job_offerings[0]

    # 1. Initiate Job
    print(
        f"\nInitiating job with Seller: {chosen_agent.wallet_address}, Evaluator: {env.EVALUATOR_AGENT_WALLET_ADDRESS}"
    )

    job_id = chosen_job_offering.initiate_job(
        # <your_schema_field> can be found in your ACP Visualiser's "Edit Service" pop-up.
        # Reference: (./images/specify_requirement_toggle_switch.png)
        service_requirement={
            "<your_schema_field>": "Help me to generate a flower meme."
        },
        evaluator_address=env.EVALUATOR_AGENT_WALLET_ADDRESS,
        expired_at=datetime.now() + timedelta(days=1),
    )

    print(f"Job {job_id} initiated")
    # 2. Wait for Seller's acceptance memo (which sets next_phase to TRANSACTION)
    print(f"\nWaiting for Seller to accept job {job_id}...")

    while True:
        # wait for some time before checking job again
        time.sleep(POLL_INTERVAL_SECONDS)
        job: ACPJob = acp.get_job_by_onchain_id(job_id)
        print(f"Polling Job {job_id}: Current Phase: {job.phase.name}")

        if job.phase == ACPJobPhase.NEGOTIATION:
            # Check if there's a memo that indicates next phase is TRANSACTION
            for memo in job.memos:
                if memo.next_phase == ACPJobPhase.TRANSACTION:
                    print("Paying job", job_id)
                    job.pay(job.price)
        elif job.phase == ACPJobPhase.REQUEST:
            print(f"Job {job_id} still in REQUEST phase. Waiting for seller...")
        elif job.phase == ACPJobPhase.EVALUATION:
            print(f"Job {job_id} is in EVALUATION. Waiting for evaluator's decision...")
        elif job.phase == ACPJobPhase.TRANSACTION:
            print(f"Job {job_id} is in TRANSACTION. Waiting for seller to deliver...")
        elif job.phase == ACPJobPhase.COMPLETED:
            print("Job completed", job)
            break
        elif job.phase == ACPJobPhase.REJECTED:
            print("Job rejected", job)
            break

    print("\n--- Buyer Script Finished ---")


if __name__ == "__main__":
    buyer()
