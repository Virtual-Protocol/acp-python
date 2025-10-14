import threading
import logging
from dotenv import load_dotenv

from virtuals_acp.job import ACPJob
from virtuals_acp.client import VirtualsACP
from virtuals_acp.env import EnvSettings
from virtuals_acp.contract_clients.contract_client_v2 import ACPContractClientV2
from virtuals_acp.configs.configs import BASE_SEPOLIA_CONFIG_V2

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("EvaluatorAgent")

load_dotenv(override=True)

def evaluator():
    env = EnvSettings()

    def on_evaluate(job: ACPJob):
        logger.info(f"[on_evaluate] Evaluation function called for job {job.id}")
        logger.info(f"[on_evaluate] Memos: {job.memos}")

        try:
            job.evaluate(True, "Externally evaluated and approved")
            logger.info(f"[on_evaluate] Job {job.id} evaluated successfully")
        except Exception as e:
            logger.error(f"[on_evaluate] Job {job.id} evaluation failed: {e}")

    acp_client = VirtualsACP(
        acp_contract_clients=ACPContractClientV2(
            wallet_private_key=env.WHITELISTED_WALLET_PRIVATE_KEY,
            agent_wallet_address=env.EVALUATOR_AGENT_WALLET_ADDRESS,
            entity_id=env.EVALUATOR_ENTITY_ID,
            config=BASE_SEPOLIA_CONFIG_V2
        ),
        on_evaluate=on_evaluate,
    )

    logger.info("[Evaluator] Listening for new jobs...")
    # Keep the script running to listen for evaluation tasks
    threading.Event().wait()


if __name__ == "__main__":
    evaluator()
