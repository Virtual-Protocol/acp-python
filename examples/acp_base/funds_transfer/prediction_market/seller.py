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
from virtuals_acp.fare import FareAmount

# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("PredictionMarketSellerAgent")

load_dotenv(override=True)
config = BASE_MAINNET_CONFIG_V2
REJECT_AND_REFUND = False  # flag to trigger job.reject_payable use cases


class JobName(str, Enum):
    CREATE_MARKET = "create_market"
    PLACE_BET = "place_bet"
    CLOSE_BET = "close_bet"


@dataclass
class Bet:
    bettor: str
    outcome: str
    amount: float


@dataclass
class Market:
    market_id: str
    question: str
    outcomes: List[str]
    end_time: str
    liquidity: float
    bets: List[Bet]
    outcome_pools: Dict[str, float]
    resolved_outcome: Optional[str] = None


markets: Dict[str, Market] = {}


def _derive_market_id(question: str) -> str:
    h = hashlib.sha256(question.encode()).hexdigest()
    return f"0x{h[:8]}"


def resolve_market(market: Market, resolved_outcome: str) -> float:
    market.resolved_outcome = resolved_outcome
    total_pool = sum(market.outcome_pools.values())
    winning_pool = market.outcome_pools.get(resolved_outcome, 0)

    if winning_pool == 0:
        logger.info(f"No bets placed on {resolved_outcome}. Liquidity returned to creator.")
        return 0

    payout_ratio = total_pool / winning_pool
    logger.info(f"Payout ratio for {resolved_outcome}: {payout_ratio:.2f}x")

    winning_bets = [b for b in market.bets if b.outcome == resolved_outcome]
    payouts: Dict[str, float] = {}

    for bet in winning_bets:
        payouts[bet.bettor] = payouts.get(bet.bettor, 0) + bet.amount * payout_ratio

    logger.info(f"Simulated payouts for {len(payouts)} winning bettors:")
    for idx, (bettor, payout) in enumerate(payouts.items(), start=1):
        logger.info(f"[{idx}] {bettor} receives {payout:.2f}")

    logger.info(f"Total distributed: {total_pool:.2f} (liquidity + all bets)")
    return total_pool


def close_bet(client_address: str, market_id: str) -> float:
    market = markets.get(market_id)
    if not market:
        return 0.0

    bets = [b for b in market.bets if b.bettor == client_address]
    if not bets:
        return 0.0

    total_payout = 0.0
    for bet in bets:
        total_pool = sum(market.outcome_pools.values())
        outcome_pool = market.outcome_pools.get(bet.outcome, 0)
        price = (outcome_pool / total_pool) if total_pool > 0 and outcome_pool > 0 else 1.0
        payout = bet.amount * price
        total_payout += payout

        market.bets.remove(bet)
        market.outcome_pools[bet.outcome] = float(max(0.0, outcome_pool - bet.amount))

    return total_payout


def prompt_resolve_market(job: ACPJob):
    market = None
    while not market:
        market_id = input("\nEnter market ID to resolve: ").strip()
        market = markets.get(market_id)
        if not market:
            logger.warning("Invalid market ID. Please try again.")

    logger.info(f"\n\nAvailable resolution actions:")
    for idx, outcome in enumerate(market.outcomes, start=1):
        print(f"{idx}. {outcome}")

    selected_action = None
    while not selected_action:
        try:
            selected_index = int(input("\nSelect a resolution (enter number): ").strip())
            selected_action = market.outcomes[selected_index - 1]
        except (ValueError, IndexError):
            logger.warning("Invalid selection. Please try again.")

    logger.info(f"Market {market.market_id} resolved as {selected_action}. Calculating payouts...")
    total_distributed = resolve_market(market, selected_action)

    job.create_payable_notification(
        f"Market {market.market_id} resolved as {selected_action}. "
        f"Payouts distributed with txn hash 0x0f60a30d66f1f3d21bad63e4e53e59d94ae286104fe8ea98f28425821edbca1b",
        FareAmount(total_distributed, config.base_fare),
    )

    logger.info(f"Payout distribution for market {market.market_id} completed successfully.")
    del markets[market.market_id]
    logger.info(f"Markets: {markets}")


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
    job_name = job.name
    if not job_name or memo_to_sign is None:
        logger.error(f"[handle_task_request] Missing data | job_id={job.id}, job_name={job_name}")
        return

    if job_name == JobName.CREATE_MARKET:
        logger.info(f"Accepts market creation request | requirement={job.requirement}")
        job.accept("Accepts market creation")
        liquidity = float(job.requirement.get("liquidity", 0))
        return job.create_payable_requirement(
            "Send USDC to setup initial liquidity to create market",
            MemoType.PAYABLE_REQUEST,
            FareAmount(
                liquidity,
                config.base_fare # ACP Base Currency: USDC
            ),
            job.provider_address, # funds receiving address, can be any address on Base
        )

    if job_name == JobName.PLACE_BET:
        payload = job.requirement
        market_id = payload.get("marketId")
        market_is_valid = market_id in markets

        response = (
            f"Accepts bet placing request, please make payment to place bet for market {market_id}"
            if market_is_valid
            else f"Rejects bet placing request, market {market_id} is invalid"
        )

        logger.info(response)
        if not market_is_valid:
            return job.reject(response)

        job.accept(response)
        amount = float(payload.get("amount", 0))
        token = payload.get("token", "USDC")
        return job.create_payable_requirement(
            f"Send {amount} {token} to place bet",
            MemoType.PAYABLE_REQUEST,
            FareAmount(
                amount,
                config.base_fare # ACP Base Currency: USDC
            ),
            job.provider_address, # funds receiving address, can be any address on Base
        )

    if job_name == JobName.CLOSE_BET:
        payload = job.requirement
        market_id = payload.get("marketId")
        market = markets.get(market_id)
        market_is_valid = market is not None
        bet_is_valid = False

        if market_is_valid:
            bet_is_valid = any(b.bettor == job.client_address for b in market.bets)

        response = (
            f"Accepts bet closing request, please make payment to close bet for market {market_id}"
            if market_is_valid and bet_is_valid
            else (
                f"Rejects bet closing request, "
                f"{f'client address {job.client_address} does not have bet placed in market {market_id}' if market_is_valid else f'market {market_id} is invalid'}"
            )
        )

        logger.info(response)
        if not bet_is_valid:
            return job.reject(response)

        job.accept(response)
        return job.create_requirement(response)

    logger.warning(f"[handle_task_request] Unsupported job name | job_name={job_name}")


