# virtuals_acp/client.py

import json
import logging
import signal
import sys
import threading
from datetime import datetime, timezone, timedelta
from importlib.metadata import version
from typing import Literal, List, Optional, Tuple, Union, Dict, Any, Callable

import requests
import socketio
from web3 import Web3

from virtuals_acp.contract_clients.base_contract_client import BaseAcpContractClient
from virtuals_acp.exceptions import ACPApiError, ACPError
from virtuals_acp.account import ACPAccount
from virtuals_acp.job import ACPJob
from virtuals_acp.memo import ACPMemo
from virtuals_acp.models import (
    ACPAgentSort,
    ACPJobPhase,
    ACPGraduationStatus,
    ACPOnlineStatus,
    MemoType,
    IACPAgent,
    DeliverablePayload,
    FeeType,
    GenericPayload,
    T,
    ACPMemoStatus,
)
from virtuals_acp.job_offering import ACPJobOffering, ACPResourceOffering
from virtuals_acp.fare import (
    ETH_FARE,
    WETH_FARE,
    FareAmount,
    FareBigInt,
    FareAmountBase,
)
from virtuals_acp.configs.configs import (
    BASE_SEPOLIA_CONFIG,
    BASE_MAINNET_CONFIG,
)
from virtuals_acp.utils import prepare_payload

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ACPClient")


