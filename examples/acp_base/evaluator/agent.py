import asyncio
import json
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Set, Union

from dotenv import load_dotenv

from google.adk.agents.llm_agent import Agent
from google.adk.events.event import Event
from google.adk.runners import Runner
from google.adk.sessions import VertexAiSessionService
from google.adk.tools.google_search_tool import GoogleSearchTool
from google.adk.tools.url_context_tool import UrlContextTool
from google.genai import types
from rapidfuzz import fuzz

from env import EnvSettings
from virtuals_acp.client import VirtualsACP
from virtuals_acp.exceptions import ACPApiError
from virtuals_acp.job import ACPJob
from virtuals_acp.contract_clients.contract_client_v2 import ACPContractClientV2
from virtuals_acp.memo import ACPMemo
from virtuals_acp.models import ACPJobPhase

# Phases where the job is already terminal; reject_job cannot be used.
_TERMINAL_PHASES = {ACPJobPhase.COMPLETED, ACPJobPhase.REJECTED, ACPJobPhase.EXPIRED}

load_dotenv(override=True)
env = EnvSettings()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("EvaluatorAgent")
# Suppress noisy GenAI warning when model returns function_call parts; ADK handles them correctly.
logging.getLogger("google_genai.types").setLevel(logging.ERROR)

POLL_INTERVAL_SECONDS = 20

# Job queue: id -> ACPJob, updated each poll and by on_evaluate socket. Use _get_job_from_queue(job_id) to read; respond_to_job uses it first.
_job_queue: Dict[int, ACPJob] = {}
_job_queue_lock = threading.Lock()

# Parent job id -> list of {job_id, expected_outcome} for evaluation flow. Poll loop waits for these to be terminal, compiles report, delivers.
_evaluation_children: Dict[int, List[Dict[str, Any]]] = {}
_evaluation_children_lock = threading.Lock()

# Parent job ids for which we have already started the evaluation flow (one round of children). Skip creating another round.
_parent_evaluation_started: Set[int] = set()

# One session per job (reused across phases: REQUEST -> TRANSACTION for parent; single EVALUATION for child).
_job_sessions: Dict[int, str] = {}
_job_sessions_lock = threading.Lock()

def _on_new_task(job: ACPJob, _memo_to_sign: Optional[ACPMemo] = None) -> None:
    """Socket handler: add incoming job to the job queue so the poll loop will process it."""
    with _job_queue_lock:
        _job_queue[job.id] = job
    logger.info("Job %s added to queue from on_new_task socket", job.id)

def _on_evaluate(job: ACPJob) -> None:
    """Socket handler: add incoming evaluation job to the job queue so the poll loop will process it."""
    with _job_queue_lock:
        _job_queue[job.id] = job
    logger.info("Job %s added to queue from on_evaluate socket", job.id)


acp_client = VirtualsACP(
    acp_contract_clients=ACPContractClientV2(
        wallet_private_key=env.WHITELISTED_WALLET_PRIVATE_KEY,
        agent_wallet_address=env.EVALUATOR_AGENT_WALLET_ADDRESS,
        entity_id=env.EVALUATOR_ENTITY_ID
    ),
    on_new_task=_on_new_task,
    on_evaluate=_on_evaluate
)


def verify_agent_identity(
    agent_wallet_address: str, agent_name: str
) -> Dict[str, Any]:
    """
    Verify if the agentName matches the wallet address in the ACP network using fuzzy matching.
    Handles typos, case differences, and spacing variations (e.g., "whisper ai" vs "whisperAI").

    Args:
        agent_wallet_address: The wallet address to verify
        agent_name: The agent name to check against

    Returns:
        Dict with "matches" (bool) and "reasoning" (str).
    """
    try:
        agent = acp_client.get_agent(agent_wallet_address)
        if not agent:
            return {
                "matches": False,
                "reasoning": f"Agent not found for wallet address: {agent_wallet_address}"
            }

        actual_name = agent.name

        # Normalize names for comparison (lowercase, strip whitespace)
        normalized_provided = (agent_name or "").strip().lower()
        normalized_actual = (actual_name or "").strip().lower()

        # Exact match after normalization
        if normalized_provided == normalized_actual:
            matches = True
            similarity = 100.0
        else:
            # Use fuzzy matching to handle typos and variations
            SIMILARITY_THRESHOLD = 85.0
            ratio = fuzz.ratio(normalized_provided, normalized_actual)
            token_sort_ratio = fuzz.token_sort_ratio(normalized_provided, normalized_actual)
            similarity = max(ratio, token_sort_ratio)
            matches = similarity >= SIMILARITY_THRESHOLD

        return {
            "matches": matches,
            "reasoning": f"Agent verification for wallet {agent_wallet_address} with provided name {agent_name} and actual name {actual_name} resulted in a similarity of {similarity:.1f}%"
        }

    except Exception as e:
        return {
            "matches": False,
            "reasoning": f"Error verifying agent identity: {e}"
        }


