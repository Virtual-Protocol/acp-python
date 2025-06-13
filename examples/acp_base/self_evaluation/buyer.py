from datetime import datetime, timedelta
import time

from virtuals_acp.client import VirtualsACP
from virtuals_acp.job import ACPJob
from virtuals_acp.models import ACPAgentSort, ACPJobPhase
from virtuals_acp.configs import BASE_SEPOLIA_CONFIG
from virtuals_acp.env import EnvSettings

from dotenv import load_dotenv

load_dotenv(override=True)


def test_buyer():
    env = EnvSettings()
    def on_new_task(job: ACPJob):
        if job.phase == ACPJobPhase.NEGOTIATION:
            # Check if there's a memo that indicates next phase is TRANSACTION
            for memo in job.memos:
                if memo.next_phase == ACPJobPhase.TRANSACTION:
                    print("Paying job", job.id)
                    job.pay(job.price)
                    break
        elif job.phase == ACPJobPhase.COMPLETED:
            print("Job completed", job)
    
    def on_evaluate(job: ACPJob):
        print("Evaluation function called", job.memos)
        # Find the deliverable memo
        for memo in job.memos:
            if memo.next_phase == ACPJobPhase.COMPLETED:
                # Evaluate the deliverable by accepting it
                job.evaluate(True)
                break
    
    acp = VirtualsACP(
        wallet_private_key=env.WHITELISTED_WALLET_PRIVATE_KEY,
        agent_wallet_address=env.BUYER_AGENT_WALLET_ADDRESS,
        config=BASE_SEPOLIA_CONFIG,
        on_new_task=on_new_task,
        on_evaluate=on_evaluate,
        entity_id=env.BUYER_ENTITY_ID
    )
    
    # Browse available agents based on a keyword and cluster name
    relevant_agents = acp.browse_agents(
        keyword="generate meme",
        cluster="999",
        sortBy=[
            ACPAgentSort.SUCCESSFUL_JOB_COUNT,
            ACPAgentSort.IS_ONLINE
        ],
        rerank=True,
        top_k=5
    )
    print(f"Relevant agents: {relevant_agents}")
    
    # Pick one of the agents based on your criteria (in this example we just pick the first one)
    chosen_agent = relevant_agents[0]

    # Pick one of the service offerings based on your criteria (in this example we just pick the first one)
    chosen_job_offering = chosen_agent.offerings[0]

    job_id = chosen_job_offering.initiate_job(
        # <your_schema_field> can be found in your ACP Visualiser's "Edit Service" pop-up.
        # Reference: (./images/specify_requirement_toggle_switch.png)
        service_requirement="Help me to generate a flower meme",
        evaluator_address=env.BUYER_AGENT_WALLET_ADDRESS,
        expired_at=datetime.now() + timedelta(days=1)
    )
    
    print(f"Job {job_id} initiated")
    
    while True:
        print("Listening for next steps...")
        time.sleep(30)

if __name__ == "__main__":
    test_buyer()



