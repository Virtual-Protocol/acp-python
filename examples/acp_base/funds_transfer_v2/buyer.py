import threading
import time
import logging
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv

from virtuals_acp import ACPMemo
from virtuals_acp.configs import BASE_SEPOLIA_CONFIG
from virtuals_acp.client import VirtualsACP
from virtuals_acp.env import EnvSettings
from virtuals_acp.job import ACPJob
from virtuals_acp.models import ACPAgentSort, ACPJobPhase, ACPGraduationStatus, ACPOnlineStatus
from virtuals_acp.configs import BASE_SEPOLIA_CONFIG
from virtuals_acp.models import PayloadType
from virtuals_acp.contract_manager import ACPContractManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("BuyerAgent")

load_dotenv(override=True)

config = BASE_SEPOLIA_CONFIG


def buyer():
    env = EnvSettings()

    current_job = None

    def on_new_task(job: ACPJob, memo_to_sign: Optional[ACPMemo] = None):
        logger.info(f"[on_new_task] Received job {job.id} (phase: {job.phase})")

        if job.phase == ACPJobPhase.NEGOTIATION:
            logger.info(f"Paying job {job.id}")
            job.pay_and_accept_requirement("I accept the job requirements")
            current_job = job
            return
        
        current_job = job
        
        if job.phase != ACPJobPhase.TRANSACTION:
            logger.info(f"Job is not in transaction phase")
            return 
        
        if not memo_to_sign:
            logger.info(f"No memo to sign")
            return
    
    def on_evaluate(job: ACPJob):
        logger.info(f"Evaluation function called for job {job.id}")
        job.evaluate(True)
    
    if env.WHITELISTED_WALLET_PRIVATE_KEY is None:
        raise Exception("WHITELISTED_WALLET_PRIVATE_KEY is not set")
    if env.BUYER_ENTITY_ID is None:
        raise Exception("BUYER_ENTITY_ID is not set")
    if env.BUYER_AGENT_WALLET_ADDRESS is None:
        raise Exception("BUYER_AGENT_WALLET_ADDRESS is not set")

    logger.info("Buyer agent started, browsing agents...")

    acp = VirtualsACP(
        acp_contract_client=ACPContractManager(
            wallet_private_key=env.WHITELISTED_WALLET_PRIVATE_KEY,
            agent_wallet_address=env.BUYER_AGENT_WALLET_ADDRESS,
            entity_id=env.BUYER_ENTITY_ID,
            config=config
        ),
        on_new_task=on_new_task,
        on_evaluate=on_evaluate
    )

    # Browse available agents based on a keyword and cluster name
    relevant_agents = acp.browse_agents(
        keyword="calm_seller",
        sort_by=[
            ACPAgentSort.SUCCESSFUL_JOB_COUNT,
        ],
        top_k=5,
        graduation_status=ACPGraduationStatus.ALL,
        online_status=ACPOnlineStatus.ALL
    )
    logger.info(f"Relevant agents: {relevant_agents}")
    
    # Pick one of the agents based on your criteria (in this example we just pick the first one)
    chosen_agent = relevant_agents[0]

    # Pick one of the service offerings based on your criteria (in this example we just pick the first one)
    chosen_job_offering = chosen_agent.jobs[0]
    
    job_id = chosen_job_offering.initiate_job({
        "fromSymbol": "USDC",
        "fromContractAddress": "0x036CbD53842c5426634e7929541eC2318f3dCF7e", # USDC token address
        "amount": 0.01,
        "toSymbol": "BMW",
        "toContractAddress": "0xbfAB80ccc15DF6fb7185f9498d6039317331846a" # BMW token address
    })
    
    logger.info(f"Job {job_id} initiated")
    logger.info("Listening for next steps...")
    # Keep the script running to listen for next steps
    threading.Event().wait()

    # # Interactive loop
    # while True:
    #     time.sleep(5)

    #     if not current_job:
    #         logger.info("No job found, waiting for new job")
    #         continue

    #     logging.info("\nAvailable actions:")
    #     for action in actions_definition:
    #         logger.info(f"{action['index']}. {action['desc']}")

    #     try:
    #         answer = input("Select an action (enter the number): ").strip()
    #         selected_index = int(answer)
    #     except ValueError:
    #         logger.warning("Invalid input, expected a number")
    #         continue

    #     action = next((action["action"] for action in actions_definition if action["index"] == selected_index), None)
    #     if action:
    #         action(current_job)
    #     else:
    #         logger.warning(f"Invalid selection {selected_index}")


if __name__ == "__main__":
    buyer()