# ADK tools only accept types the LLM can pass (e.g. int, str, bool). We look up the job from the queue (or fetch if missing).

def _log_agent_event(event: Event, job_id: int) -> None:
    """Log agent activity (text, tool calls, tool results) for visibility when running python agent.py."""
    if not event.content or not event.content.parts:
        return
    text_parts: List[str] = []
    for part in event.content.parts:
        if part.text:
            text_parts.append(part.text)
        elif part.function_call:
            logger.info(
                "[job %s] %s > tool call: %s(%s)",
                job_id,
                event.author,
                part.function_call.name,
                getattr(part.function_call, "args", None) or {},
            )
        elif part.function_response:
            resp = getattr(part.function_response, "response", None)
            name = getattr(part.function_response, "name", "")
            resp_str = str(resp or "")
            logger.info(
                "[job %s] %s > tool result: %s -> %s",
                job_id,
                event.author,
                name,
                resp_str[:200] + ("..." if len(resp_str) > 200 else ""),
            )
    if text_parts:
        full_text = " ".join(text_parts).strip()
        logger.info("[job %s] %s > %s", job_id, event.author, full_text)


def _get_job_from_queue(job_id: int) -> Optional[ACPJob]:
    """Get a job from the shared queue (updated each poll). Returns None if not in queue."""
    with _job_queue_lock:
        return _job_queue.get(job_id)


def _get_job_or_none(job_id: int) -> Optional[ACPJob]:
    """Get job from queue first, else fetch by id. Returns None if job not found."""
    job = _get_job_from_queue(job_id)
    if job is not None:
        return job
    try:
        return acp_client.get_job_by_onchain_id(job_id)
    except ACPApiError:
        return None


def accept_job(job_id: int, reason: str) -> str:
    """
    Accept a job request (REQUEST phase only). Use after verifying agent identity.
    Signs the request memo and creates the payment requirement. Fails if job is not in REQUEST phase or job not found.

    Args:
        job_id: The on-chain job id.
        reason: Explanation for accepting.
    """
    job = _get_job_or_none(job_id)
    if job is None:
        return f"Job {job_id} not found. Cannot accept."
    if job.phase != ACPJobPhase.REQUEST:
        return f"Job {job_id} is in {job.phase.name} phase. accept_job only works in REQUEST phase."
    try:
        job.accept(reason)
        job.create_requirement("Job accepted, please make payment to proceed")
        return f"Job {job_id} accepted. {reason}"
    except ValueError as e:
        return f"Job {job_id} accept failed: {e}"


def reject_job(job_id: int, reason: str) -> str:
    """
    Reject a job. Works in REQUEST phase and other active phases (e.g. NEGOTIATION, TRANSACTION, EVALUATION).
    Cannot reject jobs already COMPLETED, REJECTED, or EXPIRED. Fails if job not found.

    Args:
        job_id: The on-chain job id.
        reason: Explanation for rejecting.
    """
    job = _get_job_or_none(job_id)
    if job is None:
        return f"Job {job_id} not found. Cannot reject."
    if job.phase in _TERMINAL_PHASES:
        return f"Job {job_id} is already in {job.phase.name}. Cannot reject."
    try:
        if job.phase == ACPJobPhase.EVALUATION:
            job.evaluate(accept=False, reason=reason)
            return f"Job {job_id} evaluated and rejected. {reason}"
        else:
            job.reject(reason)
            return f"Job {job_id} rejected. {reason}"
    except ValueError as e:
        return f"Job {job_id} reject failed: {e}"


