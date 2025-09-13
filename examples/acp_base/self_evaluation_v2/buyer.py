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
            job.pay(0)
            return
        
        current_job = job
        
        if job.phase != ACPJobPhase.TRANSACTION:
            logger.info(f"Job is not in transaction phase")
            return 
        
        if not memo_to_sign:
            logger.info(f"No memo to sign")
            return
        
        # Handle memo
        if memo_to_sign.payload_type == PayloadType.CLOSE_JOB_AND_WITHDRAW:
            job.confirm_job_closure(memo_to_sign.id, True)
            logger.info(f"Closed job {job.id}")

        elif memo_to_sign.payload_type == PayloadType.RESPONSE_SWAP_TOKEN:
            memo_to_sign.sign(True, "accepts swap token")
            logger.info(f"Swapped token for job {job.id}")

        elif memo_to_sign.payload_type == PayloadType.CLOSE_POSITION:
            job.confirm_close_position(memo_to_sign.id, True)
            logger.info(f"Closed position for job {job.id}")

        else:
            logger.warning(
                "Unhandled payload type %s for job %s",
                memo_to_sign.payload_type,
                job.id,
            )
    
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
        wallet_private_key=env.WHITELISTED_WALLET_PRIVATE_KEY,
        agent_wallet_address=env.BUYER_AGENT_WALLET_ADDRESS,
        on_new_task=on_new_task,
        on_evaluate=on_evaluate,
        entity_id=env.BUYER_ENTITY_ID
    )

    # Browse available agents based on a keyword and cluster name
    relevant_agents = acp.browse_agents(
        keyword="<your_filter_agent_keyword>",
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
    
    logger.info(f"Job {job_id} initiated")
    logger.info("Listening for next steps...")
    # Keep the script running to listen for next steps
    threading.Event().wait()

    # Define your actions (sync or async depending on your SDK)
    def open_position(current_job):
        result = current_job.open_position(
            [
                {"symbol": "BTC", "amount": 0.001, "tp": {"percentage": 5}, "sl": {"percentage": 2}},
                {"symbol": "ETH", "amount": 0.002, "tp": {"percentage": 10}, "sl": {"percentage": 5}},
            ],
            0.001,  # fee in $VIRTUAL
            datetime.now() + timedelta(minutes=3),
        )
        logger.info(f"Opening position result: {result}")

    def swap_token(current_job):
        result = current_job.swap_token(
            {
                "fromSymbol": "BMW",
                "fromContractAddress": "0xbfAB80ccc15DF6fb7185f9498d6039317331846a",
                "amount": 0.01,
                "toSymbol": "USDC",
            },
            18,   # decimals from BMW
            0.001 # fee in $USDC
        )
        logger.info(f"Swapping token result: {result}")

    def close_partial_position(current_job):
        result = current_job.close_partial_position({"positionId": 0, "amount": 1})
        print("Closing partial position result", result)

    def close_position(current_job):
        result = current_job.request_close_position({"positionId": 0})
        logger.info(f"Closing position result: {result}")

    def close_job(current_job):
        result = current_job.close_job()
        logger.info(f"Closing job result: {result}")

    actions_definition = [
        {"index": 1, "desc": "Open position", "action": open_position},
        {"index": 2, "desc": "Swap token", "action": swap_token},
        {"index": 3, "desc": "Close partial position", "action": close_partial_position},
        {"index": 4, "desc": "Close position", "action": close_position},
        {"index": 5, "desc": "Close job", "action": close_job},
    ]

    # Interactive loop
    while True:
        time.sleep(5)

        if not current_job:
            logger.info("No job found, waiting for new job")
            continue

        logging.info("\nAvailable actions:")
        for action in actions_definition:
            logger.info(f"{action['index']}. {action['desc']}")

        try:
            answer = input("Select an action (enter the number): ").strip()
            selected_index = int(answer)
        except ValueError:
            logger.warning("Invalid input, expected a number")
            continue

        action = next((action["action"] for action in actions_definition if action["index"] == selected_index), None)
        if action:
            action(current_job)
        else:
            logger.warning(f"Invalid selection {selected_index}")


if __name__ == "__main__":
    buyer()
