import json

from dotenv import load_dotenv

from virtuals_acp.client import VirtualsACP
from virtuals_acp.contract_clients.contract_client_v2 import ACPContractClientV2
from virtuals_acp.env import EnvSettings
from virtuals_acp.job import ACPJob
from virtuals_acp.memo import ACPMemo
from virtuals_acp.models import IACPAgent

load_dotenv(override=True)


def subsection(title: str):
    print(f"\n--- {title} ---")

def _serialize_memo(memo: ACPMemo) -> dict:
    return memo.model_dump(
        exclude={"contract_client"}
    )

def _serialize_job(job: ACPJob) -> dict:
    return job.model_dump(
        exclude={
            "acp_client": True,
            "memos": {
                "__all__": {"contract_client"}
            },
        }
    )

def _serialize_jobs(jobs: list[ACPJob]) -> list[dict]:
    return [
        _serialize_job(job)
        for job in jobs
    ]

def _serialize_agent(agent: IACPAgent) -> dict:
    return {
        "id": agent.id,
        "document_id": agent.document_id,
        "name": agent.name,
        "description": agent.description,
        "wallet_address": agent.wallet_address,
        "is_virtual_agent": agent.is_virtual_agent,
        "profile_pic": agent.profile_pic,
        "category": agent.category,
        "token_address": agent.token_address,
        "owner_address": agent.owner_address,
        "cluster": agent.cluster,
        "twitter_handle": agent.twitter_handle,
        "jobs": [
            o.model_dump(
                exclude={
                    "acp_client",
                    "contract_client"
                }
            )
            for o in agent.job_offerings
        ],
        "resources": [
            r.model_dump()
            for r in agent.resources
        ],
        "symbol": agent.symbol,
        "metrics": agent.metrics,
        "contract_address": agent.contract_address
    }


def test_helper_functions():
    print("\n" + "=" * 60)
    print("🔹 ACP Helper Functions Test")
    print("=" * 60 + "\n")

    print("Initializing ACP client...\n")

    env = EnvSettings()

    acp_client = VirtualsACP(
        acp_contract_clients=ACPContractClientV2(
            wallet_private_key=env.WHITELISTED_WALLET_PRIVATE_KEY,
            agent_wallet_address=env.BUYER_AGENT_WALLET_ADDRESS,
            entity_id=env.BUYER_ENTITY_ID,
        ),
    )

    # ---------------- ACTIVE JOBS ----------------
    subsection("Active Jobs")
    active_jobs = acp_client.get_active_jobs(page=1, page_size=3)
    print("\n🔵 Active Jobs:")
    print(
        json.dumps(
            _serialize_jobs(active_jobs),
            indent=2,
        ) if active_jobs
        else "No active jobs found."
    )

    # ---------------- COMPLETED JOBS ----------------
    subsection("Completed Jobs")
    completed_jobs = acp_client.get_completed_jobs(page=1, page_size=3)
    print("\n✅ Completed Jobs:")
    print(
        json.dumps(
            _serialize_jobs(completed_jobs),
            indent=2
        ) if completed_jobs
        else "No completed jobs found."
    )

    if completed_jobs:
        onchain_job_id = completed_jobs[0].id
        if onchain_job_id:
            job = acp_client.get_job_by_onchain_id(onchain_job_id=onchain_job_id)
            print(f"\n📄 Job Details (Job ID: {onchain_job_id}):")
            print(json.dumps(_serialize_job(job), indent=2))

            memos = completed_jobs[0].memos
            if memos:
                memo_id = memos[0].id
                memo = acp_client.get_memo_by_id(
                    onchain_job_id=onchain_job_id,
                    memo_id=memo_id,
                )
                print(f"\n📝 Memo Details (Job ID: {onchain_job_id}, Memo ID: {memo_id}):")
                print(json.dumps(_serialize_memo(memo), indent=2))
            else:
                print("\n⚠️ No memos found for the completed job.")

    # ---------------- CANCELLED JOBS ----------------
    subsection("Cancelled Jobs")
    cancelled_jobs = acp_client.get_cancelled_jobs(page=1, page_size=3)
    print("\n❌ Cancelled Jobs:")
    print(
        json.dumps(
            _serialize_jobs(cancelled_jobs),
            indent=2,
        )
        if cancelled_jobs
        else "No cancelled jobs found."
    )

    # ---------------- PENDING MEMO JOBS ----------------
    subsection("Pending Memo Jobs")
    pending_memo_jobs = acp_client.get_pending_memo_jobs(page=1, page_size=3)

    print(
        _serialize_jobs(pending_memo_jobs) if pending_memo_jobs
        else "No jobs with pending memos found."
    )

    # ---------------- AGENT INFO ----------------
    subsection("Agent Info")
    agent_wallet_address = acp_client.wallet_address
    agent = acp_client.get_agent(agent_wallet_address)
    print(
        json.dumps(
            _serialize_agent(agent),
            indent=2
        ) if agent
        else f"No agent with wallet address {agent_wallet_address} found."
    )


if __name__ == "__main__":
    try:
        test_helper_functions()
        print("\n✨ Test completed successfully")
    except Exception as e:
        print("\n❌ Error in helper functions test:")
        raise e
