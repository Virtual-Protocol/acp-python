import threading
import time
from typing import Optional

from virtuals_acp import VirtualsACP, ACPJob, ACPJobPhase, ACPMemo, MemoType
from virtuals_acp.env import EnvSettings

from dotenv import load_dotenv

from virtuals_acp.models import FundResponsePayload, GenericPayload, PayloadType, PositionFulfilledPayload, \
    UnfulfilledPositionPayload

load_dotenv(override=True)

def seller():
    # for simulation only
    position_fulfilled_count = 0
    env = EnvSettings()

    def on_new_task(job: ACPJob, memo_to_sign: Optional[ACPMemo]):
        nonlocal position_fulfilled_count

        # Convert job.phase to ACPJobPhase enum if it's an integer
        # Check if the memo-to-sign's next phase is NEGOTIATION
        if (
                job.phase == ACPJobPhase.REQUEST
                and memo_to_sign is not None
                and memo_to_sign.next_phase == ACPJobPhase.NEGOTIATION
        ):
            job.respond(
                True,
                GenericPayload(
                    type=PayloadType.FUND_RESPONSE,
                    data=FundResponsePayload(
                        reporting_api_endpoint="https://example-reporting-api-endpoint/positions"
                    )
                )
            )
            print(f"Job {job.id} responded")
            return

        elif(
                job.phase == ACPJobPhase.TRANSACTION
                and memo_to_sign is not None
                and memo_to_sign.next_phase == ACPJobPhase.TRANSACTION
                and memo_to_sign.type != MemoType.MESSAGE
        ):
            # open positions for client
            if memo_to_sign.type == MemoType.PAYABLE_TRANSFER:
                print(f"Accepting positions opening {job} with memo {memo_to_sign.id}")
                job.respond_open_position(
                    memo_to_sign.id,
                    True,
                    "accepts position opening"
                )
                print(f"Job {job.id} position opening accepted")

                if position_fulfilled_count == 0:
                    position_fulfilled_count += 1
                    time.sleep(10)
                    job.position_fulfilled(
                        PositionFulfilledPayload(
                            symbol="VIRTUAL",
                            amount=99,
                            contract_address="0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b",
                            type="TP",
                            pnl=96,
                            entry_price=1.8,
                            exit_price=59.4,
                        )
                    )
                    print(f"Job {job.id} VIRTUAL TP fulfilled")

                    time.sleep(10)
                    job.unfulfilled_position(
                        UnfulfilledPositionPayload(
                            symbol="ETH",
                            amount=1.5,
                            contract_address="0xd449119E89773693D573ED217981659028C7662E",
                            type="PARTIAL"
                        )
                    )
                    print(f"Job {job.id} ETH position partially fulfilled, returning the remainders")

                return

            # closing positions for client
            elif memo_to_sign.type == MemoType.PAYABLE_REQUEST:
                print(f"Accepting positions closing {job} with memo {memo_to_sign.id}")
                job.respond_close_partial_position(
                    memo_to_sign.id,
                    True,
                    "accepts position closing"
                )
                print(f"Job {job.id} position closing accepted")
                return

            return

        # closing the job
        elif (
                job.phase == ACPJobPhase.TRANSACTION
                and memo_to_sign is not None
                and memo_to_sign.type == MemoType.MESSAGE
        ):
            if len(job.memos) > 3:
                print(f"Closing {job} with memo {memo_to_sign.id}")
                job.respond_close_job(
                    memo_to_sign.id,
                    True,
                    [
                        PositionFulfilledPayload(
                            symbol="ETH",
                            amount=0.5,
                            contract_address="0xd449119E89773693D573ED217981659028C7662E",
                            type="CLOSE",
                            pnl=0,
                            entry_price=3000,
                            exit_price=3000
                        )
                    ]
                )
                print(f"Job {job.id} closed")
                return

    if env.WHITELISTED_WALLET_PRIVATE_KEY is None:
        raise ValueError("WHITELISTED_WALLET_PRIVATE_KEY is not set")
    if env.SELLER_ENTITY_ID is None:
        raise ValueError("SELLER_ENTITY_ID is not set")

    # Initialize the ACP client
    VirtualsACP(
        wallet_private_key=env.WHITELISTED_WALLET_PRIVATE_KEY,
        agent_wallet_address=env.SELLER_AGENT_WALLET_ADDRESS,
        on_new_task=on_new_task,
        entity_id=env.SELLER_ENTITY_ID
    )

    print("Waiting for new task...")
    # Keep the script running to listen for new tasks
    threading.Event().wait()


if __name__ == "__main__":
    seller()
