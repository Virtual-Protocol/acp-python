import threading
import time
import logging
from typing import Optional, Dict, Any

from dotenv import load_dotenv
from virtuals_acp import ACPMemo, MemoType
from virtuals_acp.configs import BASE_SEPOLIA_CONFIG
from virtuals_acp.client import VirtualsACP
from virtuals_acp.env import EnvSettings
from virtuals_acp.job import ACPJob
from virtuals_acp.models import (
    ACPAgentSort,
    ACPJobPhase,
    ACPGraduationStatus,
    ACPOnlineStatus
)
from virtuals_acp.contract_manager import ACPContractManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("Prediction_Market_Buyer_Agent")

load_dotenv(override=True)
config = BASE_SEPOLIA_CONFIG

# Python dict equivalent to SERVICE_REQUIREMENTS_JOB_TYPE_MAPPING
SERVICE_REQUIREMENTS_JOB_TYPE_MAPPING: Dict[str, Any] = {
    "create_market": {
        "question": "Will ETH close above $3000 on Dec 31, 2025?",
        "outcomes": ["Yes", "No"],  # array that requires at least 2 outcomes
        "endTime": "Dec 31, 2025, 11:59 PM UTC",
        "liquidity": 0.001,  # Initial liquidity (USDC)
    },
    "place_bet": {
        "marketId": "0xfc274053",
        "outcome": "Yes",
        "token": "USDC",
        "amount": 0.001,
    },
    "close_bet": {
        "marketId": "0xfc274053",
    },
}


def main():
    env = EnvSettings()
    current_job_id: Optional[int] = None

    def on_new_task(job: ACPJob, memo_to_sign: Optional[ACPMemo] = None):
        nonlocal current_job_id

        job_id = job.id
        job_phase = job.phase

        if memo_to_sign is None:
            logger.info(f"[on_new_task] No memo to sign | job_id={job_id}")
            if job.phase == ACPJobPhase.REJECTED:
                current_job_id = None
            return

        memo_id = memo_to_sign.id

        logger.info(f"[on_new_task] New job received | job_id={job_id}, memo_id={memo_id}, job_phase={job_phase}")

        if job.phase == ACPJobPhase.NEGOTIATION and memo_to_sign.next_phase == ACPJobPhase.TRANSACTION:
            logger.info(f"[on_new_task] Paying job {job.id}")
            job.pay_and_accept_requirement("I accept the job requirements")
            logger.info(f"[on_new_task] Job {job_id} paid")

        elif job.phase == ACPJobPhase.TRANSACTION:
            if memo_to_sign.next_phase == ACPJobPhase.REJECTED:
                logger.info(f"[on_new_task] Signing job rejection memo | job_id={job_id}, memo_id={memo_id}")
                memo_to_sign.sign(True, "Accepted job rejection")
                logger.info(f"[on_new_task] Rejection memo signed {job.id}")
                current_job_id = None

            elif memo_to_sign.next_phase == ACPJobPhase.TRANSACTION and memo_to_sign.type == MemoType.PAYABLE_TRANSFER_ESCROW:
                logger.info(f"[on_new_task] Accepting funds transfer | job_id={job_id}, memo_id={memo_id}")
                memo_to_sign.sign(True, "Accepted funds transfer")
                logger.info(f"[on_new_task] Funds transfer memo signed {job.id}")

    def on_evaluate(job: ACPJob):
        nonlocal current_job_id
        logger.info(
            f"[on_evaluate] Evaluation function called | job_id={job.id}, requirement={job.requirement}, deliverable={job.deliverable}"
        )
        job.evaluate(True, "job auto-evaluated")
        logger.info(f"[on_evaluate] Job {job.id} evaluated")
        current_job_id = None

    acp_client = VirtualsACP(
        acp_contract_client=ACPContractManager(
            wallet_private_key=env.WHITELISTED_WALLET_PRIVATE_KEY,
            agent_wallet_address=env.BUYER_AGENT_WALLET_ADDRESS,
            entity_id=env.BUYER_ENTITY_ID,
            config=config
        ),
        on_new_task=on_new_task,
        on_evaluate=on_evaluate
    )

    relevant_agents = acp_client.browse_agents(
        keyword="<your-filter-agent-keyword>",
        sort_by=[ACPAgentSort.SUCCESSFUL_JOB_COUNT],
        top_k=5,
        graduation_status=ACPGraduationStatus.ALL,
        online_status=ACPOnlineStatus.ALL
    )
    logger.info(f"Relevant agents: {relevant_agents}")

    chosen_agent = relevant_agents[0]
    job_offerings = chosen_agent.job_offerings
    logger.info(job_offerings)

    actions_definition = [
        {
            "index": idx + 1,
            "desc": offering.name,
            "action": lambda off=offering: off.initiate_job(
                SERVICE_REQUIREMENTS_JOB_TYPE_MAPPING[off.name]
            ),
        }
        for idx, offering in enumerate(job_offerings or [])
    ]

    while True:
        time.sleep(5)

        if current_job_id is not None:
            # No job found, waiting for new job
            continue

        logger.info("\nAvailable actions:")
        for action in actions_definition:
            logger.info(f"{action['index']}. {action['desc']}")

        try:
            answer = input("\nSelect an action (enter the number): ")
            logger.info("Initiating job...")
            selected_index = int(answer)
        except ValueError:
            logger.info("Invalid input. Please enter a number.")
            continue

        selected_action = next(
            (a for a in actions_definition if a["index"] == selected_index),
            None
        )

        if selected_action:
            current_job_id = selected_action["action"]()
            logger.info(f"Job initiated {current_job_id}")
        else:
            logger.info("Invalid selection. Please try again.")


if __name__ == "__main__":
    main()