def handle_task_transaction(job: ACPJob):
    job_name = job.name

    if job_name == JobName.CREATE_MARKET:
        payload = job.requirement
        question = payload.get("question")
        outcomes = payload.get("outcomes", [])
        liquidity = job.net_payable_amount # liquidity principal after ACP fee deduction
        end_time = payload.get("endTime")
        market_id = _derive_market_id(question)

        if REJECT_AND_REFUND:  # to cater cases where a reject and refund is needed (ie: internal server error)
            reason = f"Internal server error handling market creation for {question}"
            logger.info(f"Rejecting and refunding job {job.id} with reason: {reason}")
            job.reject_payable(
                reason,
                FareAmount(
                    job.net_payable_amount, # return the net payable amount from seller wallet
                    config.base_fare
                ),
            )
            logger.info(f"Job {job.id} rejected and refunded.")
            return

        if len(outcomes) < 2:
            return job.reject("Market creation failed: need >= 2 outcomes")

        per_outcome_liquidity = liquidity / len(outcomes) if outcomes else 0
        outcome_pools = {o: per_outcome_liquidity for o in outcomes}

        markets[market_id] = Market(
            market_id=market_id,
            question=question,
            outcomes=outcomes,
            end_time=end_time,
            liquidity=liquidity,
            bets=[],
            outcome_pools=outcome_pools,
        )

        logger.info(f"Market created: {question} | id={market_id}")
        job.deliver(f"Market created with id {market_id}")
        logger.info(f"Markets: {markets}")
        return

    if job_name == JobName.PLACE_BET:
        payload = job.requirement
        market_id = payload.get("marketId")
        outcome = payload.get("outcome")
        amount = job.net_payable_amount # betting principal after ACP fee deduction
        market = markets.get(market_id)

        if not market:
            return job.reject(f"Market {market_id} not found")

        if REJECT_AND_REFUND:  # to cater cases where a reject and refund is needed (ie: internal server error)
            reason = f"Internal server error handling bet placement for market {market_id}"
            logger.info(f"Rejecting and refunding job {job.id} with reason: {reason}")
            job.reject_payable(
                reason,
                FareAmount(
                    job.net_payable_amount, # return the net payable amount from seller wallet
                    config.base_fare
                ),
            )
            logger.info(f"Job {job.id} rejected and refunded.")
            return

        market.bets.append(Bet(bettor=job.client_address, outcome=outcome, amount=amount))
        market.outcome_pools[outcome] = market.outcome_pools.get(outcome, 0) + amount

        logger.info(f"{amount} $USDC bet placed on {outcome} in {market_id} by {job.client_address}")
        job.deliver("Bet recorded")
        logger.info(f"Markets: {markets}")

        prompt_resolve_market(job)
        return

    if job_name == JobName.CLOSE_BET:
        payload = job.requirement
        market_id = payload.get("marketId")
        
        if REJECT_AND_REFUND:  # to cater cases where a reject and refund is needed (ie: internal server error)
            reason = f"Internal server error handling bet closure for market {market_id}"
            logger.info(f"Rejecting and refunding job {job.id} with reason: {reason}")
            # Get the original bet amount before closing (close_bet removes bets from market)
            market = markets.get(market_id)
            bets = [b for b in (market.bets if market else []) if b.bettor == job.client_address]
            original_bet_amount = sum(bet.amount for bet in bets)
            job.reject_payable(
                reason,
                FareAmount(
                    original_bet_amount,
                    config.base_fare
                )
            )
            logger.info(f"Job {job.id} rejected and refunded.")
            return
        
        closing_amount = close_bet(job.client_address, market_id)
        logger.info(f"Bet closed for {job.client_address} in market {market_id}")
        job.deliver_payable(
            f"Bet closed in market {market_id}, returning {closing_amount} USDC",
            FareAmount(closing_amount, config.base_fare),
        )
        logger.info(f"Markets: {markets}")
        return

    logger.warning(f"[handle_task_transaction] Unsupported job name | job_name={job_name}")


def seller():
    env = EnvSettings()
    VirtualsACP(
        acp_contract_clients=ACPContractClientV2(
            wallet_private_key=env.WHITELISTED_WALLET_PRIVATE_KEY,
            agent_wallet_address=env.SELLER_AGENT_WALLET_ADDRESS,
            entity_id=env.SELLER_ENTITY_ID,
            config=config,
        ),
        on_new_task=on_new_task,
    )
    threading.Event().wait()


if __name__ == "__main__":
    seller()
