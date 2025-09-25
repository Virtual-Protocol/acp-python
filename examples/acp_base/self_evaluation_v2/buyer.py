import threading
import logging
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from virtuals_acp import ACPMemo
from virtuals_acp.client import VirtualsACP
from virtuals_acp.env import EnvSettings
from virtuals_acp.job import ACPJob
from virtuals_acp.models import (
    ACPAgentSort,
    ACPJobPhase,
    ACPGraduationStatus,
    ACPOnlineStatus,
)
from virtuals_acp.contract_manager import ACPContractManager
from virtuals_acp.configs import BASE_SEPOLIA_CONFIG

load_dotenv(override=True)

def buyer():
    env = EnvSettings()

    def on_new_task(job: ACPJob, memo_to_sign: Optional[ACPMemo] = None):
        print(f"[on_new_task] Received job {job.id} (phase: {job.phase})")
        if (
            job.phase == ACPJobPhase.NEGOTIATION
            and memo_to_sign is not None
            and memo_to_sign.next_phase == ACPJobPhase.TRANSACTION
        ):
            print("Paying job", job.id)
            job.pay_and_accept_requirement()
            print(f"Job {job.id} paid")
        elif job.phase == ACPJobPhase.COMPLETED:
            print(f"Job {job.id} completed")
        elif job.phase == ACPJobPhase.REJECTED:
            print(f"Job {job.id} rejected")

    def on_evaluate(job: ACPJob):
        print(f"Evaluation function called for job {job.id}")
        job.evaluate(True)

    # Validate env variables
    for field in [
        "WHITELISTED_WALLET_PRIVATE_KEY",
        "BUYER_ENTITY_ID",
        "BUYER_AGENT_WALLET_ADDRESS",
    ]:
        if getattr(env, field) is None:
            raise Exception(f"{field} is not set")

    acp = VirtualsACP(
        acp_contract_client=ACPContractManager(
            wallet_private_key=env.WHITELISTED_WALLET_PRIVATE_KEY,
            agent_wallet_address=env.BUYER_AGENT_WALLET_ADDRESS,
            entity_id=env.BUYER_ENTITY_ID,
            config=BASE_SEPOLIA_CONFIG,
        ),
        on_new_task=on_new_task,
        on_evaluate=on_evaluate
    )

    # Browse available agents
    relevant_agents = acp.browse_agents(
        keyword="<your_filter_agent_keyword>",
        sort_by=[ACPAgentSort.SUCCESSFUL_JOB_COUNT],
        top_k=5,
        graduation_status=ACPGraduationStatus.ALL,
        online_status=ACPOnlineStatus.ALL,
    )
    print(f"Relevant agents: {relevant_agents}")

    # Pick the first agent
    chosen_agent = relevant_agents[0]

    # Pick the first job offering
    chosen_job_offering = chosen_agent.job_offerings[0]

    # Initiate job with plain string requirement
    job_id = chosen_job_offering.initiate_job(
        {"service_requirement": "Help me to generate a flower meme."},
        evaluator_address=env.BUYER_AGENT_WALLET_ADDRESS,
        expired_at=datetime.now() + timedelta(days=1)
    )

    print(f"Job {job_id} initiated")
    print("Listening for next steps...")

    # Keep script alive
    threading.Event().wait()


if __name__ == "__main__":
    buyer()
