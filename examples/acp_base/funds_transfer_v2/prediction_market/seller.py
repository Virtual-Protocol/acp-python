import threading
import logging
import hashlib
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
from dotenv import load_dotenv

from virtuals_acp.memo import ACPMemo, MemoType
from virtuals_acp.client import VirtualsACP
from virtuals_acp.env import EnvSettings
from virtuals_acp.job import ACPJob
from virtuals_acp.models import ACPJobPhase
from virtuals_acp.configs.configs import BASE_MAINNET_CONFIG_V2
from virtuals_acp.contract_clients.contract_client_v2 import ACPContractClientV2
from virtuals_acp.fare import FareAmount, FareAmountBase, Fare

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("PredictionMarketSellerAgent")

load_dotenv(override=True)
config = BASE_MAINNET_CONFIG_V2


class JobName(str, Enum):
    CREATE_MARKET = "create_market" # Creates a new prediction market
    PLACE_BET = "place_bet" # Places a bet on an existing market
    CLOSE_BET = "close_bet" # Closes betting for a given marketId


@dataclass
class Bet:
    outcome: str
    amount: float


@dataclass
class Market:
    market_id: str
    question: str
    outcomes: List[str]
    end_time: str
    liquidity: float
    bets: List[Bet] = field(default_factory=list)
    closed: bool = False
    outcome_pools: Dict[str, float] = field(default_factory=dict)


markets: Dict[str, Market] = {}


def _derive_market_id(question: str) -> str:
    """Derive deterministic market ID from question (sha256)."""
    h = hashlib.sha256(question.encode()).hexdigest()
    return f"0x{h[:8]}"


def on_new_task(job: ACPJob, memo_to_sign: Optional[ACPMemo] = None) -> None:
    if memo_to_sign is None:
        logger.warning(f"[on_new_task] No memo to sign | job_id={job.id}")
        return

    logger.info(
        f"[on_new_task] Received job | job_id={job.id}, job_phase={job.phase}, "
        f"job_name={job.name}, memo_id={memo_to_sign.id}"
    )

    if job.phase == ACPJobPhase.REQUEST:
        handle_task_request(job, memo_to_sign)
    elif job.phase == ACPJobPhase.TRANSACTION:
        handle_task_transaction(job)


def handle_task_request(job: ACPJob, memo_to_sign: ACPMemo):
    job_name = job.name

    if not job_name or memo_to_sign is None:
        logger.error(f"[handle_task_request] Missing data | job_id={job.id}, job_name={job_name}")
        return

    if job_name == JobName.CREATE_MARKET:
        logger.info(f"Accepts create market request | requirement={job.requirement}")
        job.respond(True, "Accepts market creation")

        market_id = _derive_market_id(job.requirement["question"])
        outcomes = job.requirement.get("outcomes", [])
        if isinstance(outcomes, str):
            outcomes = [outcomes]

        if len(outcomes) < 2:
            return job.deliver("Market creation failed: need >=2 outcomes")

        liquidity = float(job.requirement.get("liquidity", 0))
        per_outcome_liquidity = liquidity / len(outcomes)
        outcome_pools = {o: per_outcome_liquidity for o in outcomes}

        markets[market_id] = Market(
            market_id=market_id,
            question=job.requirement["question"],
            outcomes=outcomes,
            end_time=job.requirement["endTime"],
            liquidity=liquidity,
            outcome_pools=outcome_pools,
        )

        return job.create_payable_requirement(
            "Provide initial liquidity to create market",
            MemoType.PAYABLE_REQUEST,
            FareAmount(liquidity, config.base_fare),
            job.provider_address,
        )

    if job_name == JobName.PLACE_BET:
        logger.info(f"Accepts bet placement request | requirement={job.requirement}")
        job.respond(True, "Accepts bet placement")

        return job.create_payable_requirement(
            f"Send {job.requirement['amount']} {job.requirement.get('token','USDC')} to place bet",
            MemoType.PAYABLE_REQUEST,
            FareAmount(float(job.requirement["amount"]), config.base_fare),
            job.provider_address,
        )

    if job_name == JobName.CLOSE_BET:
        logger.info(f"Accepts close bet request | requirement={job.requirement}")
        job.respond(True, "Accepts bet closing")
        return job.create_requirement("Betting phase will be closed for this market")


def handle_task_transaction(job: ACPJob):
    job_name = job.name

    if not job_name:
        logger.error(f"[handle_task_transaction] Missing job name | job_id={job.id}")
        return

    if job_name == JobName.CREATE_MARKET:
        market_id = _derive_market_id(job.requirement["question"])
        logger.info(f"Market created: {markets[market_id].question} | id={market_id}")
        return job.deliver("Market created with market id {market_id}")

    if job_name == JobName.PLACE_BET:
        market_id = job.requirement["marketId"]
        outcome = job.requirement["outcome"]
        amount = float(job.requirement["amount"])

        if market_id not in markets:
            return job.deliver("Bet failed: market not found")

        market = markets[market_id]
        if market.closed:
            return job.deliver("Bet failed: market is closed")

        if outcome not in market.outcomes:
            return job.deliver("Bet failed: invalid outcome")

        market.bets.append(Bet(outcome=outcome, amount=amount))
        market.outcome_pools[outcome] += amount
        logger.info(f"Bet placed: Bet {amount} on {outcome} in {market_id}")

        return job.deliver("Bet recorded")

    if job_name == JobName.CLOSE_BET:
        market_id = job.requirement["marketId"]

        if market_id not in markets:
            return job.deliver("Close bet failed: market not found")

        market = markets[market_id]
        market.closed = True
        logger.info(f"Betting closed for market {market_id}")

        return job.deliver(f"Betting closed for market {market_id}")


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
