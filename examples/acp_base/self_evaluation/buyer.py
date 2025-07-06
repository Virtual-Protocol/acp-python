import threading
import json
from datetime import datetime, timedelta
from typing import Optional

from virtuals_acp.client import VirtualsACP
from virtuals_acp.job import ACPJob
from virtuals_acp.models import ACPAgentSort, ACPJobPhase
from virtuals_acp.env import EnvSettings
from dotenv import load_dotenv

load_dotenv(override=True)

def buyer(use_thread_lock: bool = True):
    env = EnvSettings()

    if env.WHITELISTED_WALLET_PRIVATE_KEY is None:
        raise ValueError("WHITELISTED_WALLET_PRIVATE_KEY is not set")
    if env.BUYER_AGENT_WALLET_ADDRESS is None:
        raise ValueError("BUYER_AGENT_WALLET_ADDRESS is not set")
    if env.BUYER_ENTITY_ID is None:
        raise ValueError("BUYER_ENTITY_ID is not set")

    job_queue = []
    job_queue_lock = threading.Lock()
    job_event = threading.Event()

    def safe_append_job(job: ACPJob):
        if use_thread_lock:
            print("[append] Acquiring lock to append job")
            with job_queue_lock:
                job_queue.append(job)
                print(f"[append] Job {job.id} added. Queue size: {len(job_queue)}")
        else:
            job_queue.append(job)
            print(f"[append] (No lock) Job {job.id} added. Queue size: {len(job_queue)}")

    def safe_pop_job() -> Optional[ACPJob]:
        if use_thread_lock:
            print("[pop] Acquiring lock to pop job")
            with job_queue_lock:
                if job_queue:
                    job = job_queue.pop(0)
                    print(f"[pop] Job {job.id} popped. Queue size: {len(job_queue)}")
                    return job
                print("[pop] Queue empty.")
        else:
            if job_queue:
                job = job_queue.pop(0)
                print(f"[pop] (No lock) Job {job.id} popped. Queue size: {len(job_queue)}")
                return job
            print("[pop] (No lock) Queue empty.")
        return None

    def job_worker():
        print("[worker] Job worker started, waiting for tasks.")
        while True:
            job_event.wait()
            print("[worker] job_event triggered")

            job = safe_pop_job()
            while job:
                process_job(job)
                job = safe_pop_job()

            job_event.clear()
            print("[worker] Queue empty. Waiting for next task.")

    def on_new_task(job: ACPJob):
        print(f"[on_new_task] New job received: {job.id}")
        safe_append_job(job)
        job_event.set()

    def on_evaluate(job: ACPJob):
        print("Evaluation function called", job.memos)
        for memo in job.memos:
            if memo.next_phase == ACPJobPhase.COMPLETED:
                job.evaluate(True)
                print(f"[evaluate] Job {job.id} evaluated as accepted")
                break

    def process_job(job: ACPJob):
        print(f"[process] Processing job: {job.id}")
        if job.phase == ACPJobPhase.NEGOTIATION:
            for memo in job.memos:
                if memo.next_phase == ACPJobPhase.TRANSACTION:
                    print(f"[process] Paying job {job.id}")
                    job.pay(job.price)
                    return
        elif job.phase == ACPJobPhase.COMPLETED:
            print(f"[process] Job completed: {job.id}")
        elif job.phase == ACPJobPhase.REJECTED:
            print(f"[process] Job rejected: {job.id}")
        else:
            print(f"[process] No action needed for job {job.id}")

    acp = VirtualsACP(
        wallet_private_key=env.WHITELISTED_WALLET_PRIVATE_KEY,
        agent_wallet_address=env.BUYER_AGENT_WALLET_ADDRESS,
        on_new_task=on_new_task,
        on_evaluate=on_evaluate,
        entity_id=env.BUYER_ENTITY_ID
    )

    threading.Thread(target=job_worker, daemon=True).start()

    relevant_agents = acp.browse_agents(
        keyword="devrel_seller",
        sort_by=[
            ACPAgentSort.SUCCESSFUL_JOB_COUNT,
            ACPAgentSort.IS_ONLINE
        ],
        rerank=True,
        top_k=5,
        graduated=False
    )

    print(f"Relevant agents: {relevant_agents}")

    chosen_agent = relevant_agents[0]
    chosen_job_offering = chosen_agent.offerings[0]

    job_id = chosen_job_offering.initiate_job(
        service_requirement={"question": "What is ethermage buying now"},
        evaluator_address=env.BUYER_AGENT_WALLET_ADDRESS,
        expired_at=datetime.now() + timedelta(days=1)
    )

    print(f"Job {job_id} initiated")
    print("🟢 Listening for next steps...")
    threading.Event().wait()

if __name__ == "__main__":
    buyer(use_thread_lock=True)
