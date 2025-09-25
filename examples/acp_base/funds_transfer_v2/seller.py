import threading
import logging
import hashlib
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
from dotenv import load_dotenv

from virtuals_acp import ACPMemo, MemoType
from virtuals_acp.configs import BASE_SEPOLIA_CONFIG
from virtuals_acp.client import VirtualsACP
from virtuals_acp.env import EnvSettings
from virtuals_acp.job import ACPJob
from virtuals_acp.models import ACPJobPhase, IDeliverable
from virtuals_acp.contract_manager import ACPContractManager
from virtuals_acp.fare import FareAmount, Fare

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("FundsSellerAgent")

load_dotenv(override=True)
config = BASE_SEPOLIA_CONFIG


class JobName(str, Enum):
    OPEN_POSITION = "open_position"
    CLOSE_POSITION = "close_position"
    SWAP_TOKEN = "swap_token"


@dataclass
class Position:
    symbol: str
    amount: float


@dataclass
class ClientWallet:
    client_address: str
    positions: List[Position] = field(default_factory=list)


clients: Dict[str, ClientWallet] = {}


def _derive_wallet_addr(addr: str) -> str:
    """Derive a fake wallet address from client address (sha256)."""
    h = hashlib.sha256(addr.encode()).hexdigest()
    return f"0x{h}"


def get_client_wallet(address: str) -> ClientWallet:
    """Get or create a wallet for a client address."""
    derived = _derive_wallet_addr(address)
    if derived not in clients:
        clients[derived] = ClientWallet(client_address=derived)
    return clients[derived]

def on_new_task(job: ACPJob, memo_to_sign: Optional[ACPMemo] = None) -> None:
    job_id = job.id
    job_phase = job.phase
    job_name = job.name
    if memo_to_sign == None:
        logger.warning(f"[on_new_task] No memo to sign | job_id={job_id}")
    memo_id = memo_to_sign.id

    logger.info(
        f"[on_new_task] Received job | job_id={job_id}, job_phase={job_phase}, job_name={job_name}, memo_id={memo_id}"
    )

    if job_phase == ACPJobPhase.REQUEST:
        handle_task_request(job, memo_to_sign)
    elif job_phase == ACPJobPhase.TRANSACTION:
        handle_task_transaction(job)

def handle_task_request(job: ACPJob, memo_to_sign: ACPMemo):
    job_name = job.name
    job_id = job.id
    memo_id = memo_to_sign.id if memo_to_sign else None

    if not job_name or memo_to_sign is None:
        logger.error(
            f"[handle_task_request] Missing data | job_id={job_id}, memo_id={memo_id}, job_name={job_name}"
        )
        return

    if job_name == JobName.OPEN_POSITION:
        logger.info(f"Accepts position opening request | requirement={job.requirement}")
        memo_to_sign.sign(True, "Accepts position opening")
        return job.create_requirement_payable_memo(
            "Send me USDC to open position",
            MemoType.PAYABLE_REQUEST,
            FareAmount(
                float(job.requirement.get("amount", 0)),
                config.base_fare  # Open position against ACP Base Currency: USDC
            ),
            job.provider_address,
        )

    if job_name == JobName.CLOSE_POSITION:
        wallet = get_client_wallet(job.client_address)
        symbol = job.requirement.get("symbol", None)
        position = next(
            (p for p in wallet.positions if p.symbol == symbol),
            None
        )
        position_is_valid = position is not None and position.amount > 0
        logger.info(
            f'{"Accepts" if position_is_valid else "Rejects"} position closing request | requirement={job.requirement}'
        )
        memo_to_sign.sign(
            position_is_valid,
            f"{'Accepts' if position_is_valid else 'Rejects'} position closing"
        )
        if position_is_valid:
            return job.create_requirement_memo(
                f"Close {symbol} position as requested."
            )

    if job_name == JobName.SWAP_TOKEN:
        logger.info(f"Accepts token swapping request | requirement={job.requirement}")
        memo_to_sign.sign(True, "Accepts token swapping request")
        return job.create_requirement_payable_memo(
            "Send me USDC to swap to VIRTUAL",
            MemoType.PAYABLE_REQUEST,
            FareAmount(
                float(job.requirement.get("amount", 0)),
                Fare.from_contract_address(
                    job.requirement.get("fromContractAddress"),
                    config
                )
            ),
            job.provider_address,
        )

    logger.warning(f"[handle_task_request] Unsupported job name | job_id={job_id}, job_name={job_name}")

def handle_task_transaction(job: ACPJob):
    job_name = job.name
    job_id = job.id
    wallet = get_client_wallet(job.client_address)

    if not job_name:
        logger.error(f"[handle_task_transaction] Missing job name | job_id={job_id}")
        return

    if job_name == JobName.OPEN_POSITION:
        adjust_position(
            wallet,
            job.requirement.get("symbol"),
            float(job.requirement.get("amount", 0))
        )
        logger.info(wallet)
        return job.deliver(IDeliverable(type="message", value="Opened position with hash 0x123..."))

    if job_name == JobName.CLOSE_POSITION:
        symbol = job.requirement.get("symbol")
        closing_amount = close_position(wallet, symbol)
        logger.info(wallet)
        job.create_requirement_payable_memo(
            f"Close {symbol} position as per request",
            MemoType.PAYABLE_TRANSFER_ESCROW,
            FareAmount(closing_amount, config.base_fare),
            job.client_address,
        )
        time.sleep(5)
        return job.deliver(IDeliverable(type="message", value="Closed position with hash 0x123..."))

    if job_name == JobName.SWAP_TOKEN:
        job.create_requirement_payable_memo(
            f"Return swapped token {job.requirement.get('toSymbol', 'VIRTUAL')}",
            MemoType.PAYABLE_TRANSFER_ESCROW,
            FareAmount(
                1,
                Fare.from_contract_address(
                    job.requirement.get("toContractAddress"),
                    config
                )
            ),
            job.client_address,
        )
        time.sleep(5)
        return job.deliver(IDeliverable(type="message", value="Swapped token with hash 0x123..."))

    logger.warning(f"[handle_task_transaction] Unsupported job name | job_id={job_id}, job_name={job_name}")

def adjust_position(wallet: ClientWallet, symbol: str, delta: float) -> None:
    pos = next((p for p in wallet.positions if p.symbol == symbol), None)
    if pos:
        pos.amount += delta
    else:
        wallet.positions.append(Position(symbol=symbol, amount=delta))


def close_position(wallet: ClientWallet, symbol: str) -> Optional[float]:
    pos = next((p for p in wallet.positions if p.symbol == symbol), None)
    if pos:
        # remove the position from wallet
        wallet.positions = [p for p in wallet.positions if p.symbol != symbol]
        return pos.amount
    return None


def seller():
    env = EnvSettings()

    # Initialize the ACP client
    VirtualsACP(
        acp_contract_client=ACPContractManager(
            wallet_private_key=env.WHITELISTED_WALLET_PRIVATE_KEY,
            agent_wallet_address=env.SELLER_AGENT_WALLET_ADDRESS,
            entity_id=env.SELLER_ENTITY_ID,
            config=config,
        ),
        on_new_task=on_new_task
    )

    threading.Event().wait()

if __name__ == "__main__":
    seller()
