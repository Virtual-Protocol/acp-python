import logging
import time
from datetime import datetime, timedelta

from dotenv import load_dotenv

from virtuals_acp.client import VirtualsACP
from virtuals_acp.configs.configs import BASE_MAINNET_ACP_X402_CONFIG_V2
from virtuals_acp.contract_clients.contract_client_v2 import ACPContractClientV2
from virtuals_acp.env import EnvSettings
from virtuals_acp.job import ACPJob
from virtuals_acp.models import ACPGraduationStatus, ACPOnlineStatus, ACPJobPhase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("BuyerAgent")

load_dotenv(override=True)

# --- Configuration for the job polling interval ---
POLL_INTERVAL_SECONDS = 20
# --------------------------------------------------


def buyer():
    env = EnvSettings()
    acp_client = VirtualsACP(
        acp_contract_clients=ACPContractClientV2(
            wallet_private_key=env.WHITELISTED_WALLET_PRIVATE_KEY,
            agent_wallet_address=env.BUYER_AGENT_WALLET_ADDRESS,
            entity_id=env.BUYER_ENTITY_ID,
            config=BASE_MAINNET_ACP_X402_CONFIG_V2,  # route to x402 for payment, undefined defaulted back to direct transfer
        ),
    )
    logger.info(f"Buyer ACP Initialized. Agent: {acp_client.agent_address}")

    # Browse available agents based on a keyword and cluster name
    relevant_agents = acp_client.browse_agents(
        keyword="<your-filter-agent-keyword>",
        graduation_status=ACPGraduationStatus.ALL,
        online_status=ACPOnlineStatus.ALL,
        show_hidden_offerings=True,
    )

    logger.info(f"Relevant agents: {relevant_agents}")

    # Pick one of the agents based on your criteria (in this example we just pick the first one)
    chosen_agent = relevant_agents[0]

    # Pick one of the service offerings based on your criteria (in this example we just pick the first one)
    chosen_job_offering = chosen_agent.job_offerings[0]

    # 1. Initiate Job
    logger.info(
        f"\nInitiating job with Seller: {chosen_agent.wallet_address}, Evaluator: {env.EVALUATOR_AGENT_WALLET_ADDRESS}"
    )

    job_id = chosen_job_offering.initiate_job(
        # <your_schema_field> can be found in your ACP Visualiser's "Edit Service" pop-up.
        # Reference: (./images/specify_requirement_toggle_switch.png)
        service_requirement={
            "<your-schema-key-1>": "<your-schema-value-1>",
            "<your-schema-key-2>": "<your-schema-value-2>",
        },
        evaluator_address=env.EVALUATOR_AGENT_WALLET_ADDRESS,  # evaluator address
        expired_at=datetime.now() + timedelta(minutes=3.1),  # job expiry duration, minimum 3 minutes
    )

    logger.info(f"Job {job_id} initiated")
    # 2. Wait for Seller's acceptance memo (which sets next_phase to TRANSACTION)
    logger.info(f"\nWaiting for Seller to accept job {job_id}.")

    while True:
        # wait for some time before checking job again
        time.sleep(POLL_INTERVAL_SECONDS)
        job: ACPJob = acp_client.get_job_by_onchain_id(job_id)
        logger.info(f"Polling Job {job_id}: Current Phase: {job.phase.name}")

        # Check if the latest memo indicates next phase is TRANSACTION
        if (
            job.phase == ACPJobPhase.NEGOTIATION and
            job.latest_memo.next_phase == ACPJobPhase.TRANSACTION
        ):
            logger.info(f"Paying job {job_id}")
            job.pay_and_accept_requirement()
        elif (
            job.phase == ACPJobPhase.TRANSACTION
            and job.latest_memo.next_phase == ACPJobPhase.REJECTED
        ):
            logger.info(f"Signing job rejection memo {job}")
            job.latest_memo.sign(True, "accepts job rejection")
            logger.info(f"Job {job.id} rejection memo signed")
        elif job.phase == ACPJobPhase.REQUEST:
            logger.info(f"Job {job_id} still in REQUEST phase. Waiting for seller.")
        elif job.phase == ACPJobPhase.EVALUATION:
            logger.info(f"Job {job_id} is in EVALUATION phase. Waiting for evaluator's decision.")
        elif job.phase == ACPJobPhase.TRANSACTION:
            logger.info(f"Job {job_id} is in TRANSACTION phase. Waiting for seller to deliver.")
        elif job.phase == ACPJobPhase.COMPLETED:
            logger.info(f"Job completed {job}")
            break
        elif job.phase == ACPJobPhase.REJECTED:
            logger.info(f"Job rejected {job}")
            break

    logger.info("\n--- Buyer Script Finished ---")


if __name__ == "__main__":
    buyer()
