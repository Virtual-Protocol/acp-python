import threading
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv

from virtuals_acp import ACPMemo
from virtuals_acp.client import VirtualsACP
from virtuals_acp.env import EnvSettings
from virtuals_acp.job import ACPJob
from virtuals_acp.models import ACPAgentSort, ACPJobPhase, ACPGraduationStatus, ACPOnlineStatus

load_dotenv(override=True)

def buyer():
    env = EnvSettings()

    def on_new_task(job: ACPJob, memo_to_sign: Optional[ACPMemo] = None):
        print(f"[on_new_task] Received job {job.id} (phase: {job.phase})")
        if (
            job.phase == ACPJobPhase.NEGOTIATION and
            memo_to_sign is not None and
                memo_to_sign.next_phase == ACPJobPhase.TRANSACTION
        ):
            print("Paying job", job.id)
            job.pay(job.price)
        elif job.phase == ACPJobPhase.EVALUATION:
            print("Evaluation function called", job.memos)
            job.evaluate(True)
        elif job.phase == ACPJobPhase.COMPLETED:
            print("Job completed", job)
        elif job.phase == ACPJobPhase.REJECTED:
            print("Job rejected", job)
            
    if env.WHITELISTED_WALLET_PRIVATE_KEY is None:
        raise Exception("WHITELISTED_WALLET_PRIVATE_KEY is not set")
    if env.BUYER_ENTITY_ID is None:
        raise Exception("BUYER_ENTITY_ID is not set")
    if env.BUYER_AGENT_WALLET_ADDRESS is None:
        raise Exception("BUYER_AGENT_WALLET_ADDRESS is not set")
            
    acp = VirtualsACP(
        wallet_private_key=env.WHITELISTED_WALLET_PRIVATE_KEY,
        agent_wallet_address=env.BUYER_AGENT_WALLET_ADDRESS,
        on_new_task=on_new_task,
        entity_id=env.BUYER_ENTITY_ID
    )
    
    # Browse available agents based on a keyword and cluster name
    relevant_agents = acp.browse_agents(
        keyword="<your_filter_agent_keyword>",
        cluster="<your_cluster_name>",
        sort_by=[
            ACPAgentSort.SUCCESSFUL_JOB_COUNT,
        ],
        top_k=5,
        graduation_status=ACPGraduationStatus.ALL,
        online_status=ACPOnlineStatus.ALL
    )
    print(f"Relevant agents: {relevant_agents}")
    
    # Pick one of the agents based on your criteria (in this example we just pick the first one)
    chosen_agent = relevant_agents[0]

    # Pick one of the service offerings based on your criteria (in this example we just pick the first one)
    chosen_job_offering = chosen_agent.offerings[0]
    
    job_id = chosen_job_offering.initiate_job(
        # <your_schema_field> can be found in your ACP Visualiser's "Edit Service" pop-up.
        # Reference: (./images/specify_requirement_toggle_switch.png)
        service_requirement={"<your_schema_field>": "Help me to generate a flower meme."},
        evaluator_address=env.BUYER_AGENT_WALLET_ADDRESS,
        expired_at=datetime.now() + timedelta(days=1)
    )
    
    print(f"Job {job_id} initiated")
    print("Listening for next steps...")
    # Keep the script running to listen for next steps
    threading.Event().wait()


if __name__ == "__main__":
    buyer()
