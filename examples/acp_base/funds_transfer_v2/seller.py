import threading
import logging
import hashlib
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
from dotenv import load_dotenv

from virtuals_acp import ACPMemo
from virtuals_acp.configs import BASE_SEPOLIA_CONFIG
from virtuals_acp.client import VirtualsACP
from virtuals_acp.env import EnvSettings
from virtuals_acp.job import ACPJob
from virtuals_acp.models import ACPJobPhase, IDeliverable, MemoType
from virtuals_acp.contract_manager import ACPContractManager
from virtuals_acp.fare import FareAmount

# Logging setup
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
    client_address: str
    assets: List[FareAmount] = field(default_factory=list)
    positions: List[Position] = field(default_factory=list)

clients: Dict[str, ClientWallet] = {}

def _derive_wallet_addr(addr: str) -> str:
    h = hashlib.sha256(addr.encode()).hexdigest()
    return f"0x{h}"

def get_client_wallet(address: str) -> ClientWallet:
    derived = _derive_wallet_addr(address)
    if derived not in clients:
        clients[derived] = ClientWallet(client_address=derived)
    return clients[derived]

def seller():
    env = EnvSettings()

    def handle_task_request(job: ACPJob, memo: ACPMemo):
        job_name = job.name
        if not job_name:
            logger.error(f"Job has no name: {job}")
            return

        expiry = datetime.now(timezone.utc) + timedelta(minutes=10)

        if job_name == JobName.OPEN_POSITION.value:
            memo.sign(True, "accepts open position")
            return job.create_requirement_payable_memo(
                "Send me 1 USDC to open position",
                MemoType.PAYABLE_REQUEST,
                FareAmount(1, config.base_fare),
                job.provider_address,
                expired_at=expiry,
            )

        if job_name == JobName.CLOSE_POSITION.value:
            memo.sign(True, "accepts close position")
            return job.create_requirement_memo("Closing a random position")

        if job_name == JobName.SWAP_TOKEN.value:
            memo.sign(True, "accepts swap token")
            return job.create_requirement_payable_memo(
                "Send me 1 USDC to swap to 1 VIRTUAL",
                MemoType.PAYABLE_REQUEST,
                FareAmount(1, config.base_fare),
                job.provider_address,
                expired_at=expiry,
            )

        if job_name == JobName.WITHDRAW.value:
            memo.sign(True, "accepts withdraw")
            return job.create_requirement_payable_memo(
                "Withdrawing a random amount",
                MemoType.PAYABLE_TRANSFER_ESCROW,
                FareAmount(1, config.base_fare),
                job.provider_address,
                expired_at=expiry,
            )

        logger.warning("Unhandled job name %s", job_name)

    def handle_task_transaction(job: ACPJob, memo: Optional[ACPMemo]):
        job_name = job.name
        if not job_name:
            logger.error(f"Job has no name in transaction: {job}")
            return

        if job_name == JobName.OPEN_POSITION.value:
            wallet = get_client_wallet(job.client_address)
            pos = next((p for p in wallet.positions if p.symbol == "USDC"), None)
            if pos:
                pos.amount += 1
            else:
                wallet.positions.append(Position(symbol="USDC", amount=1))
            return job.deliver(IDeliverable(
                type="message", 
                value="Opened position with hash 0x1234567890"
            ))

        if job_name == JobName.CLOSE_POSITION.value:
            wallet = get_client_wallet(job.client_address)
            pos = next((p for p in wallet.positions if p.symbol == "USDC"), None)
            wallet.positions = [p for p in wallet.positions if p.symbol != "USDC"]

            # credit assets in base token
            asset = next((a for a in wallet.assets if a.fare.contract_address == config.base_fare.contract_address), None)
            credited = (pos.amount if pos else 0)
            if not asset:
                wallet.assets.append(FareAmount(credited, config.base_fare))
            else:
                asset.amount += FareAmount(credited, config.base_fare).amount  # FareAmount.amount is int (scaled)

            return job.deliver(IDeliverable(
                type="message", 
                value="Closed position with hash 0x1234567890"
            ))

        if job_name == JobName.SWAP_TOKEN.value:
            wallet = get_client_wallet(job.client_address)
            asset = next((a for a in wallet.assets if a.fare.contract_address == config.base_fare.contract_address), None)
            if not asset:
                wallet.assets.append(FareAmount(1, config.base_fare))
            else:
                asset.amount += FareAmount(1, config.base_fare).amount
            return job.deliver(IDeliverable(
                type="message", 
                value="Swapped token with hash 0x1234567890"
            ))

        if job_name == JobName.WITHDRAW.value:
            return job.deliver(IDeliverable(
                type="message",
                value="Withdrawn amount with hash 0x1234567890"
            ))

        logger.warning("Unhandled job name %s in transaction", job_name)
    
    def on_new_task(job: ACPJob, memo_to_sign: Optional[ACPMemo] = None):
        logger.info(f"New job {job.id} phase={job.phase} name={job.name} memo={getattr(memo_to_sign,'id',None)}")

        if job.phase == ACPJobPhase.REQUEST:
            if not memo_to_sign:
                logger.error(f"No memo provided for request phase job {job.id}")
                return
            return handle_task_request(job, memo_to_sign)

        if job.phase == ACPJobPhase.TRANSACTION:
            return handle_task_transaction(job, memo_to_sign)

        # Ignore other phases (mirrors Node’s behavior of only acting in REQUEST/TRANSACTION)
        logger.info(f"Ignoring job {job.id} in phase {job.phase}")

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
