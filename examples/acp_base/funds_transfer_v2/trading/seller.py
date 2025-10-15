import threading
import logging
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from dotenv import load_dotenv

from virtuals_acp.memo import ACPMemo, MemoType
from virtuals_acp.client import VirtualsACP
from virtuals_acp.env import EnvSettings
from virtuals_acp.job import ACPJob
from virtuals_acp.models import ACPJobPhase
from virtuals_acp.configs.configs import BASE_MAINNET_CONFIG_V2
from virtuals_acp.contract_clients.contract_client_v2 import ACPContractClientV2
from virtuals_acp.fare import FareAmount, Fare

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("FundsSellerAgent")

load_dotenv(override=True)
config = BASE_MAINNET_CONFIG_V2

class JobName(str, Enum):
    OPEN_POSITION = "open_position"
    CLOSE_POSITION = "close_position"
    SWAP_TOKEN = "swap_token"

@dataclass
class Position:
    symbol: str
    amount: float
    tp: Dict[str, float]
    sl: Dict[str, float]

@dataclass
class ClientWallet:
    client_address: str
    positions: List[Position] = field(default_factory=list)

clients: Dict[str, ClientWallet] = {}

def _derive_wallet_address(addr: str) -> str:
    h = hashlib.sha256(addr.encode()).hexdigest()
    return f"0x{h}"

def get_client_wallet(address: str) -> ClientWallet:
    derived = _derive_wallet_address(address)
    if derived not in clients:
        clients[derived] = ClientWallet(client_address=derived)
    return clients[derived]

def prompt_tp_sl_action(job: ACPJob, wallet: ClientWallet):
    logger.info(f"Wallet: {wallet}")
    positions = [p for p in wallet.positions if p.amount > 0]
    if not positions:
        return

    action = None
    while action not in ("TP", "SL"):
        print("\nAvailable actions:\n1. Hit TP\n2. Hit SL")
        selection = input("\nSelect an action (enter 1 or 2): ").strip()
        if selection == "1":
            action = "TP"
        elif selection == "2":
            action = "SL"
        else:
            logger.warning("Invalid selection. Please try again.")

    position = None
    while position is None:
        symbol = input("Token symbol to close: ").strip()
        position = next((p for p in wallet.positions if p.symbol.lower() == symbol.lower()), None)
        if not position or position.amount <= 0:
            logger.warning("Invalid token symbol or position amount is zero. Please try again.")
            position = None

    logger.info(f"{position.symbol} position hits {action}, sending remaining funds back to buyer.")
    closing_amount = close_position(wallet, position.symbol)
    job.create_payable_notification(
        f"{position.symbol} position has hit {action}. Closed {position.symbol} position with txn hash 0x0f60a30d66f1f3d21bad63e4e53e59d94ae286104fe8ea98f28425821edbca1b",
        FareAmount(
            closing_amount * (
                (1 + ((position.tp.get("percentage") or 0) / 100)) if action == "TP"
                else (1 - ((position.sl.get("percentage") or 0) / 100))
            ),
            config.base_fare
        ),
    )
    logger.info(f"{position.symbol} position funds sent back to buyer.")
    logger.info(f"Wallet: {wallet}")

def on_new_task(job: ACPJob, memo_to_sign: Optional[ACPMemo] = None) -> None:
    job_id, job_phase, job_name = job.id, job.phase, job.name
    if memo_to_sign is None:
        logger.warning(f"[on_new_task] No memo to sign | job_id={job_id}")
        return
    memo_id = memo_to_sign.id
    logger.info(
        f"[on_new_task] Received job | job_id={job_id}, job_phase={job_phase}, job_name={job_name}, memo_id={memo_id}"
    )

    if job_phase == ACPJobPhase.REQUEST:
        handle_task_request(job, memo_to_sign)
    elif job_phase == ACPJobPhase.TRANSACTION:
        handle_task_transaction(job)

