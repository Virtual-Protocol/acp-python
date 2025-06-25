# virtuals_acp/client.py
import json
import signal
import sys
import threading
import requests
import time
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple, Union, Dict, Any, Callable
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account
from eth_account.signers.local import LocalAccount
import socketio
import socketio.client

from virtuals_acp.exceptions import (
    ACPApiError, 
    ACPError, 
    ACPRPCConnectionError,
    ACPSocketConnectionError,
    ACPInvalidPrivateKeyError,
    ACPJobCreationError,
    ACPContractLogParsingError,
    ACPApiRequestError,
    ACPJobNotFoundError,
    ACPMemoNotFoundError,
    ACPAgentNotFoundError
)
from virtuals_acp.models import  ACPAgentSort, ACPJobPhase, MemoType, IACPAgent
from virtuals_acp.contract_manager import _ACPContractManager
from virtuals_acp.configs import ACPContractConfig, DEFAULT_CONFIG
from virtuals_acp.offering import ACPJobOffering
from virtuals_acp.job import ACPJob
from virtuals_acp.memo import ACPMemo

class VirtualsACP:
    """
    VirtualsACP is the main client for interacting with the ACP (Agent Communication Protocol) platform.
    
    This client provides a comprehensive interface for:
    - Discovering and browsing agents on the platform
    - Creating and managing jobs between clients and service providers
    - Real-time communication via WebSocket connections
    - Blockchain transaction management for payments and contracts
    - Job lifecycle management (initiation, negotiation, execution, evaluation)
    
    The client handles both on-chain interactions (via smart contracts) and off-chain 
    communication (via API and WebSocket connections) seamlessly.
    
    Attributes:
        config (ACPContractConfig): Network and contract configuration
        w3 (Web3): Web3 instance for blockchain interactions
        entity_id (int): Unique entity identifier on the platform
        contract_manager (_ACPContractManager): Handles smart contract interactions
        acp_api_url (str): Base URL for ACP API endpoints
        sio (socketio.Client): WebSocket client for real-time communication
    """
    
    def __init__(self, 
                 wallet_private_key: str, 
                 entity_id: int,
                 agent_wallet_address: Optional[str] = None, 
                 config: ACPContractConfig = DEFAULT_CONFIG,
                 on_new_task: Optional[Callable] = None,
                 on_evaluate: Optional[Callable] = None):
        """
        Initialize the VirtualsACP client.
        
        Args:
            wallet_private_key (str): Private key for signing transactions (without 0x prefix)
            entity_id (int): Unique entity identifier registered on the platform
            agent_wallet_address (Optional[str], optional): Wallet address for the agent. 
                If not provided, derives from private key. Defaults to None.
            config (ACPContractConfig, optional): Network configuration. 
                Defaults to DEFAULT_CONFIG.
            on_new_task (Optional[Callable], optional): Callback function called when 
                receiving new job assignments. Function signature: (job: ACPJob) -> None. 
                Defaults to None.
            on_evaluate (Optional[Callable], optional): Callback function called when 
                evaluation is required. Function signature: (job: ACPJob) -> Tuple[bool, str]. 
                Defaults to None.
        
        Raises:
            ConnectionError: If unable to connect to the specified RPC URL
            ValueError: If private key format is invalid
        """
        
        self.config = config
        self.w3 = Web3(Web3.HTTPProvider(config.rpc_url))
        self.entity_id = entity_id

        if config.chain_env == "base-sepolia":
            self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

        if not self.w3.is_connected():
            raise ACPRPCConnectionError(f"Failed to connect to RPC URL: {config.rpc_url}")

        try:
            self.signer_account: LocalAccount = Account.from_key(wallet_private_key)
        except Exception as e:
            raise ACPInvalidPrivateKeyError(f"Invalid private key format: {e}")
        
        if agent_wallet_address:
            self._agent_wallet_address = Web3.to_checksum_address(agent_wallet_address)
        else:
            self._agent_wallet_address = self.signer_account.address
            # print(f"Warning: agent_wallet_address not provided, defaulting to signer EOA: {self._agent_wallet_address}")

        # Initialize the contract manager here
        self.contract_manager = _ACPContractManager(self.w3, self._agent_wallet_address, entity_id, config, wallet_private_key)
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
        print('Connected to room', data)  # Send acknowledgment back to server
        return True

    def _on_evaluate(self, data):
        print('--------------------------------')
        print(f"Evaluating job {data}")
        print('--------------------------------')
        if self.on_evaluate:
            print(f"Evaluating job {data}")
            try:
                threading.Thread(target=self.handle_evaluate, args=(data,)).start()
                return True
            except Exception as e:
                print(f"Error in onEvaluate handler: {e}")
                return False

    def _on_new_task(self, data):
        if self.on_new_task:
            try:
                threading.Thread(target=self.handle_new_task, args=(data,)).start()
                return True
            except Exception as e:
                print(f"Error in onNewTask handler: {e}")
                return False
    def handle_new_task(self, data) -> None:
        memos = [ACPMemo(
                    id=memo["id"], 
                    type=MemoType(int(memo["memoType"])),
                    content=memo["content"],
                    next_phase=memo["nextPhase"],
                ) for memo in data["memos"]]
                
                
        job = ACPJob(
                    acp_client=self,
                    id=data["id"],
                    provider_address=data["providerAddress"],
                    client_address=data["clientAddress"],
                    evaluator_address=data["evaluatorAddress"],
                    memos=memos,
                    phase=data["phase"],
                    price=data["price"]
                )
        print(f"Received new task: {job}")
        if self.on_new_task:
            self.on_new_task(job)
        
    def handle_evaluate(self, data) -> None:
        memos = [ACPMemo(
                    id=memo["id"], 
                    type=MemoType(int(memo["memoType"])),
                    content=memo["content"],
                    next_phase=memo["nextPhase"],
                ) for memo in data["memos"]]
                
        job = ACPJob(
                    acp_client=self,
                    id=data["id"],
                    provider_address=data["providerAddress"],
                    client_address=data["clientAddress"],
                    evaluator_address=data["evaluatorAddress"],
                    memos=memos,
                    phase=data["phase"],
                    price=data["price"]
                )
        print(f"Received evaluate: {job}")
        self.on_evaluate(job)

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
            raise ACPSocketConnectionError(f"Failed to connect to socket server: {e}")

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
    

    def browse_agents(self, keyword: str, cluster: Optional[str] = None, sortBy: Optional[List[ACPAgentSort]] = None, rerank: Optional[bool] = True, top_k: Optional[int] = None) -> List[IACPAgent]:
        """
        Search and browse available agents on the platform.
        
        This method allows you to discover agents based on various criteria including
        keywords, clusters, and sorting preferences. The results can be reranked using
        semantic similarity and limited to a specific number of results.
        
        Args:
            keyword (str): Search keyword to match against agent names, descriptions, 
                and service offerings
            cluster (Optional[str], optional): Filter agents by cluster name. 
                Defaults to None.
            sortBy (Optional[List[ACPAgentSort]], optional): List of sorting criteria. 
                Available options: SUCCESS_RATE, JOB_COUNT, IS_ONLINE, etc. 
                Defaults to None.
            rerank (Optional[bool], optional): Whether to use semantic reranking 
                for better relevance. Defaults to True.
            top_k (Optional[int], optional): Maximum number of agents to return. 
                Defaults to None (no limit).
        
        Returns:
            List[IACPAgent]: List of matching agents with their offerings and metadata
        
        Raises:
            ACPApiError: If the API request fails
            ACPError: If an unexpected error occurs during browsing
        """
        url = f"{self.acp_api_url}/agents?search={keyword}"
        
        if sortBy and len(sortBy) > 0:
            url += f"&sort={','.join([s.value for s in sortBy])}"
            
        if rerank is True:
            url += f"&rerank={rerank}"
            
        if top_k:
            url += f"&top_k={top_k}"
        
        if self.agent_address:
            url += f"&filters[walletAddress][$notIn]={self.agent_address}"
            
        if cluster:
            url += f"&filters[cluster]={cluster}"
        
        if self.config.chain_env == "base-sepolia":
            url += f"&filters[hasGraduated]=false"
        else:
            url += f"&filters[hasGraduated]=true"
            
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
                    twitter_handle=agent_data.get("twitterHandle"),
                    metrics=agent_data.get("metrics"),
                    processing_time=agent_data.get("processingTime","")
                ))
            return agents
        except requests.exceptions.RequestException as e:
            raise ACPApiRequestError(f"Failed to browse agents: {e}")
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
        """
        Create a new job request with a service provider.
        
        This method initiates the complete job lifecycle including:
        1. Creating the job on-chain via smart contract
        2. Setting the job budget 
        3. Creating the initial service requirement memo
        4. Registering the job with the ACP API
        
        Args:
            provider_address (str): Ethereum address of the service provider
            service_requirement (Union[Dict[str, Any], str]): Description of the 
                required service. Can be a string or structured data matching 
                the provider's requirement schema.
            amount (float): Payment amount in ETH for the job
            evaluator_address (Optional[str], optional): Address of the evaluator. 
                If not provided, defaults to the client's address. Defaults to None.
            expired_at (Optional[datetime], optional): Job expiration timestamp. 
                If not provided, defaults to 1 day from now. Defaults to None.
        
        Returns:
            int: Unique job ID that can be used to track the job
        
        Raises:
            Exception: If job creation fails or transaction is rejected
        """
        if expired_at is None:
            expired_at = datetime.now(timezone.utc) + timedelta(days=1)
        
        eval_addr = Web3.to_checksum_address(evaluator_address) if evaluator_address else self.agent_address
        
        job_id = None
        retry_count = 3
        retry_delay = 3
        
        user_op_hash = self.contract_manager.create_job(
            self.agent_address, provider_address, eval_addr, expired_at
        )
        
        time.sleep(retry_delay) 
        for attempt in range(retry_count):
            try:
                response = self.contract_manager.validate_transaction(user_op_hash)
                
                if response.get("status") == 200:
                    logs = response.get("receipts", [])[0].get("logs", [])
                    contract_logs = next(
                        (log for log in logs if log.get("address", "").lower() == self.contract_manager.config.contract_address.lower()),
                        None
                    )
                    
                    if not contract_logs:
                        raise ACPContractLogParsingError("Failed to get contract logs")
                        
                    try:
                        job_id = int(Web3.to_int(hexstr=contract_logs.get("data")))
                        break
                    except (ValueError, TypeError, AttributeError) as e:
                        raise ACPContractLogParsingError(f"Failed to parse job ID from contract logs: {e}")
                
                
                # data = response.get("data", {})
                # if not data:
                #     raise Exception("Invalid tx_hash!")
                
                # if data.get("status") == "retry":
                #     raise Exception("Transaction failed, retrying...")
                
                # if data.get("status") == "failed":
                #     break
                
                # if data.get("status") == "success":
                #     job_id = int(data.get("result").get("jobId"))
                    
                # if job_id is not None and job_id != "":
                #     break  
                
            except Exception as e:
                if (attempt == retry_count - 1):
                    print(f"Error in create_job function: {e}")
                if attempt < retry_count - 1:
                    time.sleep(retry_delay) 
                else:
                    raise
        
        if job_id is None or job_id == "":
            raise ACPJobCreationError("Failed to create job")
        
        amount_in_wei = self.w3.to_wei(amount, "ether")
        self.contract_manager.set_budget(job_id, amount_in_wei)
        time.sleep(10)
        
        self.contract_manager.create_memo(
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
        """
        Respond to a job memo during the negotiation phase.
        
        This method is typically used by service providers to accept or reject
        job proposals during the negotiation phase.
        
        Args:
            job_id (int): ID of the job being responded to
            memo_id (int): ID of the specific memo being responded to
            accept (bool): Whether to accept (True) or reject (False) the proposal
            reason (Optional[str], optional): Reason for the decision. Defaults to "".
        
        Returns:
            str: Transaction hash of the response
        
        Raises:
            Exception: If the response transaction fails
        """
        try:
            data = self.contract_manager.sign_memo(memo_id, accept, reason or "")
            tx_hash = data.get('receipts',[])[0].get('txHash')
            if (not accept):
                exit()
                
            time.sleep(10)
            
            print(f"Responding to job {job_id} with memo {memo_id} and accept {accept} and reason {reason}")
            self.contract_manager.create_memo(
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
    ) -> Dict[str, Any]:
        """
        Make payment for an accepted job.
        
        This method handles the complete payment process including:
        1. Approving token allowance for the contract
        2. Signing the payment memo
        3. Creating a payment confirmation memo
        
        Args:
            job_id (int): ID of the job being paid for
            memo_id (int): ID of the memo authorizing payment
            amount (Union[float, str]): Payment amount in ETH
            reason (Optional[str], optional): Payment reason or description. Defaults to "".
        
        Returns:
            Dict[str, Any]: Transaction result data
        
        Raises:
            Exception: If payment processing fails
        """
        
        amount_in_wei = self.w3.to_wei(amount, "ether")
        time.sleep(10)

        self.contract_manager.approve_allowance(amount_in_wei)
        time.sleep(10)

        self.contract_manager.sign_memo(memo_id, True, reason or "")
        time.sleep(10)
        
        reason = f"{reason if reason else f'Job {job_id} paid.'}"
        print(f"Paid for job {job_id} with memo {memo_id} and amount {amount} and reason {reason}")

        return self.contract_manager.create_memo(
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
        """
        Submit job deliverable to the client.
        
        This method is used by service providers to submit their completed work
        to the client for evaluation.
        
        Args:
            job_id (int): ID of the job for which deliverable is being submitted
            deliverable_content (str): The deliverable content (URL, JSON, or text)
        
        Returns:
            str: Transaction hash of the submission
        """
        
        data = self.contract_manager.create_memo(
            job_id,
            deliverable_content,
            MemoType.OBJECT_URL,
            is_secured=True,
            next_phase=ACPJobPhase.COMPLETED
        )
        tx_hash = data.get('receipts',[])[0].get('txHash')
        # print(f"Deliverable submission tx: {tx_hash} for job {job_id}")
        return tx_hash

    def evaluate_job_delivery(
        self, 
        memo_id_of_deliverable: int, 
        accept: bool, 
        reason: Optional[str] = ""
    ) -> str:
        """
        Evaluate a job deliverable as an evaluator.
        
        This method is used by evaluators to approve or reject submitted deliverables,
        which determines whether the service provider gets paid.
        
        Args:
            memo_id_of_deliverable (int): ID of the memo containing the deliverable
            accept (bool): Whether to accept (True) or reject (False) the deliverable
            reason (Optional[str], optional): Evaluation reason or feedback. Defaults to "".
        
        Returns:
            str: Transaction hash of the evaluation
        """
        
        data = self.contract_manager.sign_memo(memo_id_of_deliverable, accept, reason or "")
        txHash = data.get('receipts',[])[0].get('transactionHash')
        print(f"Evaluation (signMemo) tx: {txHash} for deliverable memo ID {memo_id_of_deliverable} is {accept}")
        return txHash


    def get_active_jobs(self, page: int = 1, pageSize: int = 10) -> List["ACPJob"]:
        """
        Retrieve active jobs for the current agent.
        
        Args:
            page (int, optional): Page number for pagination. Defaults to 1.
            pageSize (int, optional): Number of jobs per page. Defaults to 10.
        
        Returns:
            List[ACPJob]: List of active jobs
        
        Raises:
            ACPApiError: If the API request fails
        """
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
                        type=MemoType(int(memo.get("memoType"))),
                        content=memo.get("content"),
                        next_phase=ACPJobPhase(int(memo.get("nextPhase"))),
                    ))
                jobs.append(ACPJob(
                    acp_client=self,
                    id=job.get("id"),
                    provider_address=job.get("providerAddress"),
                    client_address=job.get("clientAddress"),
                    evaluator_address=job.get("evaluatorAddress"),
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
                        type=MemoType(int(memo.get("memoType"))),
                        content=memo.get("content"),
                        next_phase=ACPJobPhase(int(memo.get("nextPhase")))
                    ))
                jobs.append(ACPJob(
                    acp_client=self,
                    id=job.get("id"),
                    provider_address=job.get("providerAddress"),
                    client_address=job.get("clientAddress"),
                    evaluator_address=job.get("evaluatorAddress"),
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
                        type=MemoType(int(memo.get("memoType"))),
                        content=memo.get("content"),
                        next_phase=ACPJobPhase(int(memo.get("nextPhase")))
                    ))
                jobs.append(ACPJob(
                    acp_client=self,
                    id=job.get("id"),
                    provider_address=job.get("providerAddress"),
                    client_address=job.get("clientAddress"),
                    evaluator_address=job.get("evaluatorAddress"),
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
                raise ACPJobNotFoundError(data["error"]["message"])
            
            memos = []
            for memo in data.get("data", {}).get("memos", []):
                memos.append(ACPMemo(
                    id=memo.get("id"),
                    type=MemoType(int(memo.get("memoType"))),
                    content=memo.get("content"),
                    next_phase=ACPJobPhase(int(memo.get("nextPhase")))
                ))
            return ACPJob(
                acp_client=self,
                id=data.get("data", {}).get("id"),
                provider_address=data.get("data", {}).get("providerAddress"),
                client_address=data.get("data", {}).get("clientAddress"),
                evaluator_address=data.get("data", {}).get("evaluatorAddress"),
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
                raise ACPMemoNotFoundError(data["error"]["message"])
            
            return ACPMemo(
                id=data.get("data", {}).get("id"),
                type=MemoType(int(data.get("data", {}).get("memoType"))),
                content=data.get("data", {}).get("content"),
                next_phase=ACPJobPhase(int(data.get("data", {}).get("nextPhase")))
            )
            
        except Exception as e:
            raise ACPApiError(f"Failed to get memo by ID: {e}")

    def get_agent(self, wallet_address: str) -> Optional[IACPAgent]:
        """
        Retrieve agent information by wallet address.
        
        Args:
            wallet_address (str): Ethereum address of the agent
        
        Returns:
            Optional[IACPAgent]: Agent information if found, None otherwise
        
        Raises:
            ACPApiError: If the API request fails
            ACPError: If an unexpected error occurs
        """
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
                twitter_handle=agent_data.get("twitterHandle"),
                metrics=agent_data.get("metrics"),
                processing_time=agent_data.get("processingTime","")
            )
            
        except requests.exceptions.RequestException as e:
            raise ACPApiRequestError(f"Failed to get agent: {e}")
        except Exception as e:
            raise ACPError(f"An unexpected error occurred while getting agent: {e}")

# Rebuild the AcpJob model after VirtualsACP is defined
ACPJob.model_rebuild()
ACPMemo.model_rebuild()
ACPJobOffering.model_rebuild()