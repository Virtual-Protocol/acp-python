import threading
import time
import json

from virtuals_acp import VirtualsACP, ACPJob, ACPJobPhase
from virtuals_acp.env import EnvSettings

from dotenv import load_dotenv
load_dotenv(override=True)

def seller(use_thread_lock: bool = True):
    env = EnvSettings()

    if env.WHITELISTED_WALLET_PRIVATE_KEY is None:
        raise ValueError("WHITELISTED_WALLET_PRIVATE_KEY is not set")
    if env.SELLER_AGENT_WALLET_ADDRESS is None:
        raise ValueError("SELLER_AGENT_WALLET_ADDRESS is not set")
    if env.SELLER_ENTITY_ID is None:
        raise ValueError("SELLER_ENTITY_ID is not set")

    job_queue = []
    job_queue_lock = threading.Lock()
    job_event = threading.Event()

    def safe_append_job(job):
        if use_thread_lock:
            print(f"[safe_append_job] Acquiring lock to append job {job.id}")
            with job_queue_lock:
                print(f"[safe_append_job] Lock acquired, appending job {job.id} to queue")
                job_queue.append(job)
        else:
            job_queue.append(job)

    def safe_pop_job():
        if use_thread_lock:
            print(f"[safe_pop_job] Acquiring lock to pop job")
            with job_queue_lock:
                if job_queue:
                    job = job_queue.pop(0)
                    print(f"[safe_pop_job] Lock acquired, popped job {job.id}")
                    return job
                else:
                    print("[safe_pop_job] Queue is empty after acquiring lock")
        else:
            if job_queue:
                job = job_queue.pop(0)
                print(f"[safe_pop_job] Popped job {job.id} without lock")
                return job
            else:
                print("[safe_pop_job] Queue is empty (no lock)")
        return None

    def job_worker():
        while True:
            job_event.wait()
            while True:
                job = safe_pop_job()
                if not job:
                    break
                try:
                    process_job(job)
                    time.sleep(2)
                except Exception as e:
                    print(f"\u274c Error processing job: {e}")

            if use_thread_lock:
                with job_queue_lock:
                    if not job_queue:
                        job_event.clear()
            else:
                if not job_queue:
                    job_event.clear()

    def on_new_task(job: ACPJob):
        print(f"[on_new_task] Received job {job.id} (phase: {job.phase})")
        safe_append_job(job)
        job_event.set()

    def process_job(job: ACPJob):
        if job.phase == ACPJobPhase.REQUEST:
            for memo in job.memos:
                if memo.next_phase == ACPJobPhase.NEGOTIATION:
                    job.respond(True)
                    break
        elif job.phase == ACPJobPhase.TRANSACTION:
            for memo in job.memos:
                if memo.next_phase == ACPJobPhase.EVALUATION:
                    print("Delivering job", job)
                    delivery_data = {
                        "type": "url",
                        "value": "https://example.com"
                    }
                    job.deliver(json.dumps(delivery_data))
                    break
        elif job.phase == ACPJobPhase.COMPLETED:
            print("Job completed", job)
        elif job.phase == ACPJobPhase.REJECTED:
            print("Job rejected", job)

    threading.Thread(target=job_worker, daemon=True).start()

    # Initialize the ACP client
    acp = VirtualsACP(
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