def handle_task_request(job: ACPJob, memo_to_sign: ACPMemo):
    job_name, job_id = job.name, job.id
    memo_id = memo_to_sign.id if memo_to_sign else None

    if not job_name or memo_to_sign is None:
        logger.error(f"[handle_task_request] Missing data | job_id={job_id}, memo_id={memo_id}, job_name={job_name}")
        return

    if job_name == JobName.OPEN_POSITION:
        logger.info(f"Accepts position opening request | requirement={job.requirement}")
        job.respond(True, "Accepts position opening")
        amount = float(job.requirement.get("amount", 0))
        return job.create_payable_requirement(
            "Send me USDC to open position",
            MemoType.PAYABLE_REQUEST,
            FareAmount(amount, config.base_fare),
            job.provider_address,
        )

    if job_name == JobName.CLOSE_POSITION:
        wallet = get_client_wallet(job.client_address)
        symbol = job.requirement.get("symbol")
        position = next((p for p in wallet.positions if p.symbol == symbol), None)
        position_is_valid = position is not None and position.amount > 0
        logger.info(f'{"Accepts" if position_is_valid else "Rejects"} position closing request | requirement={job.requirement}')
        if position_is_valid:
            response = f"Accepts position closing. Please make payment to close {symbol} position."
        else:
            response = "Rejects position closing. Position is invalid."

        job.respond(position_is_valid, response)
        return job.create_requirement(response)

    if job_name == JobName.SWAP_TOKEN:
        logger.info(f"Accepts token swapping request | requirement={job.requirement}")
        job.respond(True, "Accepts token swapping request")
        amount = float(job.requirement.get("amount", 0))
        from_contract = job.requirement.get("fromContractAddress")
        return job.create_payable_requirement(
            f"Send me {job.requirement.get('fromSymbol', 'USDC')} to swap to {job.requirement.get('toSymbol', 'VIRTUAL')}",
            MemoType.PAYABLE_REQUEST,
            FareAmount(amount, Fare.from_contract_address(from_contract, config)),
            job.provider_address,
        )

    logger.warning(f"[handle_task_request] Unsupported job name | job_id={job_id}, job_name={job_name}")

def handle_task_transaction(job: ACPJob):
    job_name, job_id = job.name, job.id
    wallet = get_client_wallet(job.client_address)

    if not job_name:
        logger.error(f"[handle_task_transaction] Missing job name | job_id={job_id}")
        return

    if job_name == JobName.OPEN_POSITION:
        open_position(wallet, job.requirement)
        logger.info(f"Opening position: {job.requirement}")
        job.deliver("Opened position with txn 0x71c038a47fd90069f133e991c4f19093e37bef26ca5c78398b9c99687395a97a")
        logger.info("Position opened")
        return prompt_tp_sl_action(job, wallet)

    if job_name == JobName.CLOSE_POSITION:
        symbol = job.requirement.get("symbol")
        closing_amount = close_position(wallet, symbol)
        logger.info(f"Returning closing amount: {closing_amount} USDC")
        job.deliver_payable(
            f"Closed {symbol} position with txn hash 0x0f60a30d66f1f3d21bad63e4e53e59d94ae286104fe8ea98f28425821edbca1b",
            FareAmount(closing_amount, config.base_fare),
        )
        logger.info("Closing amount returned")
        logger.info(f"Wallet: {wallet}")

    if job_name == JobName.SWAP_TOKEN:
        to_contract = job.requirement.get("toContractAddress")
        swapped_amount = FareAmount(
            0.00088,
            Fare.from_contract_address(to_contract, config)
        )
        logger.info(f"Returning swapped token: {swapped_amount}")
        job.deliver_payable(
            f"Return swapped token {job.requirement.get('toSymbol', 'VIRTUAL')}",
            swapped_amount
        )
        logger.info("Swapped token returned")

    else:
        logger.warning(f"[handle_task_transaction] Unsupported job name | job_id={job_id}, job_name={job_name}")

def open_position(wallet: ClientWallet, payload: dict[str, Any]) -> None:
    pos = next((p for p in wallet.positions if p.symbol == payload.get("symbol")), None)
    if pos:
        pos.amount += payload.get("amount")
    else:
        wallet.positions.append(
            Position(
                symbol=payload.get("symbol"),
                amount=payload.get("amount"),
                tp=payload.get("tp"),
                sl=payload.get("sl")
            )
        )

def close_position(wallet: ClientWallet, symbol: str) -> Optional[float]:
    pos = next((p for p in wallet.positions if p.symbol == symbol), None)
    wallet.positions = [p for p in wallet.positions if p.symbol != symbol]
    return pos.amount if pos else 0

def seller():
    env = EnvSettings()
    VirtualsACP(
        acp_contract_clients=ACPContractClientV2(
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
