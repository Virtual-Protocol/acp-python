# virtuals_acp/client.py
import json
import signal
import sys
import requests
import time
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple, Union, Dict, Any
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account
from eth_account.signers.local import LocalAccount
import socketio
import socketio.client

from virtuals_acp.exceptions import ACPApiError, ACPError
from virtuals_acp.models import  ACPJobPhase, MemoType, IACPAgent
from virtuals_acp.contract_manager import _ACPContractManager
from virtuals_acp.configs import ACPContractConfig, DEFAULT_CONFIG
from virtuals_acp.offering import ACPJobOffering
from virtuals_acp.job import ACPJob
from virtuals_acp.memo import ACPMemo

class VirtualsACP:
    def __init__(self, 
                 wallet_private_key: str, 
                 agent_wallet_address: Optional[str] = None, 
                 config: Optional[ACPContractConfig] = DEFAULT_CONFIG,
                 on_new_task: Optional[callable] = None,
                 on_evaluate: Optional[callable] = None):
        
        self.config = config
        self.w3 = Web3(Web3.HTTPProvider(config.rpc_url))

        if config.chain_env == "base-sepolia":
            self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

        if not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to RPC URL: {config.rpc_url}")

        self.signer_account: LocalAccount = Account.from_key(wallet_private_key)
        
        if agent_wallet_address:
            self._agent_wallet_address = Web3.to_checksum_address(agent_wallet_address)
        else:
            self._agent_wallet_address = self.signer_account.address
            # print(f"Warning: agent_wallet_address not provided, defaulting to signer EOA: {self._agent_wallet_address}")

        # Initialize the contract manager here
        self.contract_manager = _ACPContractManager(self.w3, config, wallet_private_key)
        self.acp_api_url = config.acp_api_url
        
        # Socket.IO setup
        self.on_new_task = on_new_task
        self.on_evaluate = on_evaluate or self._default_on_evaluate
        self.sio = socketio.Client()
        self._setup_socket_handlers()
        self._connect_socket()

    def _default_on_evaluate(self, job: ACPJob) -> Tuple[bool, str]:
        """Default handler for job evaluation events."""
        return True,"Succesful"
    
    def _on_room_joined(self, data):
        print('Connected to room', data)

    def _on_evaluate(self, data):
        if self.on_evaluate:
            print(f"Evaluating job {data}")
            try:
                memos = [ACPMemo(
                    id=memo["id"], 
                    type=int(memo["memoType"]),
                    content=memo["content"],
                    next_phase=memo["nextPhase"],
                ) for memo in data["memos"]]
                
                job = ACPJob(
                    acp_client=self,
                    id=data["id"],
                    provider_address=data["providerAddress"],
                    memos=memos,
                    phase=data["phase"],
                    price=data["price"]
                )
                self.on_evaluate(job)
            except Exception as e:
                print(f"Error in onEvaluate handler: {e}")

    def _on_new_task(self, data):
        if self.on_new_task:
            print("Received new task:", data["memos"])
            try:
                memos = [ACPMemo(
                    id=memo["id"], 
                    type=int(memo["memoType"]),
                    content=memo["content"],
                    next_phase=memo["nextPhase"],
                ) for memo in data["memos"]]
                
                
                job = ACPJob(
                    acp_client=self,
                    id=data["id"],
                    provider_address=data["providerAddress"],
                    memos=memos,
                    phase=data["phase"],
                    price=data["price"]
                )
                
                self.on_new_task(job)
            except Exception as e:
                print(f"Error in onNewTask handler: {e}")

    def _setup_socket_handlers(self) -> None:
        self.sio.on('roomJoined', self._on_room_joined)
        self.sio.on('onEvaluate', self._on_evaluate)
        self.sio.on('onNewTask', self._on_new_task)

    def _connect_socket(self) -> None:
        """Connect to the socket server with appropriate authentication."""
        auth_data = {}
        if self.on_new_task:
            auth_data['walletAddress'] = self.agent_address
            
        if self.on_evaluate != self._default_on_evaluate:
            auth_data['evaluatorAddress'] = self.agent_address

        try:
            self.sio.connect(
                self.acp_api_url,
                auth=auth_data,
            )
            
            def signal_handler(sig, frame):
                self.sio.disconnect()
                sys.exit(0)
                
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            
        except Exception as e:
            print(f"Failed to connect to socket server: {e}")

    def __del__(self):
        """Cleanup when the object is destroyed."""
        if hasattr(self, 'sio') and self.sio is not None:
            self.sio.disconnect()
        
    @property
    def agent_address(self) -> str:
        return self._agent_wallet_address

    @property
    def signer_address(self) -> str:
        return self.signer_account.address
    

    def browse_agents(self, keyword: str, cluster: Optional[str] = None) -> List[IACPAgent]:
        url = f"{self.acp_api_url}/agents?search={keyword}&filters[walletAddress][$notIn]={self.agent_address}"
        if cluster:
            url += f"&filters[cluster]={cluster}"
            
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            agents_data = data.get("data", [])
            agents = []
            for agent_data in agents_data:
                
                offerings = [
                    ACPJobOffering(
                        acp_client=self,
                        provider_address=agent_data["walletAddress"],
                        type=off["name"],
                        price=off["price"],
                        requirementSchema=off.get("requirementSchema", None)
                    )
                    for off in agent_data.get("offerings", [])
                ]
                
                agents.append(IACPAgent(
                    id=agent_data["id"],
                    name=agent_data.get("name"),
                    description=agent_data.get("description"),
                    wallet_address=Web3.to_checksum_address(agent_data["walletAddress"]),
                    offerings=offerings,
                    twitter_handle=agent_data.get("twitterHandle")
                ))
            return agents
        except requests.exceptions.RequestException as e:
            raise ACPApiError(f"Failed to browse agents: {e}")
        except Exception as e:
            raise ACPError(f"An unexpected error occurred while browsing agents: {e}")

    def initiate_job(
        self,
        provider_address: str,
        service_requirement: Union[Dict[str, Any], str],
        amount: float,
        evaluator_address: Optional[str] = None,
        expired_at: Optional[datetime] = None
    ) -> int:
        if expired_at is None:
            expired_at = datetime.now(timezone.utc) + timedelta(days=1)
        
        eval_addr = Web3.to_checksum_address(evaluator_address) if evaluator_address else self.agent_address
        
        job_id = None
        retry_count = 3
        retry_delay = 3
        
        tx_hash = self.contract_manager.create_job(
            self.agent_address, provider_address, eval_addr, expired_at
        )

        time.sleep(retry_delay) 
        for attempt in range(retry_count):
            try:
                response = self.contract_manager.validate_transaction(tx_hash['txHash'])
                data = response.get("data", {})
                if not data:
                    raise Exception("Invalid tx_hash!")
                
                if data.get("status") == "retry":
                    raise Exception("Transaction failed, retrying...")
                
                if data.get("status") == "failed":
                    break
                
                if data.get("status") == "success":
                    job_id = int(data.get("result").get("jobId"))
                    
                if job_id is not None and job_id != "":
                    break  
                
            except Exception as e:
                if (attempt == retry_count - 1):
                    print(f"Error in create_job function: {e}")
                if attempt < retry_count - 1:
                    time.sleep(retry_delay) 
                else:
                    raise
        
        if job_id is None or job_id == "":
            raise Exception("Failed to create job")
        
        amount_in_wei = self.w3.to_wei(amount, "ether")
        set_budget_tx_hash = self.contract_manager.set_budget(self.agent_address, job_id, amount_in_wei)
        time.sleep(10)
        
        self.contract_manager.create_memo(
            self.agent_address,
            job_id,
            service_requirement if isinstance(service_requirement, str) else json.dumps(service_requirement),
            MemoType.MESSAGE,
            is_secured=True,
            next_phase=ACPJobPhase.NEGOTIATION
        )
        print(f"Initial memo for job {job_id} created.")
        
        payload = {
            "jobId": job_id,
            "clientAddress": self.agent_address,
            "providerAddress": provider_address,
            "description": service_requirement,
            "expiredAt": expired_at.astimezone(timezone.utc).isoformat(),
            "evaluatorAddress": evaluator_address
        }
        
        if amount:
            payload["price"] = amount
        
        requests.post(
            self.acp_api_url,
            json=payload,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )
        return job_id

    def respond_to_job_memo(
        self,
        job_id: int, 
        memo_id: int, 
        accept: bool, 
        reason: Optional[str] = ""
    ) -> str:
        
        try:
            tx_hash = self.contract_manager.sign_memo(self.agent_address, memo_id, accept, reason or "")
            time.sleep(10)
            
            print(f"Responding to job {job_id} with memo {memo_id} and accept {accept} and reason {reason}")
            self.contract_manager.create_memo(
                self.agent_address,
                job_id,
                f"{reason if reason else f'Job {job_id} accepted.'}",
                MemoType.MESSAGE,
                is_secured=False,
                next_phase=ACPJobPhase.TRANSACTION
            )
            print(f"Responded to job {job_id} with memo {memo_id} and accept {accept} and reason {reason}")
            return tx_hash
        except Exception as e:
            print(f"Error in respond_to_job_memo: {e}")
            raise

    def pay_for_job(
        self, 
        job_id: int, 
        memo_id: int, 
        amount: Union[float, str], 
        reason: Optional[str] = ""
    ) -> Tuple[str, str, str, str]:
        
        amount_in_wei = self.w3.to_wei(amount, "ether")
        time.sleep(10)

        approve_tx_hash = self.contract_manager.approve_allowance(self.agent_address, amount_in_wei)
        time.sleep(10)

        sign_memo_tx_hash = self.contract_manager.sign_memo(self.agent_address, memo_id, True, reason or "")
        time.sleep(10)
        
        reason = f"{reason if reason else f'Job {job_id} paid.'}"
        print(f"Paid for job {job_id} with memo {memo_id} and amount {amount} and reason {reason}")

        return self.contract_manager.create_memo(
            self.agent_address,
            job_id,
            reason,
            MemoType.MESSAGE,
            is_secured=False,
            next_phase=ACPJobPhase.EVALUATION
        )

    def submit_job_deliverable(
        self, 
        job_id: int, 
        deliverable_content: str
    ) -> str:
        
        tx_hash = self.contract_manager.create_memo(
            self.agent_address,
            job_id,
            deliverable_content,
            MemoType.OBJECT_URL,
            is_secured=True,
            next_phase=ACPJobPhase.COMPLETED
        )
        # print(f"Deliverable submission tx: {tx_hash} for job {job_id}")
        return tx_hash

    def evaluate_job_delivery(
        self, 
        memo_id_of_deliverable: int, 
        accept: bool, 
        reason: Optional[str] = ""
    ) -> str:
        
        tx_hash = self.contract_manager.sign_memo(self.agent_address, memo_id_of_deliverable, accept, reason or "")
        print(f"Evaluation (signMemo) tx: {tx_hash} for deliverable memo ID {memo_id_of_deliverable} is {accept}")
        return tx_hash


    def get_active_jobs(self, page: int = 1, pageSize: int = 10) -> List["ACPJob"]:
        url = f"{self.acp_api_url}/jobs/active?pagination[page]={page}&pagination[pageSize]={pageSize}"
        headers = {
            "wallet-address": self.agent_address
        }
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            jobs = []
            
            for job in data.get("data", []):
                memos = []
                for memo in job.get("memos", []):
                    memos.append(ACPMemo(
                        id=memo.get("id"),
                        type=int(memo.get("memoType")),
                        content=memo.get("content"),
                        next_phase=int(memo.get("nextPhase")),
                    ))
                jobs.append(ACPJob(
                    acp_client=self,
                    id=job.get("id"),
                    provider_address=job.get("providerAddress"),
                    memos=memos,
                    phase=job.get("phase"),
                    price=job.get("price")
                ))
            return jobs 
        except Exception as e:
            raise ACPApiError(f"Failed to get active jobs: {e}")
        
        
    def get_completed_jobs(self, page: int = 1, pageSize: int = 10) -> List["ACPJob"]:
        url = f"{self.acp_api_url}/jobs/completed?pagination[page]=${page}&pagination[pageSize]=${pageSize}"
        headers = {
            "wallet-address": self.agent_address
        }
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            jobs = []
            
            for job in data.get("data", []):
                memos = []
                for memo in job.get("memos", []):
                    memos.append(ACPMemo(
                        id=memo.get("id"),
                        type=int(memo.get("memoType")),
                        content=memo.get("content"),
                        next_phase=int(memo.get("nextPhase"))
                    ))
                jobs.append(ACPJob(
                    acp_client=self,
                    id=job.get("id"),
                    provider_address=job.get("providerAddress"),
                    memos=memos,
                    phase=job.get("phase"),
                    price=job.get("price")
                ))
            return jobs
        except Exception as e:
            raise ACPApiError(f"Failed to get completed jobs: {e}")
        
    def get_cancelled_jobs(self, page: int = 1, pageSize: int = 10) -> List["ACPJob"]:
        url = f"{self.acp_api_url}/jobs/cancelled?pagination[page]=${page}&pagination[pageSize]=${pageSize}"
        headers = {
            "wallet-address": self.agent_address
        }
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            jobs = []
            
            for job in data.get("data", []):
                memos = []
                for memo in job.get("memos", []):
                    memos.append(ACPMemo(
                        id=memo.get("id"),
                        type=int(memo.get("memoType")),
                        content=memo.get("content"),
                        next_phase=int(memo.get("nextPhase"))
                    ))
                jobs.append(ACPJob(
                    acp_client=self,
                    id=job.get("id"),
                    provider_address=job.get("providerAddress"),
                    memos=memos,
                    phase=job.get("phase"),
                    price=job.get("price")
                ))
            return jobs
        except Exception as e:
            raise ACPApiError(f"Failed to get cancelled jobs: {e}")
        
    def get_job_by_onchain_id(self, onchain_job_id: int) -> "ACPJob":
        url = f"{self.acp_api_url}/jobs/{onchain_job_id}"
        headers = {
            "wallet-address": self.agent_address
        }
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            if data.get("error"):
                raise ACPApiError(data["error"]["message"])
            
            memos = []
            for memo in data.get("data", {}).get("memos", []):
                memos.append(ACPMemo(
                    id=memo.get("id"),
                    type=int(memo.get("memoType")),
                    content=memo.get("content"),
                    next_phase=int(memo.get("nextPhase"))
                ))
            return ACPJob(
                acp_client=self,
                id=data.get("data", {}).get("id"),
                provider_address=data.get("data", {}).get("providerAddress"),
                memos=memos,
                phase=data.get("data", {}).get("phase"),
                price=data.get("data", {}).get("price")
            )
        except Exception as e:
            raise ACPApiError(f"Failed to get job by onchain ID: {e}")
        
    def get_memo_by_id(self, onchain_job_id: int, memo_id: int) -> 'ACPMemo':
        url = f"{self.acp_api_url}/jobs/{onchain_job_id}/memos/{memo_id}"
        headers = {
            "wallet-address": self.agent_address
        }
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            if data.get("error"):
                raise ACPApiError(data["error"]["message"])
            
            return ACPMemo(
                id=data.get("data", {}).get("id"),
                type=int(data.get("data", {}).get("memoType")),
                content=data.get("data", {}).get("content"),
                next_phase=int(data.get("data", {}).get("nextPhase"))
            )
            
        except Exception as e:
            raise ACPApiError(f"Failed to get memo by ID: {e}")

    def get_agent(self, wallet_address: str) -> Optional[IACPAgent]:
        url = f"{self.acp_api_url}/agents?filters[walletAddress]={wallet_address}"
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            agents_data = data.get("data", [])
            if not agents_data:
                return None
                
            agent_data = agents_data[0]
            
            offerings = [
                ACPJobOffering(
                    acp_client=self,
                    provider_address=agent_data["walletAddress"], 
                    type=off["name"],
                    price=off["price"],
                    requirementSchema=off.get("requirementSchema", None)
                )
                for off in agent_data.get("offerings", [])
            ]
            
            return IACPAgent(
                id=agent_data["id"],
                name=agent_data.get("name"),
                description=agent_data.get("description"), 
                wallet_address=Web3.to_checksum_address(agent_data["walletAddress"]),
                offerings=offerings,
                twitter_handle=agent_data.get("twitterHandle")
            )
            
        except requests.exceptions.RequestException as e:
            raise ACPApiError(f"Failed to get agent: {e}")
        except Exception as e:
            raise ACPError(f"An unexpected error occurred while getting agent: {e}")

# Rebuild the AcpJob model after VirtualsACP is defined
ACPJob.model_rebuild()
ACPMemo.model_rebuild()
ACPJobOffering.model_rebuild()