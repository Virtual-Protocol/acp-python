import time
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv

from virtuals_acp.memo import ACPMemo, MemoType
from virtuals_acp.client import VirtualsACP
from virtuals_acp.env import EnvSettings
from virtuals_acp.job import ACPJob
from virtuals_acp.models import (
    ACPAgentSort,
    ACPJobPhase,
    ACPGraduationStatus,
    ACPOnlineStatus,
)
from virtuals_acp.contract_clients.contract_client_v2 import ACPContractClientV2


# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("PredictionMarketBuyerAgent")

load_dotenv(override=True)

SERVICE_REQUIREMENTS_JOB_TYPE_MAPPING: Dict[str, Any] = {
    "create_market": {
        "question": "Will ETH close above $3000 on Dec 31, 2025?",
        "outcomes": ["Yes", "No"],
        "endTime": "Dec 31, 2025, 11:59 PM UTC",
        "liquidity": 0.005,
    },
    "place_bet": {
        "marketId": "0xfc274053",
        "outcome": "Yes",
        "token": "USDC",
        "amount": 0.003,
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
        job_id, job_phase = job.id, job.phase

        if memo_to_sign is None:
            if job_phase in [ACPJobPhase.REJECTED, ACPJobPhase.COMPLETED]:
                current_job_id = None
                msg = (
                        f"[on_new_task] Job {job_id} {job_phase}. "
                        + (
                            f"Deliverable received: {job.deliverable}"
                            if job_phase == ACPJobPhase.COMPLETED
                            else f"Rejection reason: {job.rejection_reason}"
                        )
                )
                logger.info(msg)
                return
            logger.info(f"[on_new_task] No memo to sign | job_id={job_id}")
            return

        memo_id = memo_to_sign.id
        logger.info(
            f"[on_new_task] New job received | job_id={job_id}, memo_id={memo_id}, job_phase={job_phase}"
        )

        if (
                job_phase == ACPJobPhase.NEGOTIATION
                and memo_to_sign.next_phase == ACPJobPhase.TRANSACTION
        ):
            logger.info(f"[on_new_task] Paying for job {job_id}")
            job.pay_and_accept_requirement("Accepts prediction market requirement")
            current_job_id = job_id
            logger.info(f"[on_new_task] Job {job_id} paid")

        elif job_phase == ACPJobPhase.TRANSACTION:
            if memo_to_sign.next_phase == ACPJobPhase.REJECTED:
                logger.info(
                    f"[on_new_task] Signing job rejection memo | job_id={job_id}, memo_id={memo_id}"
                )
                memo_to_sign.sign(True, "Accepts job rejection")
                logger.info(f"[on_new_task] Rejection memo signed | job_id={job_id}")
                current_job_id = None

            elif (
                    memo_to_sign.next_phase == ACPJobPhase.TRANSACTION
                    and memo_to_sign.type == MemoType.PAYABLE_TRANSFER_ESCROW
            ):
                logger.info(
                    f"[on_new_task] Accepting funds transfer | job_id={job_id}, memo_id={memo_id}"
                )
                memo_to_sign.sign(True, "Accepts funds transfer")
                logger.info(f"[on_new_task] Funds transfer memo signed | job_id={job_id}")

        elif memo_to_sign.type in [
            MemoType.NOTIFICATION,
            MemoType.PAYABLE_NOTIFICATION,
        ]:
            logger.info(
                f"[on_new_task] Job {job_id} received notification: {memo_to_sign.content}"
            )
            memo_to_sign.sign(True, "Acknowledged on job update notification")

    acp_client = VirtualsACP(
        acp_contract_clients=ACPContractClientV2(
            wallet_private_key=env.WHITELISTED_WALLET_PRIVATE_KEY,
            agent_wallet_address=env.BUYER_AGENT_WALLET_ADDRESS,
            entity_id=env.BUYER_ENTITY_ID,
        ),
        on_new_task=on_new_task,
    )

    agents = acp_client.browse_agents(
        keyword="<your-filter-agent-keyword>",
        sort_by=[ACPAgentSort.SUCCESSFUL_JOB_COUNT],
        top_k=5,
        graduation_status=ACPGraduationStatus.ALL,
        online_status=ACPOnlineStatus.ALL,
    )

    logger.info(f"Relevant agents: {agents}")
    chosen_agent = agents[0]
    job_offerings = chosen_agent.job_offerings
    logger.info(f"Available job offerings: {job_offerings}")

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
        time.sleep(1)

        if current_job_id:
            # Waiting for current job to complete
            continue

        print("\nAvailable actions:")
        for action in actions_definition:
            print(f"{action['index']}. {action['desc']}")

        try:
            answer = input("\nSelect an action (enter the number): ").strip()
            selected_index = int(answer)
        except ValueError:
            logger.info("Invalid input. Please enter a number.")
            continue

        selected_action = next(
            (a for a in actions_definition if a["index"] == selected_index), None
        )

        if selected_action:
            logger.info("Initiating job...")
            current_job_id = selected_action["action"]()
            logger.info(f"Job {current_job_id} initiated")
        else:
            logger.info("Invalid selection. Please try again.")


if __name__ == "__main__":
    main()
