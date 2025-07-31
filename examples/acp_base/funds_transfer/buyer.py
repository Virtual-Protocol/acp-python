import threading
import time
from datetime import datetime, timedelta
from typing import Optional

from virtuals_acp import ACPMemo, MemoType
from virtuals_acp.client import VirtualsACP
from virtuals_acp.job import ACPJob
from virtuals_acp.models import ACPJobPhase, OpenPositionPayload, TPSLConfig, ClosePositionPayload, PayloadType
from virtuals_acp.env import EnvSettings

from dotenv import load_dotenv

load_dotenv(override=True)


def buyer():
    env = EnvSettings()

    def on_new_task(job: ACPJob, memo_to_sign: Optional[ACPMemo]):
        if (
                job.phase == ACPJobPhase.NEGOTIATION
                and memo_to_sign is not None
                and memo_to_sign.next_phase == ACPJobPhase.TRANSACTION
        ):
            print("Paying job", job.id)
            job.pay(job.price)
            print(f"Job {job.id} paid")

            # Buyer starts opening positions
            print(f"Opening position {job}")
            job.open_position(
                [
                    OpenPositionPayload(
                        symbol="BTC",
                        amount=0.001, # amount in $VIRTUAL
                        tp=TPSLConfig(percentage=5),
                        sl=TPSLConfig(percentage=2),
                    ),
                    OpenPositionPayload(
                        symbol="ETH",
                        amount=0.002, # amount in $VIRTUAL
                        tp=TPSLConfig(percentage=5),
                        sl=TPSLConfig(percentage=2),
                    ),
                ],
                0.001 # fee amount in $VIRTUAL
            )
            print(f"Job {job.id} 2 positions opened")

            # Buyer open 1 more position
            time.sleep(10)
            job.open_position(
                [
                    OpenPositionPayload(
                        symbol="VIRTUAL",
                        amount=0.003, # amount in $VIRTUAL
                        tp=TPSLConfig(percentage=33000),
                        sl=TPSLConfig(percentage=2),
                    )
                ],
                0.0001
            )
            print(f"Job {job.id} 1 more position opened")

            # Buyer starts closing positions on initiative, before TP/SL hit
            time.sleep(10)
            job.close_partial_position(
                ClosePositionPayload(
                    position_id=0,
                    amount=1.01
                )
            )
            print(f"Job {job.id} BTC position closed")

            # Buyer close job upon all positions return
            time.sleep(10)
            job.close_job()
            print(f"Start closing Job {job.id}")
            return

        # receiving funds transfer from provider for the fulfilled/unfulfilled positions
        elif (
                job.phase == ACPJobPhase.TRANSACTION
                and memo_to_sign is not None
                and memo_to_sign.next_phase == ACPJobPhase.TRANSACTION
                and memo_to_sign.type == MemoType.PAYABLE_TRANSFER
        ):
            print(f"Accepting funds transfer {job} with memo {memo_to_sign.id}")
            if memo_to_sign.payload_type == PayloadType.UNFULFILLED_POSITION:
                job.respond_unfulfilled_position(
                    memo_to_sign.id,
                    True,
                    "Accepting funds transfer for the unfulfilled positions"
                )
                print(f"Job {job.id} funds transfer for the unfulfilled position accepted")
                return
            else:
                job.respond_position_fulfilled(
                    memo_to_sign.id,
                    True,
                    "Accepting funds transfer for the fulfilled positions"
                )
                print(f"Job {job.id} funds transfer for the fulfilled position accepted")

        # receiving funds transfer from provider at closing of the job
        elif (
                job.phase == ACPJobPhase.TRANSACTION
                and memo_to_sign is not None
                and memo_to_sign.next_phase == ACPJobPhase.EVALUATION # if phase is evaluation, it means the job is closing
                and memo_to_sign.type == MemoType.PAYABLE_TRANSFER
        ):
            print(f"Accepting funds transfer {job} with memo {memo_to_sign.id}")
            job.confirm_job_closure(memo_to_sign.id, True)
            print(f"Job {job.id} closed and funds transfer accepted")

        elif job.phase == ACPJobPhase.COMPLETED:
            print("Job completed", job)
            return

        elif job.phase == ACPJobPhase.REJECTED:
            print("Job rejected", job)
            return

    def on_evaluate(job: ACPJob):
        print("Evaluation function called", job)
        job.evaluate(True)

    if env.WHITELISTED_WALLET_PRIVATE_KEY is None:
        raise ValueError("WHITELISTED_WALLET_PRIVATE_KEY is not set")
    if env.BUYER_AGENT_WALLET_ADDRESS is None:
        raise ValueError("BUYER_AGENT_WALLET_ADDRESS is not set")
    if env.BUYER_ENTITY_ID is None:
        raise ValueError("BUYER_ENTITY_ID is not set")

    acp = VirtualsACP(
        wallet_private_key=env.WHITELISTED_WALLET_PRIVATE_KEY,
        agent_wallet_address=env.BUYER_AGENT_WALLET_ADDRESS,
        on_new_task=on_new_task,
        on_evaluate=on_evaluate,
        entity_id=env.BUYER_ENTITY_ID,
    )

    # Browse available agents based on a keyword and cluster name
    relevant_agents = acp.browse_agents(
        keyword="<your_filter_agent_keyword>",
        cluster="<your_cluster_name>",
        graduated=True # False for sandbox agents; True for graduated agents
    )
    print(f"Relevant agents: {relevant_agents}")

    # Pick one of the agents based on your criteria (in this example we just pick the first one)
    chosen_agent = relevant_agents[0]

    # Pick one of the service offerings based on your criteria (in this example we just pick the first one)
    chosen_job_offering = chosen_agent.offerings[0]
    job_id = chosen_job_offering.initiate_job(
        service_requirement="<your_service_requirement>",
        evaluator_address=env.BUYER_AGENT_WALLET_ADDRESS,
        expired_at=datetime.now() + timedelta(minutes=8)
    )

    print(f"Job {job_id} initiated")

    print("Listening for next steps...")
    # Keep the script running to listen for next steps
    threading.Event().wait()


if __name__ == "__main__":
    buyer()