def get_agent_offerings(agent_wallet_address: str) -> str:
    """
    Get an agent and their job offerings for the evaluation flow.
    Returns a JSON string with agent name, description, and list of offerings (each with index, name, requirement_schema, price).
    For each offering: initiate at least 2 jobs with expected_outcome "accept" (valid requirement) to evaluate deliverable quality. When the requirement schema has fields that can be invalid (e.g. token_symbol, news_category, type), initiate 2 jobs with expected_outcome "reject" using invalid values (e.g. fake token_symbol "casdcasd", wrong enum, missing required field) so the provider should reject them — do not be lenient; always test reject when such fields exist. Offerings with no or empty schema need only 2 accept cases; use service_requirement_json "{}" for those.

    Args:
        agent_wallet_address: The provider agent's wallet address (from requirement.agentWalletAddress).
    """
    agent = acp_client.get_agent(agent_wallet_address)
    if not agent:
        return json.dumps({"error": f"Agent not found: {agent_wallet_address}"})
    offerings_list = []
    for i, off in enumerate(agent.job_offerings):
        offerings_list.append({
            "index": i,
            "name": off.name,
            "price": off.price,
            "requirement_schema": off.requirement,
        })
    return json.dumps({
        "agent_name": agent.name,
        "agent_description": agent.description or "",
        "offerings": offerings_list,
    }, indent=2)


