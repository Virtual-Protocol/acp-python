import threading
import json
from typing import Optional
from virtuals_acp import VirtualsACP, ACPJob, ACPJobPhase
from virtuals_acp.env import EnvSettings
from dotenv import load_dotenv

load_dotenv(override=True)

def seller(use_thread_lock: bool = True):
    env = EnvSettings()

    if env.WHITELISTED_WALLET_PRIVATE_KEY is None:
        raise ValueError("WHITELISTED_WALLET_PRIVATE_KEY is not set")
    if env.SELLER_ENTITY_ID is None:
        raise ValueError("SELLER_ENTITY_ID is not set")

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

    def process_job(job: ACPJob):
        print(f"[process] Processing job: {job.id}")
        if job.phase == ACPJobPhase.REQUEST:
            for memo in job.memos:
                if memo.next_phase == ACPJobPhase.NEGOTIATION:
                    print(f"[process] Responding to job {job.id}")
                    job.respond(True)
                    return
        elif job.phase == ACPJobPhase.TRANSACTION:
            for memo in job.memos:
                if memo.next_phase == ACPJobPhase.EVALUATION:
                    print(f"[process] Delivering job {job.id}")
                    delivery_data = {
                        "type": "url",
                        "value": "https://example.com"
                    }
                    job.deliver(json.dumps(delivery_data))
                    return
        print(f"[process] No action needed for job {job.id}")

    VirtualsACP(
        wallet_private_key=env.WHITELISTED_WALLET_PRIVATE_KEY,
        agent_wallet_address=env.SELLER_AGENT_WALLET_ADDRESS,
        on_new_task=on_new_task,
        entity_id=env.SELLER_ENTITY_ID
    )

    threading.Thread(target=job_worker, daemon=True).start()
    print("🟢 Seller agent running. Awaiting tasks...")
    threading.Event().wait()

if __name__ == "__main__":
    seller(use_thread_lock=True)
