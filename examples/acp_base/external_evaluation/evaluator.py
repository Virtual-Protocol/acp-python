import threading

from virtuals_acp import VirtualsACP, ACPJob, ACPJobPhase
from virtuals_acp.env import EnvSettings

from dotenv import load_dotenv
load_dotenv(override=True)

def evaluator():
    env = EnvSettings()

    def on_evaluate(job: ACPJob):
        # Find the deliverable memo
        job.evaluate(True)

    # Initialize the ACP client
    VirtualsACP(
        wallet_private_key=env.WHITELISTED_WALLET_PRIVATE_KEY,
        agent_wallet_address=env.EVALUATOR_AGENT_WALLET_ADDRESS,
        on_evaluate=on_evaluate,
        entity_id=env.EVALUATOR_ENTITY_ID
    )

    print("Waiting for evaluation tasks...")
    # Keep the script running to listen for evaluation tasks
    threading.Event().wait()


if __name__ == "__main__":
    evaluator()