def initiate_evaluation_job(
    agent_wallet_address: str,
    job_offering_index: int,
    service_requirement_json: str,
    expected_outcome: str,
    parent_job_id: int,
) -> str:
    """
    Initiate one evaluation job with the agent (as buyer). For each offering: call at least 2 times with expected_outcome "accept" (valid requirement) to evaluate deliverable quality. When the schema has fields that can be invalid (e.g. token_symbol, news_category, type), call 2 times with expected_outcome "reject" using invalid values (e.g. token_symbol "casdcasd", wrong enum) so the provider should reject — 2 accept and 2 reject when reject is testable, not one each. Offerings with no or empty schema need only 2 accept; use service_requirement_json "{}" when schema is empty.
    Child jobs are tracked for the parent; the runner will wait for them (via job queue), compile the report, and deliver.

    Args:
        agent_wallet_address: The provider agent's wallet address.
        job_offering_index: Index of the job offering (0 to len(offerings)-1).
        service_requirement_json: JSON string of the service requirement payload (valid for accept; for reject use invalid values e.g. fake token_symbol, invalid category, invalid type).
        expected_outcome: "accept" or "reject" — whether we expect the provider to accept or reject this job.
        parent_job_id: The parent (evaluation) job id; used to track children and deliver the report later.
    """
    agent = acp_client.get_agent(agent_wallet_address)
    if not agent:
        return json.dumps({"error": f"Agent not found: {agent_wallet_address}"})
    if not agent.job_offerings:
        return json.dumps({"error": "Agent has no job offerings"})
    if job_offering_index < 0 or job_offering_index >= len(agent.job_offerings):
        return json.dumps({"error": f"job_offering_index must be 0..{len(agent.job_offerings) - 1}"})
    if expected_outcome not in ("accept", "reject"):
        return json.dumps({"error": "expected_outcome must be 'accept' or 'reject'"})
    try:
        service_requirement = json.loads(service_requirement_json)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid service_requirement_json: {e}"})
    offering = agent.job_offerings[job_offering_index]
    try:
        logger.info(
            "initiate_evaluation_job: calling offering.initiate_job (agent=%s, offering_index=%s, parent=%s)",
            agent_wallet_address[:10] + "..",
            job_offering_index,
            parent_job_id,
        )
        job_id = offering.initiate_job(
            service_requirement=service_requirement,
            evaluator_address=acp_client.agent_wallet_address,
            expired_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
        logger.info("initiate_evaluation_job: job_id=%s initiated", job_id)
        offering_name = getattr(offering, "name", None) or f"offering_{job_offering_index}"
        with _evaluation_children_lock:
            _evaluation_children.setdefault(parent_job_id, []).append({
                "job_id": job_id,
                "expected_outcome": expected_outcome,
                "offering_name": offering_name,
            })
        return json.dumps({"job_id": job_id, "expected_outcome": expected_outcome})
    except Exception as e:
        logger.exception("initiate_evaluation_job failed: %s", e)
        return json.dumps({"error": str(e)})


def _deliver_evaluation_report(parent_job_id: int, report: Union[Dict[str, Any], str]) -> str:
    """Internal: deliver compiled report to parent job. Parent job delivery by us only happens in TRANSACTION phase (we are the provider)."""
    job = _get_job_or_none(parent_job_id)
    if job is None:
        try:
            job = acp_client.get_job_by_onchain_id(parent_job_id)
        except ACPApiError:
            return f"Parent job {parent_job_id} not found."
    if job.phase != ACPJobPhase.TRANSACTION:
        return f"Parent job {parent_job_id} is in {job.phase.name}; delivery only in TRANSACTION phase."
    try:
        job.deliver(report)
        return f"Evaluation report delivered to parent job {parent_job_id}."
    except ValueError as e:
        return f"Deliver failed: {e}"


def evaluate_job_deliverable(job_id: int, accept: bool, reason: str) -> str:
    """
    Evaluate a job deliverable (child jobs in EVALUATION phase). We are the evaluator; call job.evaluate(accept, reason).
    Use when a job is in EVALUATION phase and you have evaluated the deliverable against the requirement.

    Args:
        job_id: The on-chain job id.
        accept: True to accept the deliverable, False to reject.
        reason: Explanation for the evaluation.
    """
    job = _get_job_or_none(job_id)
    if job is None:
        return f"Job {job_id} not found. Cannot evaluate."
    if job.phase != ACPJobPhase.EVALUATION:
        return f"Job {job_id} is in {job.phase.name}; evaluate_job_deliverable only for EVALUATION phase."
    try:
        job.evaluate(accept=accept, reason=reason)
        return f"Job {job_id} deliverable {'accepted' if accept else 'rejected'}. {reason}"
    except ValueError as e:
        return f"Job {job_id} evaluate failed: {e}"


def _is_tracked_child_job(job_id: int) -> bool:
    """True if this job id is a child we initiated (listed in _evaluation_children for some parent)."""
    with _evaluation_children_lock:
        for entries in _evaluation_children.values():
            if any(e.get("job_id") == job_id for e in entries):
                return True
    return False


def _summary_for_report(value: Any, max_len: int = 500) -> Optional[str]:
    """Format requirement or deliverable for report; truncate if too long."""
    if value is None:
        return None
    if isinstance(value, dict):
        s = json.dumps(value, ensure_ascii=False)
    else:
        s = str(value)
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def _get_evaluator_rejection_reason(job: ACPJob) -> Optional[str]:
    """Get the reason we (evaluator) gave when rejecting a deliverable: signed_reason on the delivery memo we signed."""
    for m in getattr(job, "memos", []) or []:
        if getattr(m, "next_phase", None) == ACPJobPhase.COMPLETED and getattr(m, "signed_reason", None):
            return m.signed_reason
    return None


def _evaluation_reason(expected: str, phase: ACPJobPhase, passed: bool, evaluator_reason: Optional[str] = None) -> str:
    """Human-readable reason why the job passed or failed the evaluation check. If we rejected the deliverable, evaluator_reason is the detailed reason we gave."""
    phase_name = phase.name if hasattr(phase, "name") else str(phase)
    if expected == "accept":
        if passed:
            if phase == ACPJobPhase.COMPLETED:
                return "Pass: expected accept; job COMPLETED. Provider accepted the requirement and delivered; deliverable was evaluated and accepted."
            if phase in (ACPJobPhase.NEGOTIATION, ACPJobPhase.TRANSACTION):
                return f"Pass: expected accept; job in {phase_name}. Provider accepted the requirement; job is in progress."
            return f"Pass: expected accept; job in {phase_name}. Provider accepted; awaiting completion."
        if evaluator_reason:
            return f"Fail: expected accept but deliverable was rejected by evaluator.\n\nEvaluator reason: {evaluator_reason}"
        return f"Fail: expected accept but job ended in {phase_name}. Provider rejected or job did not complete as expected."
    else:  # expected == "reject"
        if passed and phase == ACPJobPhase.REJECTED:
            return "Pass: expected reject; job REJECTED. Provider correctly rejected the invalid requirement."
        if not passed:
            return f"Fail: expected reject but job reached {phase_name}. Provider accepted when we expected rejection (invalid input should have been rejected)."
        return f"Unexpected outcome: expected reject, phase {phase_name}."


def _aggregate_results_by_offering(results: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group result dicts by offering_name. Keys are offering names; use 'unknown' for missing. Result items omit offering_name since the key carries it."""
    by_offering: Dict[str, List[Dict[str, Any]]] = {}
    for r in results:
        name = r.get("offering_name") or "unknown"
        item = {k: v for k, v in r.items() if k != "offering_name"}
        by_offering.setdefault(name, []).append(item)
    return by_offering


def _format_detailed_report(results: List[Dict[str, Any]], summary: str) -> str:
    """Build a human-readable detailed report string for delivery, aggregated by job offering name."""
    by_offering = _aggregate_results_by_offering(results)
    lines = [
        "Graduation Evaluation Result",
        "The evaluation has concluded with a " + summary + " pass rate.",
        "",
    ]
    for offering_name in sorted(by_offering.keys()):
        offering_results = by_offering[offering_name]
        passed_count = sum(1 for r in offering_results if r.get("passed"))
        lines.append(f"--- {offering_name} ---")
        lines.append(f"  Passed: {passed_count}/{len(offering_results)}")
        lines.append("")
        for r in offering_results:
            job_id = r.get("job_id")
            expected = r.get("expected_outcome", "")
            actual_phase = r.get("actual_phase", "unknown")
            passed = r.get("passed", False)
            reason = r.get("reason", "")
            requirement = r.get("requirement")
            deliverable_summary = r.get("deliverable_summary")
            status_line = f"  Job ID {job_id}: {'Passed' if passed else 'Failed'} (Status: {actual_phase})"
            lines.append(status_line)
            lines.append(f"    Expected: {expected}; Actual phase: {actual_phase}.")
            lines.append(f"    Reason: {reason}")
            if requirement:
                lines.append(f"    Requirement: {requirement}")
            if deliverable_summary is not None:
                lines.append(f"    Deliverable summary: {deliverable_summary}")
            lines.append("")
        lines.append("")
    return "\n".join(lines).rstrip()


def _wait_for_children_and_deliver_report(parent_job_id: int) -> None:
    """Wait until all tracked child jobs are terminal (fetch phase by id for fresh data; terminal jobs may not be in poll loop's active_jobs). Compile report, deliver to parent, clear children. Do not mutate _job_queue."""
    with _evaluation_children_lock:
        children = list(_evaluation_children.get(parent_job_id, []))
    if not children:
        return
    max_wait_polls = 120  # 120 * POLL_INTERVAL_SECONDS = ~40 min
    for _ in range(max_wait_polls):
        results: List[Dict[str, Any]] = []
        all_terminal = True
        for entry in children:
            job_id = entry["job_id"]
            expected = entry["expected_outcome"]
            offering_name = entry.get("offering_name") or f"offering_{entry.get('job_offering_index', '?')}"
            # Fetch by id so we get current phase; terminal jobs may not be in _job_queue (get_active_jobs often excludes them)
            try:
                child_job = acp_client.get_job_by_onchain_id(job_id)
                phase = child_job.phase
            except ACPApiError:
                phase = None
            if phase is None:
                results.append({
                    "job_id": job_id, "expected_outcome": expected, "actual_phase": "unknown", "passed": False,
                    "reason": "Could not fetch job phase.",
                    "requirement": None, "deliverable_summary": None, "offering_name": offering_name,
                })
                all_terminal = False
                continue
            phase_name = phase.name if hasattr(phase, "name") else str(phase)
            if phase not in _TERMINAL_PHASES:
                all_terminal = False
                results.append({
                    "job_id": job_id, "expected_outcome": expected, "actual_phase": phase_name, "passed": False,
                    "reason": f"Job not yet terminal (current phase: {phase_name}).",
                    "requirement": _summary_for_report(getattr(child_job, "requirement", None), max_len=500),
                    "deliverable_summary": None, "offering_name": offering_name,
                })
                continue
            passed = (
                (expected == "reject" and phase == ACPJobPhase.REJECTED)
                or (expected == "accept" and phase in (ACPJobPhase.COMPLETED, ACPJobPhase.NEGOTIATION, ACPJobPhase.TRANSACTION, ACPJobPhase.EVALUATION))
            )
            reason = _evaluation_reason(expected, phase, passed)
            results.append({
                "job_id": job_id,
                "expected_outcome": expected,
                "actual_phase": phase_name,
                "passed": passed,
                "reason": reason,
                "requirement": _summary_for_report(getattr(child_job, "requirement", None), max_len=500),
                "deliverable_summary": _summary_for_report(getattr(child_job, "deliverable", None), max_len=800) if phase == ACPJobPhase.COMPLETED else ("N/A (job rejected)" if phase == ACPJobPhase.REJECTED else None),
                "offering_name": offering_name,
            })
        if all_terminal:
            parent_job = _get_job_or_none(parent_job_id)
            if parent_job is None:
                try:
                    parent_job = acp_client.get_job_by_onchain_id(parent_job_id)
                except ACPApiError:
                    parent_job = None
            if parent_job is not None and parent_job.phase == ACPJobPhase.TRANSACTION:
                summary_str = f"{sum(1 for r in results if r.get('passed'))}/{len(results)} passed"
                by_offering = _aggregate_results_by_offering(results)
                report = {
                    "test_results": by_offering,
                    "summary": summary_str,
                    "details": _format_detailed_report(results, summary_str),
                }
                _deliver_evaluation_report(parent_job_id, report)
                with _evaluation_children_lock:
                    _evaluation_children.pop(parent_job_id, None)
                    _parent_evaluation_started.discard(parent_job_id)
                logger.info("Evaluation report delivered for parent job %s", parent_job_id)
                return
            if all_terminal and (parent_job is None or parent_job.phase != ACPJobPhase.TRANSACTION):
                logger.warning("Parent %s: all children terminal but parent not in TRANSACTION (phase=%s); will not deliver.", parent_job_id, getattr(parent_job, "phase", None))
        time.sleep(POLL_INTERVAL_SECONDS)
    logger.error("Timeout waiting for child jobs of parent %s", parent_job_id)
    with _evaluation_children_lock:
        _evaluation_children.pop(parent_job_id, None)
        # Do NOT discard _parent_evaluation_started on timeout: ensure only one round of children per parent forever


def _evaluator_poll_loop() -> None:
    """Poll for active jobs; queue them and hand off each REQUEST-phase job to the ADK agent via runner.run(). Child-wait for parent TRANSACTION runs in a background thread so this loop keeps running and can pay child jobs (NEGOTIATION) and evaluate deliverables (EVALUATION)."""
    logger.info("Evaluator ACP polling started. Agent: %s", acp_client.agent_wallet_address)
    while True:
        try:
            logger.debug("Poll iteration: fetching active jobs...")
            active_jobs: List[ACPJob] = acp_client.get_active_jobs()
            with _job_queue_lock:
                for job in active_jobs:
                    _job_queue[job.id] = job
                # Merge API and socket jobs; deduplicate by job id (prefer API data when same id in both)
                by_id: Dict[int, ACPJob] = {j.id: j for j in active_jobs}
                for j in _job_queue.values():
                    if j.id not in by_id:
                        by_id[j.id] = j
                jobs_to_process = list(by_id.values())
            for job in jobs_to_process:
                # Parent REQUEST: we are provider (graduation request) — accept/reject only. Parent TRANSACTION: we are provider, client paid — start children evaluation flow. Child EVALUATION: we are evaluator — evaluate deliverable (job.evaluate). Client NEGOTIATION: we are client — pay and accept. We do NOT accept/reject child jobs (provider of children does that).
                is_parent_request = job.provider_address == acp_client.agent_wallet_address and job.phase == ACPJobPhase.REQUEST
                is_parent_transaction = job.provider_address == acp_client.agent_wallet_address and job.phase == ACPJobPhase.TRANSACTION
                is_evaluator_evaluation = job.evaluator_address == acp_client.agent_wallet_address and job.phase == ACPJobPhase.EVALUATION
                is_client_negotiation = job.client_address == acp_client.agent_wallet_address and job.phase == ACPJobPhase.NEGOTIATION
                if not (is_parent_request or is_parent_transaction or is_evaluator_evaluation or is_client_negotiation):
                    continue
                # Only process child jobs (evaluator/client) that we initiated — ignore others not linked to any parent
                if (is_evaluator_evaluation or is_client_negotiation) and not _is_tracked_child_job(job.id):
                    continue
                # Only create one round of children per parent: skip parent TRANSACTION if we already started evaluation for this parent
                if is_parent_transaction:
                    with _evaluation_children_lock:
                        if job.id in _parent_evaluation_started:
                            continue
                        _parent_evaluation_started.add(job.id)
                try:
                    if is_client_negotiation:
                        if job.latest_memo and job.latest_memo.next_phase == ACPJobPhase.TRANSACTION:
                            job.pay_and_accept_requirement()
                            logger.info("Job %s: Paid and accepted requirement", job.id)
                        continue
                    with _job_sessions_lock:
                        session_id = _job_sessions.get(job.id)
                    if session_id is None:
                        async def create_session_for_job():
                            session = await session_service.create_session(
                                app_name=runner.app_name,
                                user_id="evaluator",
                                session_id=None,
                            )
                            return session.id

                        session_id = asyncio.run(create_session_for_job())
                        with _job_sessions_lock:
                            _job_sessions[job.id] = session_id
                        logger.info("Job %s: created session %s", job.id, session_id)
                    else:
                        logger.info("Job %s: reusing session %s", job.id, session_id)

                    if is_parent_request:
                        req_json = json.dumps(job.requirement) if isinstance(job.requirement, dict) else str(job.requirement)
                        prompt = (
                            f"Agent graduation request (you are the provider). job_id: {job.id}. "
                            f"requirement (use only what was passed in): {req_json}. "
                            "If requirement is invalid (not an object with agentName and agentWalletAddress), call reject_job. "
                            "Otherwise verify agent identity with verify_agent_identity, then call accept_job or reject_job to accept or reject the graduation request."
                        )
                    elif is_evaluator_evaluation:
                        req_json = json.dumps(job.requirement) if isinstance(job.requirement, dict) else str(job.requirement)
                        deliverable_str = str(job.deliverable) if job.deliverable is not None else "(none)"
                        prompt = (
                            f"Evaluate this job deliverable (EVALUATION phase). job_id: {job.id}. "
                            f"requirement: {req_json}. deliverable: {deliverable_str}. "
                            "Call evaluate_job_deliverable(job_id, accept, reason) to accept or reject the deliverable."
                        )
                    elif is_parent_transaction:
                        # Parent job in TRANSACTION (client paid): start children evaluation jobs; runner waits, compiles report, delivers
                        req_json = json.dumps(job.requirement) if isinstance(job.requirement, dict) else str(job.requirement)
                        prompt = (
                            f"Parent job {job.id} (you are the provider, client has paid — TRANSACTION phase). Run the evaluation flow. "
                            f"requirement (agent to evaluate): {req_json}. "
                            "1) Call get_agent_offerings(agent_wallet_address) with agentWalletAddress from requirement. "
                            "2) As soon as you have the offerings, you MUST call initiate_evaluation_job for each offering (do not reply with text instead). "
                            "For each offering: call initiate_evaluation_job at least 2 times with expected_outcome \"accept\" and valid service_requirement_json (use \"{}\" when the offering has no or empty requirement schema). "
                            "When the requirement schema has fields that can be invalid (e.g. token_symbol, news_category, type), call 2 times with expected_outcome \"reject\" using invalid values (e.g. token_symbol \"casdcasd\", wrong enum) so the provider should reject — 2 accept and 2 reject when reject is testable, not one each. Do not be lenient; always test reject when such fields exist. "
                            f"Use parent_job_id={job.id}. The runner will wait for child jobs, compile the report, and deliver."
                        )
                    content = types.UserContent(parts=[types.Part(text=prompt)])
                    events = runner.run(
                        user_id="evaluator",
                        session_id=session_id,
                        new_message=content,
                    )
                    for event in events:
                        _log_agent_event(event, job.id)
                    logger.info("Job %s: agent run finished", job.id)
                    if is_parent_transaction:
                        # Run child-wait in background so poll loop keeps running (to pay child jobs and evaluate deliverables)
                        def _run_wait_and_deliver(pid: int) -> None:
                            _wait_for_children_and_deliver_report(pid)
                            logger.info("Job %s: child wait finished, report delivered or timeout.", pid)

                        threading.Thread(
                            target=_run_wait_and_deliver,
                            args=(job.id,),
                            daemon=True,
                        ).start()
                        logger.info("Job %s: waiting for child jobs in background; poll loop continues (pay/evaluate children).", job.id)
                        # Sign first memo with next_phase REJECTED (accept job rejection)
                        job = acp_client.get_job_by_onchain_id(job.id)
                        rejected_memo = next(
                            (m for m in job.memos if m.next_phase == ACPJobPhase.REJECTED), None
                        )
                        if rejected_memo:
                            rejected_memo.sign(True, "accepts job rejection")
                except Exception as e:
                    logger.error("Error handing off job %s to agent: %s", job.id, e)
        except Exception as e:
            logger.error("Error in evaluator poll loop: %s", e)
        time.sleep(POLL_INTERVAL_SECONDS)


# Start polling in a non-daemon thread so the process stays alive when run directly (python agent.py).
# Daemon threads are killed when the main thread exits; non-daemon keeps the process running.
_poll_thread = threading.Thread(target=_evaluator_poll_loop, daemon=False)
_poll_thread.start()

root_agent = Agent(
    model=env.GEMINI_MODEL,
    name='acp_evaluator',
    description='Graduation evaluation agent: parent job accept/reject (REQUEST), children evaluation flow (TRANSACTION), child deliverable evaluation (EVALUATION).',
    instruction="""
    You are the graduation evaluation agent for the Virtuals Protocol Agent Commerce Protocol (ACP) network.
    You only handle parent (graduation) job acceptance/rejection. You do NOT accept or reject child jobs — only the provider of each child job does that. You are both evaluator and client for children; you initiate children and evaluate their deliverables.

    Parent job REQUEST (graduation request — you are the provider):
    1. Verify agent identity with verify_agent_identity(agent_wallet_address, agent_name).
    2. Accept with accept_job(job_id, reason) or reject with reject_job(job_id, reason).

    Child job EVALUATION phase: Evaluate the deliverable against the requirement. Call evaluate_job_deliverable(job_id, accept, reason) to accept or reject the deliverable.
    When the deliverable or requirement includes a URL, use the URL context tool to fetch and read the live page content before evaluating.
    When the deliverable is real-time or time-sensitive (e.g. current prices, news, market data), use the search tool to verify or contextualize it, then call evaluate_job_deliverable.
    You can combine both: use the search tool to find relevant results and URLs, then use the URL context tool to crawl and read those URLs before evaluating.

    Parent job TRANSACTION (client paid — you are the provider, run evaluation flow):
    1. Get agent from requirement (agentWalletAddress). Call get_agent_offerings(agent_wallet_address) to get agent name, description, and job offerings (each with index, name, requirement_schema, price).
    2. Immediately after get_agent_offerings returns, you MUST call initiate_evaluation_job for each offering (do not respond with text only). For each offering: call at least 2 times with expected_outcome "accept" and valid service_requirement_json (use "{}" when no or empty requirement schema). When the requirement schema has fields that can be invalid (e.g. token_symbol, symbol, ticker, enum), call 2 times with expected_outcome "reject" using invalid values (e.g. token_symbol "casdcasd", wrong enum) so the provider should reject — 2 accept and 2 reject when reject is testable, not one each. Do not be lenient; always test reject when such fields exist. Use parent_job_id from the prompt. The runner will wait for child jobs (via job queue), compile the report, and deliver to the parent job.

    When answering, always explain in detail the steps you have taken. Use JSON where appropriate.
    """,
    # ACP callables first; then UrlContextTool (live URL content) and GoogleSearchTool (real-time/time-sensitive deliverable evaluation). Class-based tools may trigger AFC warning but are required for evaluation.
    tools=[
        verify_agent_identity,
        accept_job,
        reject_job,
        evaluate_job_deliverable,
        get_agent_offerings,
        initiate_evaluation_job,
        UrlContextTool(),
        GoogleSearchTool(),
    ]
)

session_service = VertexAiSessionService(
    project=env.GOOGLE_CLOUD_PROJECT,
    location=env.AGENT_ENGINE_LOCATION,
    agent_engine_id=env.AGENT_ENGINE_ID
)

runner = Runner(
    app_name='acp_evaluator',
    agent=root_agent,
    session_service=session_service,
)

if __name__ == "__main__":
    # Run with ADK runner (interactive CLI): from this directory run:  adk run agent
    # When run as `python agent.py`, we keep the process alive so the poll thread keeps running.
    _poll_thread.join()
