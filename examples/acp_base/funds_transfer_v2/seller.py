import threading
import logging
from typing import Optional
from enum import Enum
from dataclasses import dataclass, field

from dotenv import load_dotenv

from virtuals_acp import ACPMemo
from virtuals_acp.configs import BASE_SEPOLIA_CONFIG
from virtuals_acp.client import VirtualsACP
from virtuals_acp.env import EnvSettings
from virtuals_acp.job import ACPJob
from virtuals_acp.models import ACPJobPhase, MemoType
from virtuals_acp.contract_manager import ACPContractManager
from virtuals_acp.fare import FareAmount
from enum import Enum
from typing import Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("SellerAgent")

load_dotenv(override=True)

config = BASE_SEPOLIA_CONFIG

class JobName(str, Enum):
    OPEN_POSITION = "open_position"
    CLOSE_POSITION = "close_position"
    SWAP_TOKEN = "swap_token"
    WITHDRAW = "withdraw"

@dataclass
class Position:
    symbol: str
    amount: int

@dataclass
class ClientWallet:
    client_address: str        # Address type → use str unless you have a custom Address type
    assets: List["FareAmount"] = field(default_factory=list)
    positions: List[Position] = field(default_factory=list)

clients: Dict[str, ClientWallet] = {}


def seller():
    env = EnvSettings()

    def on_new_task(job: ACPJob, memo_to_sign: Optional[ACPMemo] = None):
        if not memo_to_sign:
            logger.error("Memo to sign not found %s", memo_to_sign)
            return

        job_name = job.name
        if not job_name:
            logger.error("Job name not found %s", job)
            return

        # if job_name == job_name.OPEN_POSITION.value:
        #     memo_to_sign.sign(True, "accepts open position")
        #     return job.create_requirement_payable_memo(
        #         "Send me 1 USDC to open position",
        #         MemoType.PAYABLE_REQUEST,
        #         FareAmount(1, config.base_fare),
        #         job.provider_address,
        #     )

        # elif job_name == job_name.CLOSE_POSITION.value:
        #     memo_to_sign.sign(True, "accepts close position")
        #     return job.create_requirement_memo("Closing a random position")

        if job_name == JobName.SWAP_TOKEN.value:
            memo_to_sign.sign(True, "accepts swap token")
            return job.create_requirement_payable_memo(
                "Send me 1 USDC to swap to 1 USD",
                MemoType.PAYABLE_REQUEST,
                FareAmount(1, config.base_fare),
                job.provider_address,
            )

        # elif job_name == job_name.WITHDRAW.value:
        #     memo_to_sign.sign(True, "accepts withdraw")
        #     return job.create_requirement_payable_memo(
        #         "Withdrawing a random amount",
        #         MemoType.PAYABLE_TRANSFER_ESCROW,
        #         FareAmount(1, config.base_fare),
        #         job.provider_address,
        #     )

        logger.error("Job name not supported %s", job_name)
        return


    def handle_task_transaction(job: ACPJob, memo_to_sign: Optional[ACPMemo] = None):
        task = memo_to_sign.payload_type if memo_to_sign else None
        if not task:
            logger.error(f"Task not found, payloadType={memo_to_sign.payload_type}")
            return None

        wallet = clients[job.client_address]

        if task == JobName.OPEN_POSITION:
            wallet.positions.append(Position("USDC", 1))
            job.deliver({"type": "message", "value": "Opened position with hash 0x1234567890"})
            logger.info(f"Opened position for client {job.client_address}")
            return

        if task == JobName.CLOSE_POSITION:
            wallet.positions = [p for p in wallet.positions if p.symbol != "USDC"]
            job.deliver({"type": "message", "value": "Closed position with hash 0x1234567890"})
            logger.info(f"Closed position for client {job.client_address}")
            return

        if task == JobName.SWAP_TOKEN:
            wallet.assets.append(FareAmount(1, config.base_fare))
            job.deliver({"type": "message", "value": "Swapped token with hash 0x1234567890"})
            logger.info(f"Swapped token for client {job.client_address}")
            return

        if task == JobName.WITHDRAW:
            job.deliver({"type": "message", "value": "Withdrawn amount with hash 0x1234567890"})
            logger.info(f"Withdrawn for client {job.client_address}")
            return

        logger.error(f"Task not supported: {task}")
        return
    
    if env.WHITELISTED_WALLET_PRIVATE_KEY is None:
        raise Exception("WHITELISTED_WALLET_PRIVATE_KEY is not set")
    if env.SELLER_ENTITY_ID is None:
        raise Exception("SELLER_ENTITY_ID is not set")
    if env.SELLER_AGENT_WALLET_ADDRESS is None:
        raise Exception("SELLER_AGENT_WALLET_ADDRESS is not set")

    # Initialize the ACP client
    acp_client = VirtualsACP(
        acp_contract_client=ACPContractManager(
            wallet_private_key=env.WHITELISTED_WALLET_PRIVATE_KEY,
            agent_wallet_address=env.SELLER_AGENT_WALLET_ADDRESS,
            entity_id=env.SELLER_ENTITY_ID,
            config=config
        ),
        on_new_task=on_new_task
    )

    logger.info("Seller agent is running...")
    threading.Event().wait()


if __name__ == "__main__":
    seller()