class VirtualsACP:
    def __init__(
        self,
        acp_contract_clients: Union[BaseAcpContractClient, List[BaseAcpContractClient]],
        on_new_task: Optional[Callable] = None,
        on_evaluate: Optional[Callable] = None,
    ):
        # Handle both single client and list of clients
        if isinstance(acp_contract_clients, list):
            self.contract_clients = acp_contract_clients
        else:
            self.contract_clients = [acp_contract_clients]

        if len(self.contract_clients) == 0:
            raise ACPError("ACP contract client is required")

        # Validate all clients have the same agent wallet address
        first_agent_address = self.contract_clients[0].agent_wallet_address
        for client in self.contract_clients:
            if client.agent_wallet_address != first_agent_address:
                raise ACPError(
                    "All contract clients must have the same agent wallet address"
                )

        # Use the first client for common properties
        self.contract_client = self.contract_clients[0]
        self.agent_wallet_address = first_agent_address
        self.config = self.contract_client.config
        self.acp_api_url = self.config.acp_api_url

        self._agent_wallet_address = Web3.to_checksum_address(self.agent_wallet_address)

        # Socket.IO setup
        self.on_new_task = on_new_task
        self.on_evaluate = on_evaluate or self._default_on_evaluate
        self.sio = socketio.Client()
        self._setup_socket_handlers()
        self._connect_socket()

    @property
    def acp_contract_client(self):
        """Get the first contract client (for backward compatibility)."""
        return self.contract_clients[0]

    @property
    def acp_url(self):
        """Get the ACP URL from the first contract client."""
        return self.contract_client.config.acp_api_url

    @property
    def wallet_address(self):
        """Get the wallet address from the first contract client."""
        return self.contract_client.agent_wallet_address

    def contract_client_by_address(self, address: Optional[str]):
        """Find contract client by contract address."""
        if not address:
            return self.contract_clients[0]

        for client in self.contract_clients:
            if (
                hasattr(client, "contract_address")
                and client.contract_address == address
            ):
                return client

        raise ACPError("ACP contract client not found")

    def _default_on_evaluate(self, job: ACPJob):
        """Default handler for job evaluation events."""
        job.evaluate(True, "Evaluated by default")

    def _on_room_joined(self, data):
        logger.info("Connected to room", data)  # Send acknowledgment back to server
        return True

    def _on_evaluate(self, data):
        if self.on_evaluate:
            try:
                threading.Thread(target=self.handle_evaluate, args=(data,)).start()
                return True
            except Exception as e:
                logger.warning(f"Error in onEvaluate handler: {e}")
                return False

    def _on_new_task(self, data):
        if self.on_new_task:
            try:
                threading.Thread(target=self.handle_new_task, args=(data,)).start()
                return True
            except Exception as e:
                logger.warning(f"Error in onNewTask handler: {e}")
                return False

    def handle_new_task(self, data) -> None:
        memo_to_sign_id = data.get("memoToSign")

        memos = [
            ACPMemo(
                contract_client=self.contract_client_by_address(
                    data.get("contractAddress")
                ),
                id=memo.get("id"),
                type=MemoType(int(memo.get("memoType"))),
                content=memo.get("content"),
                next_phase=ACPJobPhase.from_value(memo.get("nextPhase")),
                status=ACPMemoStatus(memo.get("status")),
                signed_reason=memo.get("signedReason"),
                expiry=(
                    datetime.fromtimestamp(int(memo["expiry"]))
                    if memo.get("expiry")
                    else None
                ),
                payable_details=memo.get("payableDetails"),
            )
            for memo in data["memos"]
        ]

        memo_to_sign = (
            next((m for m in memos if int(m.id) == int(memo_to_sign_id)), None)
            if memo_to_sign_id is not None
            else None
        )

        context = data["context"]
        if isinstance(context, str):
            try:
                context = json.loads(context)
            except json.JSONDecodeError:
                context = None

        job = ACPJob(
            acp_client=self,
            id=data["id"],
            provider_address=data["providerAddress"],
            client_address=data["clientAddress"],
            evaluator_address=data["evaluatorAddress"],
            contract_address=data.get("contractAddress"),
            memos=memos,
            phase=data["phase"],
            price=data["price"],
            price_token_address=data["priceTokenAddress"],
            context=context,
        )
        if self.on_new_task:
            self.on_new_task(job, memo_to_sign)

    def handle_evaluate(self, data) -> None:
        memos = [
            ACPMemo(
                contract_client=self.contract_client_by_address(
                    data.get("contractAddress")
                ),
                id=memo.get("id"),
                type=MemoType(int(memo.get("memoType"))),
                content=memo.get("content"),
                next_phase=ACPJobPhase.from_value(memo.get("nextPhase")),
                status=ACPMemoStatus(memo.get("status")),
                signed_reason=memo.get("signedReason"),
                expiry=(
                    datetime.fromtimestamp(int(memo["expiry"]))
                    if memo.get("expiry")
                    else None
                ),
                payable_details=memo.get("payableDetails"),
            )
            for memo in data["memos"]
        ]

        context = data["context"]
        if isinstance(context, str):
            try:
                context = json.loads(context)
            except json.JSONDecodeError:
                context = None

        job = ACPJob(
            acp_client=self,
            id=data["id"],
            provider_address=data["providerAddress"],
            client_address=data["clientAddress"],
            evaluator_address=data["evaluatorAddress"],
            contract_address=data.get("contractAddress"),
            memos=memos,
            phase=data["phase"],
            price=data["price"],
            price_token_address=data["priceTokenAddress"],
            context=context,
        )
        self.on_evaluate(job)

    def _setup_socket_handlers(self) -> None:
        self.sio.on("roomJoined", self._on_room_joined)
        self.sio.on("onEvaluate", self._on_evaluate)
        self.sio.on("onNewTask", self._on_new_task)

    def _connect_socket(self) -> None:
        """Connect to the socket server with appropriate authentication."""
        headers_data = {
            "x-sdk-version": version("virtuals_acp"),
            "x-sdk-language": "python",
            "x-contract-address": self.contract_clients[0].contract_address,
        }
        auth_data = {"walletAddress": self.agent_address}

        if self.on_evaluate != self._default_on_evaluate:
            auth_data["evaluatorAddress"] = self.agent_address

        try:
            self.sio.connect(
                self.acp_api_url,
                auth=auth_data,
                headers=headers_data,
                transports=["websocket"],
                retry=True,
            )

            def signal_handler(sig, frame):
                self.sio.disconnect()
                sys.exit(0)

            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

        except Exception as e:
            logger.warning(f"Failed to connect to socket server: {e}")

    def __del__(self):
        """Cleanup when the object is destroyed."""
        if hasattr(self, "sio") and self.sio is not None:
            self.sio.disconnect()

    @property
    def agent_address(self) -> str:
        return self._agent_wallet_address

    def browse_agents(
        self,
        keyword: str,
        cluster: Optional[str] = None,
        sort_by: Optional[List[ACPAgentSort]] = None,
        top_k: Optional[int] = None,
        graduation_status: Optional[ACPGraduationStatus] = None,
        online_status: Optional[ACPOnlineStatus] = None,
    ) -> List[IACPAgent]:
        url = f"{self.acp_api_url}/agents/v3/search?search={keyword}"
        top_k = 5 if top_k is None else top_k

        if sort_by:
            url += f"&sortBy={','.join([s.value for s in sort_by])}"

        if top_k:
            url += f"&top_k={top_k}"

        if self.agent_address:
            url += f"&walletAddressesToExclude={self.agent_address}"

        if cluster:
            url += f"&cluster={cluster}"

        if graduation_status is not None:
            url += f"&graduationStatus={graduation_status.value}"

        if online_status is not None:
            url += f"&onlineStatus={online_status.value}"

        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            agents_data = data.get("data", [])

            # Filter agents by available contract addresses
            available_contract_addresses = [
                client.contract_address.lower() for client in self.contract_clients
            ]

            # Filter out self and agents not using our contract addresses
            filtered_agents = [
                agent
                for agent in agents_data
                if agent["walletAddress"].lower() != self.agent_address.lower()
                and agent.get("contractAddress", "").lower()
                in available_contract_addresses
            ]

            agents = []
            for agent_data in filtered_agents:
                contract_client = self.contract_client_by_address(
                    agent_data.get("contractAddress")
                )
                provider_address = agent_data.get("walletAddress")
                job_offerings = [
                    ACPJobOffering(
                        acp_client=self,
                        contract_client=contract_client,
                        provider_address=provider_address,
                        name=job["name"],
                        price=job["price"],
                        requirement=job.get("requirement", None),
                    )
                    for job in agent_data.get("jobs", [])
                ]

                agents.append(
                    IACPAgent(
                        id=agent_data["id"],
                        name=agent_data.get("name"),
                        description=agent_data.get("description"),
                        wallet_address=Web3.to_checksum_address(
                            agent_data["walletAddress"]
                        ),
                        job_offerings=job_offerings,
                        twitter_handle=agent_data.get("twitterHandle"),
                        metrics=agent_data.get("metrics"),
                        processing_time=agent_data.get("processingTime", ""),
                    )
                )
            return agents
        except requests.exceptions.RequestException as e:
            raise ACPApiError(f"Failed to browse agents: {e}")
        except Exception as e:
            raise ACPError(f"An unexpected error occurred while browsing agents: {e}")

    def initiate_job(
        self,
        provider_address: str,
        service_requirement: Union[Dict[str, Any], str],
        fare_amount: FareAmountBase,
        evaluator_address: Optional[str] = None,
        expired_at: Optional[datetime] = None,
    ) -> int:
        if expired_at is None:
            expired_at = datetime.now(timezone.utc) + timedelta(days=1)

        if provider_address == self.agent_address:
            raise ACPError("Provider address cannot be the same as the client address")

        eval_addr = (
            Web3.to_checksum_address(evaluator_address)
            if evaluator_address
            else self.agent_address
        )

        # Lookup existing account between client and provider
        account = self.get_by_client_and_provider(
            self.agent_address, provider_address, self.contract_client
        )

        # Determine whether to call createJob or createJobWithAccount
        base_contract_addresses = {
            BASE_SEPOLIA_CONFIG.contract_address.lower(),
            BASE_MAINNET_CONFIG.contract_address.lower(),
        }

        use_simple_create = (
            self.contract_client.config.contract_address.lower()
            in base_contract_addresses
        )

        if use_simple_create or not account:
            response = self.contract_client.create_job(
                provider_address,
                eval_addr or self.wallet_address,
                expired_at,
                fare_amount.fare.contract_address,
                fare_amount.amount,
                "",
            )
        else:
            response = self.contract_client.create_job_with_account(
                account.id,
                eval_addr or self.wallet_address,
                fare_amount.amount,
                fare_amount.fare.contract_address,
                expired_at,
            )

        job_id = self.contract_client.get_job_id(
            response, self.agent_address, provider_address
        )

        self.contract_client.create_memo(
            job_id,
            (
                service_requirement
                if isinstance(service_requirement, str)
                else json.dumps(service_requirement)
            ),
            MemoType.MESSAGE,
            is_secured=True,
            next_phase=ACPJobPhase.NEGOTIATION,
        )

        return job_id

    def get_by_client_and_provider(
        self,
        client_address: str,
        provider_address: str,
        acp_contract_client: Optional[BaseAcpContractClient] = None,
    ) -> Optional[ACPAccount]:
        """Get account by client and provider addresses."""
        try:
            url = f"{self.acp_url}/accounts/client/{client_address}/provider/{provider_address}"

            response = requests.get(url)
            if response.status_code == 404:
                return None

            response.raise_for_status()
            data = response.json()

            if not data.get("data"):
                return None

            account_data = data["data"]
            contract_client = acp_contract_client or self.contract_clients[0]

            return ACPAccount(
                contract_client=contract_client,
                id=account_data["id"],
                client_address=account_data["clientAddress"],
                provider_address=account_data["providerAddress"],
                metadata=account_data.get("metadata", ""),
            )
        except requests.exceptions.RequestException as e:
            raise ACPApiError(f"Failed to get account by client and provider: {e}")
        except Exception as e:
            raise ACPError(f"An unexpected error occurred while getting account: {e}")

    def get_account_by_job_id(
        self,
        job_id: int,
        acp_contract_client: Optional[BaseAcpContractClient] = None,
    ) -> Optional[ACPAccount]:
        """Get account by job ID."""
        try:
            url = f"{self.acp_url}/accounts/job/{job_id}"

            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            if not data.get("data"):
                return None

            account_data = data["data"]
            contract_client = acp_contract_client or self.contract_clients[0]

            return ACPAccount(
                contract_client=contract_client,
                id=account_data["id"],
                client_address=account_data["clientAddress"],
                provider_address=account_data["providerAddress"],
                metadata=account_data.get("metadata", ""),
            )
        except requests.exceptions.RequestException as e:
            raise ACPApiError(f"Failed to get account by job id: {e}")
        except Exception as e:
            raise ACPError(
                f"An unexpected error occurred while getting account by job id: {e}"
            )

    def create_memo(self, job_id: int, content: str, next_phase: ACPJobPhase):
        return self.contract_client.create_memo(
            job_id, content, MemoType.MESSAGE, False, next_phase
        )

    def create_payable_memo(
        self,
        job_id: int,
        content: str,
        amount: FareAmountBase,
        recipient: str,
        next_phase: ACPJobPhase,
        type: Literal[MemoType.PAYABLE_REQUEST, MemoType.PAYABLE_TRANSFER_ESCROW],
        expired_at: datetime,
    ):
        if type == MemoType.PAYABLE_TRANSFER_ESCROW:
            self.contract_client.approve_allowance(
                amount.amount, amount.fare.contract_address
            )

        fee_amount = FareAmount(0, self.contract_client.config.base_fare)

        return self.contract_client.create_payable_memo(
            job_id,
            content,
            amount.amount,
            recipient,
            fee_amount.amount,
            FeeType.NO_FEE,
            next_phase,
            type,
            expired_at,
            amount.fare.contract_address,
        )

    def respond_to_job(
        self,
        job_id: int,
        memo_id: int,
        accept: bool,
        content: Optional[str],
        reason: Optional[str] = "",
    ) -> str:
        try:
            data = self.contract_client.sign_memo(memo_id, accept, reason or "")
            tx_hash = data.get("receipts", [])[0].get("transactionHash")
            if not accept:
                return tx_hash

            logger.info(
                f"Responding to job {job_id} with memo {memo_id} and accept {accept} and reason {reason}"
            )
            self.contract_client.create_memo(
                job_id,
                content or f"{reason or ''}",
                MemoType.MESSAGE,
                is_secured=False,
                next_phase=ACPJobPhase.TRANSACTION,
            )
            return tx_hash
        except Exception as e:
            logger.warning(f"Error in respond_to_job_memo: {e}")
            raise

    def send_message(
        self, job_id: int, message: GenericPayload[T], next_phase: ACPJobPhase
    ) -> str:
        data = self.contract_client.create_memo(
            job_id,
            json.dumps(message.model_dump()),
            MemoType.MESSAGE,
            False,
            next_phase,
        )
        tx_hash = data.get("receipts", [])[0].get("transactionHash")
        return tx_hash

    def respond_to_funds_transfer(
        self, memo_id: int, accept: bool, reason: Optional[str] = ""
    ):
        data = self.contract_client.sign_memo(memo_id, accept, reason)
        tx_hash = data.get("receipts", [])[0].get("transactionHash")
        return tx_hash

    def reject_job(self, job_id: int, reason: Optional[str] = "") -> str:
        data = self.contract_client.create_memo(
            job_id, f"{reason or ''}", MemoType.MESSAGE, False, ACPJobPhase.REJECTED
        )
        tx_hash = data.get("receipts", [])[0].get("transactionHash")
        return tx_hash

    def deliver_job(self, job_id: int, deliverable: DeliverablePayload) -> str:
        data = self.contract_client.create_memo(
            job_id,
            prepare_payload(deliverable),
            MemoType.OBJECT_URL,
            is_secured=True,
            next_phase=ACPJobPhase.COMPLETED,
        )
        tx_hash = data.get("receipts", [])[0].get("transactionHash")
        return tx_hash

    def sign_memo(self, memo_id: int, accept: bool, reason: Optional[str] = "") -> str:
        data = self.contract_client.sign_memo(memo_id, accept, reason)
        tx_hash = data.get("receipts", [])[0].get("transactionHash")
        return tx_hash

    def get_active_jobs(self, page: int = 1, pageSize: int = 10) -> List["ACPJob"]:
        url = f"{self.acp_api_url}/jobs/active?pagination[page]={page}&pagination[pageSize]={pageSize}"
        headers = {"wallet-address": self.agent_address}

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            jobs = []

            for job in data.get("data", []):
                memos = []
                for memo in job.get("memos", []):
                    memos.append(
                        ACPMemo(
                            contract_client=self.contract_client,
                            id=memo.get("id"),
                            type=MemoType(int(memo.get("memoType"))),
                            content=memo.get("content"),
                            next_phase=ACPJobPhase.from_value(memo.get("nextPhase")),
                            status=ACPMemoStatus(memo.get("status")),
                            signed_reason=memo.get("signedReason"),
                            expiry=(
                                datetime.fromtimestamp(int(memo["expiry"]))
                                if memo.get("expiry")
                                else None
                            ),
                            payable_details=memo.get("payableDetails"),
                        )
                    )

                context = job.get("context")
                if isinstance(context, str):
                    try:
                        context = json.loads(context)
                    except json.JSONDecodeError:
                        context = None

                jobs.append(
                    ACPJob(
                        acp_client=self,
                        id=job.get("id"),
                        provider_address=job.get("providerAddress"),
                        client_address=job.get("clientAddress"),
                        evaluator_address=job.get("evaluatorAddress"),
                        contract_address=job.get("contractAddress"),
                        memos=memos,
                        phase=job.get("phase"),
                        price_token_address=job.get("priceTokenAddress"),
                        price=job.get("price"),
                        context=context,
                    )
                )
            return jobs
        except Exception as e:
            raise ACPApiError(f"Failed to get active jobs: {e}")

    def get_completed_jobs(self, page: int = 1, pageSize: int = 10) -> List["ACPJob"]:
        url = f"{self.acp_api_url}/jobs/completed?pagination[page]={page}&pagination[pageSize]={pageSize}"
        headers = {"wallet-address": self.agent_address}

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            jobs = []

            for job in data.get("data", []):
                memos = []
                for memo in job.get("memos", []):
                    memos.append(
                        ACPMemo(
                            contract_client=self.contract_client,
                            id=memo.get("id"),
                            type=MemoType(int(memo.get("memoType"))),
                            content=memo.get("content"),
                            next_phase=ACPJobPhase.from_value(memo.get("nextPhase")),
                            status=ACPMemoStatus(memo.get("status")),
                            signed_reason=memo.get("signedReason"),
                            expiry=(
                                datetime.fromtimestamp(int(memo["expiry"]))
                                if memo.get("expiry")
                                else None
                            ),
                            payable_details=memo.get("payableDetails"),
                        )
                    )

                context = job.get("context")
                if isinstance(context, str):
                    try:
                        context = json.loads(context)
                    except json.JSONDecodeError:
                        context = None

                jobs.append(
                    ACPJob(
                        acp_client=self,
                        id=job.get("id"),
                        provider_address=job.get("providerAddress"),
                        client_address=job.get("clientAddress"),
                        evaluator_address=job.get("evaluatorAddress"),
                        contract_address=job.get("contractAddress"),
                        price_token_address=job.get("priceTokenAddress"),
                        memos=memos,
                        phase=job.get("phase"),
                        price=job.get("price"),
                        context=context,
                    )
                )
            return jobs
        except Exception as e:
            raise ACPApiError(f"Failed to get completed jobs: {e}")

    def get_cancelled_jobs(self, page: int = 1, pageSize: int = 10) -> List["ACPJob"]:
        url = f"{self.acp_api_url}/jobs/cancelled?pagination[page]={page}&pagination[pageSize]={pageSize}"
        headers = {"wallet-address": self.agent_address}

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            jobs = []

            for job in data.get("data", []):
                memos = []
                for memo in job.get("memos", []):
                    memos.append(
                        ACPMemo(
                            contract_client=self.contract_client,
                            id=memo.get("id"),
                            type=MemoType(int(memo.get("memoType"))),
                            content=memo.get("content"),
                            next_phase=ACPJobPhase.from_value(memo.get("nextPhase")),
                            status=ACPMemoStatus(memo.get("status")),
                            signed_reason=memo.get("signedReason"),
                            expiry=(
                                datetime.fromtimestamp(int(memo["expiry"]))
                                if memo.get("expiry")
                                else None
                            ),
                            payable_details=memo.get("payableDetails"),
                        )
                    )

                context = job.get("context")
                if isinstance(context, str):
                    try:
                        context = json.loads(context)
                    except json.JSONDecodeError:
                        context = None

                jobs.append(
                    ACPJob(
                        acp_client=self,
                        id=job.get("id"),
                        provider_address=job.get("providerAddress"),
                        client_address=job.get("clientAddress"),
                        evaluator_address=job.get("evaluatorAddress"),
                        contract_address=job.get("contractAddress"),
                        memos=memos,
                        phase=job.get("phase"),
                        price_token_address=job.get("priceTokenAddress"),
                        price=job.get("price"),
                        context=context,
                    )
                )
            return jobs
        except Exception as e:
            raise ACPApiError(f"Failed to get cancelled jobs: {e}")

    def get_job_by_onchain_id(self, onchain_job_id: int) -> "ACPJob":
        url = f"{self.acp_api_url}/jobs/{onchain_job_id}"
        headers = {"wallet-address": self.agent_address}

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            if data.get("error"):
                raise ACPApiError(data["error"]["message"])

            memos = []
            for memo in data.get("data", {}).get("memos", []):
                memos.append(
                    ACPMemo(
                        contract_client=self.contract_client,
                        id=memo.get("id"),
                        type=MemoType(int(memo.get("memoType"))),
                        content=memo.get("content"),
                        next_phase=ACPJobPhase.from_value(memo.get("nextPhase")),
                        status=ACPMemoStatus(memo.get("status")),
                        signed_reason=memo.get("signedReason"),
                        expiry=(
                            datetime.fromtimestamp(int(memo["expiry"]))
                            if memo.get("expiry")
                            else None
                        ),
                        payable_details=memo.get("payableDetails"),
                    )
                )

            context = data.get("data", {}).get("context")
            if isinstance(context, str):
                try:
                    context = json.loads(context)
                except json.JSONDecodeError:
                    context = None

            return ACPJob(
                acp_client=self,
                id=data.get("data", {}).get("id"),
                provider_address=data.get("data", {}).get("providerAddress"),
                client_address=data.get("data", {}).get("clientAddress"),
                evaluator_address=data.get("data", {}).get("evaluatorAddress"),
                contract_address=data.get("data", {}).get("contractAddress"),
                memos=memos,
                phase=data.get("data", {}).get("phase"),
                price=data.get("data", {}).get("price"),
                price_token_address=data.get("data", {}).get("priceTokenAddress"),
                context=context,
            )
        except Exception as e:
            raise ACPApiError(f"Failed to get job by onchain ID: {e}")

    def get_memo_by_id(self, onchain_job_id: int, memo_id: int) -> "ACPMemo":
        url = f"{self.acp_api_url}/jobs/{onchain_job_id}/memos/{memo_id}"
        headers = {"wallet-address": self.agent_address}

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            if data.get("error"):
                raise ACPApiError(data["error"]["message"])

            memo = data.get("data", {})

            return ACPMemo(
                contract_client=self.contract_client,
                id=memo.get("id"),
                type=MemoType(memo.get("memoType")),
                content=memo.get("content"),
                next_phase=ACPJobPhase.from_value(memo.get("nextPhase")),
                status=ACPMemoStatus(memo.get("status")),
                signed_reason=memo.get("signedReason"),
                expiry=(
                    datetime.fromtimestamp(int(memo["expiry"]))
                    if memo.get("expiry")
                    else None
                ),
                payable_details=memo.get("payableDetails"),
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
                    contract_client=self.contract_client_by_address(
                        offering.get("contractAddress")
                    ),
                    provider_address=agent_data["walletAddress"],
                    name=offering["name"],
                    price=offering["price"],
                    requirement=offering.get("requirement", None),
                )
                for offering in agent_data.get("jobs", [])
            ]

            resources = [
                ACPResourceOffering(
                    acp_client=self,
                    name=resource["name"],
                    description=resource["description"],
                    url=resource["url"],
                    parameters=resource.get("parameters", None),
                    id=resource["id"],
                )
                for resource in agent_data.get("resources", [])
            ]

            return IACPAgent(
                id=agent_data["id"],
                name=agent_data.get("name"),
                description=agent_data.get("description"),
                wallet_address=Web3.to_checksum_address(agent_data["walletAddress"]),
                job_offerings=offerings,
                resources=resources,
                twitter_handle=agent_data.get("twitterHandle"),
                metrics=agent_data.get("metrics"),
                processing_time=agent_data.get("processingTime", ""),
            )

        except requests.exceptions.RequestException as e:
            raise ACPApiError(f"Failed to get agent: {e}")
        except Exception as e:
            raise ACPError(f"An unexpected error occurred while getting agent: {e}")


# Rebuild the AcpJob model after VirtualsACP is defined
ACPJob.model_rebuild()
ACPMemo.model_rebuild()
ACPJobOffering.model_rebuild()
