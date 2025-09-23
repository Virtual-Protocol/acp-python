import threading
import time
import logging
from typing import Optional, Dict, Any

from dotenv import load_dotenv
from virtuals_acp import ACPMemo
from virtuals_acp.configs import BASE_SEPOLIA_CONFIG
from virtuals_acp.client import VirtualsACP
from virtuals_acp.env import EnvSettings
from virtuals_acp.job import ACPJob
from virtuals_acp.models import (
    ACPAgentSort,
    ACPJobPhase,
    ACPGraduationStatus,
    ACPOnlineStatus,
    PayloadType,
)
from virtuals_acp.contract_manager import ACPContractManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("BuyerAgent")

load_dotenv(override=True)
config = BASE_SEPOLIA_CONFIG

# Python dict equivalent to SERVICE_REQUIREMENTS_JOB_TYPE_MAPPING
SERVICE_REQUIREMENTS_JOB_TYPE_MAPPING: Dict[str, Any] = {
    "open_position": {
        "symbol": "BTC",
        "amount": 0.001,
        "tp": {"percentage": 5},
        "sl": {"percentage": 2},
        "direction": "long",
    },
    "swap_token": {
        "fromSymbol": "BMW",
        "fromContractAddress": "0xbfAB80ccc15DF6fb7185f9498d6039317331846a",
        "amount": 0.01,
        "toSymbol": "USDC",
    },
    "close_partial_position": {"positionId": 0, "amount": 1},
    "close_position": {"positionId": 0},
    "close_job": "Close job and withdraw all",
}


def main():
    env = EnvSettings()

    current_job = None

    def on_new_task(job: ACPJob, memo_to_sign: Optional[ACPMemo] = None):
        nonlocal current_job
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

        if memo_to_sign.payload_type == PayloadType.CLOSE_JOB_AND_WITHDRAW:
            job.confirm_job_closure(memo_to_sign.id, True)
            logger.info("Closed job")

        elif memo_to_sign.payload_type == PayloadType.RESPONSE_SWAP_TOKEN:
            memo_to_sign.sign(True, "accepts swap token")
            logger.info("Swapped token")

        elif memo_to_sign.payload_type == PayloadType.CLOSE_POSITION:
            job.confirm_close_position(memo_to_sign.id, True)
            logger.info("Closed position")

        else:
            logger.warning(f"Unhandled payload type {memo_to_sign.payload_type}")
    
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
    
    chosen_agent = relevant_agents[0]
    offerings = chosen_agent.jobs

    actions_definition = [
        {
            "index": idx + 1,
            "desc": offering.name,
            "action": lambda off=offering: off.initiate_job(
                SERVICE_REQUIREMENTS_JOB_TYPE_MAPPING.get(offering.name, {})
            ),
        }
        for idx, offering in enumerate(offerings)
    ]
    
    while True:
        time.sleep(5)

        if current_job:
            continue  # skip interactive loop if a job is already active

        print("\nAvailable actions:")
        for action in actions_definition:
            print(f"{action['index']}. {action['desc']}")

        try:
            selected_index = int(input("Select an action: ").strip())
        except ValueError:
            print("Invalid input, expected a number")
            continue

        selected_action = next((a for a in actions_definition if a["index"] == selected_index), None)
        if selected_action:
            job_id = selected_action["action"]()
            logger.info(f"Job {job_id} initiated")
        else:
            print("Invalid selection")


if __name__ == "__main__":
    main()
