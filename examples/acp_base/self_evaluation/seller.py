import time
import json

from virtuals_acp import VirtualsACP, ACPJob, ACPJobPhase
from virtuals_acp.configs import BASE_SEPOLIA_CONFIG
from virtuals_acp.env import EnvSettings

from dotenv import load_dotenv
load_dotenv(override=True)

def seller():
    env = EnvSettings()

    def on_new_task(job: ACPJob):
        # Convert job.phase to ACPJobPhase enum if it's an integer
        if job.phase == ACPJobPhase.REQUEST:
            # Check if there's a memo that indicates next phase is NEGOTIATION
            for memo in job.memos:
                if memo.next_phase == ACPJobPhase.NEGOTIATION:
                    job.respond(True)
                    break
        elif job.phase == ACPJobPhase.TRANSACTION:
            # Check if there's a memo that indicates next phase is EVALUATION
            for memo in job.memos:
                if memo.next_phase == ACPJobPhase.EVALUATION:
                    print("Delivering job", job)
                    delivery_data = {
                        "type": "url",
                        "value": "https://example.com"
                    }
                    job.deliver(json.dumps(delivery_data))
                    break

    # Initialize the ACP client
    acp_client = VirtualsACP(
        wallet_private_key=env.SELLER_WALLET_PRIVATE_KEY,
        agent_wallet_address=env.SELLER_AGENT_WALLET_ADDRESS,
        config=BASE_SEPOLIA_CONFIG,
        on_new_task=on_new_task
    )
    
    # Keep the script running to listen for new tasks
    while True:
        print("Waiting for new task...")
        time.sleep(30)

if __name__ == "__main__":
    seller()
