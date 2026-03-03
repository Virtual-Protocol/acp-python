# virtuals_acp/client.py

import json
import logging
import signal
import sys
import threading
import jwt
import socketio
import requests
import time

from datetime import datetime, timezone, timedelta
from importlib.metadata import version
from typing import List, Optional, Union, Dict, Any, Callable
from web3 import Web3
from requests.auth import AuthBase

from virtuals_acp.account import ACPAccount
from virtuals_acp.configs.configs import (
    BASE_MAINNET_ACP_X402_CONFIG,
    BASE_SEPOLIA_ACP_X402_CONFIG,
    BASE_SEPOLIA_CONFIG,
    BASE_MAINNET_CONFIG,
)
from virtuals_acp.constants import USDC_TOKEN_ADDRESS
from virtuals_acp.contract_clients.base_contract_client import BaseAcpContractClient
from virtuals_acp.exceptions import ACPApiError, ACPError
from virtuals_acp.fare import FareAmountBase
from virtuals_acp.job import ACPJob
from virtuals_acp.job_offering import ACPJobOffering, ACPResourceOffering
from virtuals_acp.memo import ACPMemo
from virtuals_acp.models import (
    ACPAgentSort,
    ACPJobPhase,
    ACPGraduationStatus,
    ACPMemoState,
    ACPOnlineStatus,
    MemoType,
    IACPAgent,
    ACPMemoStatus,
    PriceType,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ACPClient")



class BearerAuth(AuthBase):
    def __init__(self, get_access_token: Callable[[], str]):
        self._get_access_token = get_access_token
        self._access_token: Optional[str] = None

    def __call__(self, req: requests.PreparedRequest):
        if not self._access_token:
            self._access_token = self._get_access_token()
        req.headers["authorization"] = f"Bearer {self._access_token}"
        return req

    def clear_token(self):
        self._access_token = None


class ACPApiClient:
    def __init__(self, acp_contract_client: BaseAcpContractClient, acp_url: str, wallet_address: str, require_auth: bool = False):
        self.acp_contract_client = acp_contract_client
        self.base_url = acp_url
        self.wallet_address = wallet_address
        self.require_auth = require_auth
        self.session = requests.Session()
        
        self.access_token: Optional[str] = None
        self.auth: Optional[BearerAuth] = None
        if require_auth:
            self.auth = BearerAuth(self.get_access_token)
            self.session.auth = self.auth
            self.session.headers["wallet-address"] = wallet_address
            

    def request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        err_callback: Optional[Callable[[requests.RequestException], None]] = None,
    ) -> Optional[Any]:
        if self.base_url in path:
            # absolute URL, use as is
            url = path
        else:
            url = f"{self.base_url}/{path}"
        
        try:
            resp = self.session.request(method, url, params=params, json=data)

            if resp.status_code == 401 and self.require_auth and self.auth:
                self.auth.clear_token()
                resp = self.session.request(method, url, params=params, json=data)

            resp.raise_for_status()
            return resp.json().get("data")
        except requests.RequestException as err:
            if err_callback:
                err_callback(err)
                return None

            if hasattr(err, "response") and err.response is not None:
                try:
                    error_message = err.response.json().get("error", {}).get("message")
                    if error_message:
                        raise ACPApiError(error_message) from err
                except (ValueError, AttributeError, KeyError):
                    pass

            raise ACPApiError(f"Failed to fetch {path}: {err}") from err
        except Exception as err:
            raise ACPApiError(
                f"Failed to fetch ACP Endpoint: {path} (network error)"
            ) from err

    def get_access_token(self) -> str:
        needs_refresh = self.access_token is None

        if self.access_token:
            decoded = jwt.decode(self.access_token, options={"verify_signature": False})
            if decoded.get("exp") and decoded["exp"] - 300 < time.time():
                needs_refresh = True

        if not needs_refresh:
            # Access token is still valid
            if self.access_token:
                return self.access_token
            else:
                raise Exception("Access token needs refreshing!")

        self.access_token = self.refresh_token()
        return self.access_token

    def refresh_token(self) -> str:
        challenge = self.get_auth_challenge()
        signature = self.acp_contract_client.sign_typed_data(challenge)

        verified = self.verify_auth_challenge(
            wallet_address=challenge["message"]["walletAddress"],
            nonce=challenge["message"]["nonce"],
            expires_at=challenge["message"]["expiresAt"],
            signature=signature,
        )

        return verified["accessToken"]

    def get_auth_challenge(self):
        try:
            response = requests.get(
                f"{self.base_url}/auth/challenge",
                params={"walletAddress": self.wallet_address},
            )
            response.raise_for_status()
            return response.json()["data"]
        except requests.RequestException as err:
            error_data = err.response.json() if err.response is not None else None
            print(f"Failed to get auth challenge: {error_data}")
            raise Exception("Failed to get auth challenge") from err

    def verify_auth_challenge(self, wallet_address: str, nonce: str, expires_at: int, signature: str):
        try:
            response = requests.post(
                f"{self.base_url}/auth/verify-typed-signature",
                json={
                    "walletAddress": wallet_address,
                    "nonce": nonce,
                    "expiresAt": expires_at,
                    "signature": signature,
                },
            )
            response.raise_for_status()
            return response.json()["data"]
        except requests.RequestException as err:
            raise Exception("Failed to verify auth challenge") from err


class VirtualsACP:
    def __init__(
        self,
        acp_contract_clients: Union[BaseAcpContractClient, List[BaseAcpContractClient]],
        on_new_task: Optional[Callable] = None,
        on_evaluate: Optional[Callable] = None,
        custom_rpc_url: Optional[str] = None,
        skip_socket_connection: Optional[bool] = False,
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

        self.acp_client = ACPApiClient(self.acp_contract_client, self.acp_url, self.wallet_address, require_auth=True)
        self.no_auth_acp_client = ACPApiClient(self.acp_contract_client, self.acp_url, self.wallet_address)

        # Socket.IO setup
        self.on_new_task = on_new_task
        self.on_evaluate = on_evaluate or self._default_on_evaluate

        if not skip_socket_connection:
            self.sio = socketio.Client()
            self.init()

    @property
    def acp_contract_client(self):
        """Get the first contract client (for backward compatibility)."""
        return self.contract_clients[0]

    @property
    def wallet_address(self):
        """Get the wallet address from the first contract client."""
        return Web3.to_checksum_address(self.acp_contract_client.agent_wallet_address)

    @property
    def acp_url(self):
        """Get the ACP URL from the first contract client."""
        return self.acp_contract_client.config.acp_api_url

    def init(self):
        logger.info(f"Initializing socket")
        
        try:
            auth_data = {
                "walletAddress": self.wallet_address,
                "accessToken": self.acp_client.get_access_token()
            }
            headers_data = {
                "x-sdk-version": version("virtuals_acp"),
                "x-sdk-language": "python",
                "x-contract-address": self.contract_clients[0].contract_address,
            }

            self.sio.connect(
                url=self.acp_url,
                auth=auth_data,
                headers=headers_data,
                transports=["websocket"],
                retry=True,
            )

            def cleanup(sig, frame):
                self.sio.disconnect()
                sys.exit(0)

            self.sio.on("roomJoined", self._on_room_joined)
            self.sio.on("onEvaluate", self._on_evaluate)
            self.sio.on("onNewTask", self._on_new_task)

            signal.signal(signal.SIGINT, cleanup)
            signal.signal(signal.SIGTERM, cleanup)
        except Exception as e:
            logger.error(f"Failed to connect to socket server: {e}")
    
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
        logger.info("Joined ACP Room", data)  # Send acknowledgment back to server
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
                txn_hash=memo.get("txHash"),
                signed_txn_hash=memo.get("signedTxHash"),
                state=ACPMemoState(memo.get("state")) if memo.get("state") else None,
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
            client_address=data["clientAddress"],
            provider_address=data["providerAddress"],
            evaluator_address=data["evaluatorAddress"],
            price=data["price"],
            price_token_address=data["priceTokenAddress"],
            memos=memos,
            phase=data["phase"],
            context=context,
            contract_address=data.get("contractAddress"),
            net_payable_amount=data.get("netPayableAmount"),
            deliverable=data.get("deliverable"),
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
                txn_hash=memo.get("txHash"),
                signed_txn_hash=memo.get("signedTxHash"),
                state=ACPMemoState(memo.get("state")) if memo.get("state") else None,
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
            client_address=data["clientAddress"],
            provider_address=data["providerAddress"],
            evaluator_address=data["evaluatorAddress"],
            price=data["price"],
            price_token_address=data["priceTokenAddress"],
            memos=memos,
            phase=data["phase"],
            context=context,
            contract_address=data.get("contractAddress"),
            net_payable_amount=data.get("netPayableAmount"),
            deliverable=data.get("deliverable"),
        )
        self.on_evaluate(job)

    def __del__(self):
        """Cleanup when the object is destroyed."""
        if hasattr(self, "sio") and self.sio is not None:
            self.sio.disconnect()

    def _hydrate_agent(self, agent_data: Dict[str, Any]) -> IACPAgent:
        contract_address = Web3.to_checksum_address(agent_data.get("contractAddress"))
        if not contract_address:
            raise ACPError("Agent contract address is required")

        contract_client = self.contract_client_by_address(contract_address)
        provider_address = agent_data.get("walletAddress")

        job_offerings: List[ACPJobOffering] = []
        for offering in agent_data.get("jobs", []):
            if "priceV2" in offering:
                price = offering["priceV2"]["value"]
                price_type = PriceType(offering["priceV2"]["type"])
            elif "price" in offering:
                price = offering["price"]
                price_type = PriceType.FIXED
            else:
                continue

            job_offerings.append(
                ACPJobOffering(
                    acp_client=self,
                    contract_client=contract_client,
                    provider_address=provider_address,
                    name=offering["name"],
                    price=price,
                    price_type=price_type,
                    required_funds=offering["requiredFunds"],
                    sla_minutes=offering["slaMinutes"],
                    requirement=offering.get("requirement", None),
                    deliverable=offering.get("deliverable", None),
                )
            )

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
            job_offerings=job_offerings,
            resources=resources,
            cluster=agent_data.get("cluster"),
            twitter_handle=agent_data.get("twitterHandle"),
            metrics=agent_data.get("metrics"),
            contract_address=contract_address,
        )

    def browse_agents(
        self,
        keyword: str,
        cluster: Optional[str] = None,
        sort_by: Optional[List[ACPAgentSort]] = None,
        top_k: Optional[int] = None,
        graduation_status: Optional[ACPGraduationStatus] = None,
        online_status: Optional[ACPOnlineStatus] = None,
        show_hidden_offerings: bool = False,
    ) -> List[IACPAgent]:
        url = f"{self.acp_url}/agents/v4/search?search={keyword}"
        top_k = 5 if top_k is None else top_k

        if sort_by:
            url += f"&sortBy={','.join([s.value for s in sort_by])}"

        if top_k:
            url += f"&top_k={top_k}"

        if self.wallet_address:
            url += f"&walletAddressesToExclude={self.wallet_address}"

        if cluster:
            url += f"&cluster={cluster}"

        if graduation_status is not None:
            url += f"&graduationStatus={graduation_status.value}"

        if online_status is not None:
            url += f"&onlineStatus={online_status.value}"

        if show_hidden_offerings:
            url += f"&showHiddenOfferings=true"

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
                if agent["walletAddress"].lower() != self.wallet_address.lower()
                   and agent.get("contractAddress", "").lower()
                   in available_contract_addresses
            ]

            agents = []
            for agent_data in filtered_agents:
                try:
                    agents.append(self._hydrate_agent(agent_data))
                except Exception as e:
                    logger.warning(f"Failed to hydrate agent {agent_data.get('id')}: {e}")
                    continue

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

        if provider_address == self.wallet_address:
            raise ACPError("Provider address cannot be the same as the client address")

        eval_addr = (
            Web3.to_checksum_address(evaluator_address)
            if evaluator_address
            else self.wallet_address
        )

        # Lookup existing account between client and provider
        account = self.get_by_client_and_provider(
            self.wallet_address, provider_address, self.acp_contract_client
        )

        # Determine whether to call createJob or createJobWithAccount
        base_contract_addresses = {
            BASE_SEPOLIA_CONFIG.contract_address.lower(),
            BASE_SEPOLIA_ACP_X402_CONFIG.contract_address.lower(),
            BASE_MAINNET_CONFIG.contract_address.lower(),
            BASE_MAINNET_ACP_X402_CONFIG.contract_address.lower(),

        }

        use_simple_create = (
            self.acp_contract_client.config.contract_address.lower()
            in base_contract_addresses
        )

        chain_id = self.acp_contract_client.config.chain_id
        usdc_token_address = USDC_TOKEN_ADDRESS[chain_id]
        is_usdc_payment_token = usdc_token_address == fare_amount.fare.contract_address
        is_x402_job = bool(getattr(self.acp_contract_client.config, "x402_config", None) and is_usdc_payment_token)

        if use_simple_create or not account:
            create_job_operation = self.acp_contract_client.create_job(
                provider_address,
                eval_addr or self.wallet_address,
                expired_at,
                fare_amount.fare.contract_address,
                fare_amount.amount,
                "",
                is_x402_job=is_x402_job,
            )
        else:
            create_job_operation = self.acp_contract_client.create_job_with_account(
                account.id,
                eval_addr or self.wallet_address,
                fare_amount.amount,
                fare_amount.fare.contract_address,
                expired_at,
                is_x402_job=is_x402_job,
            )

        response = self.acp_contract_client.handle_operation([create_job_operation])

        job_id = self.acp_contract_client.get_job_id(
            response, self.wallet_address, provider_address
        )

        operations = self.acp_contract_client.create_memo(
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

        self.acp_contract_client.handle_operation([operations])

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

    def get_active_jobs(self, page: int = 1, page_size: int = 10) -> List["ACPJob"]:
        url = f"{self.acp_url}/jobs/active?pagination[page]={page}&pagination[pageSize]={page_size}"
        raw_jobs = self._fetch_job_list(url)
        return self._hydrate_jobs(raw_jobs, log_prefix="Active jobs")

    def get_pending_memo_jobs(self, page: int = 1, page_size: int = 10) -> List["ACPJob"]:
        url = f"{self.acp_url}/jobs/pending-memos?pagination[page]={page}&pagination[pageSize]={page_size}"
        raw_jobs = self._fetch_job_list(url)
        return self._hydrate_jobs(raw_jobs, log_prefix="Pending memo jobs")

    def get_completed_jobs(self, page: int = 1, page_size: int = 10) -> List["ACPJob"]:
        url = f"{self.acp_url}/jobs/completed?pagination[page]={page}&pagination[pageSize]={page_size}"
        raw_jobs = self._fetch_job_list(url)
        return self._hydrate_jobs(raw_jobs, log_prefix="Completed jobs")

    def get_cancelled_jobs(self, page: int = 1, page_size: int = 10) -> List["ACPJob"]:
        url = f"{self.acp_url}/jobs/cancelled?pagination[page]={page}&pagination[pageSize]={page_size}"
        raw_jobs = self._fetch_job_list(url)
        return self._hydrate_jobs(raw_jobs, log_prefix="Cancelled jobs")

    def _fetch_job_list(
        self,
        url: str,
    ) -> List[dict]:
        try:
            response = requests.get(
                url,
                headers={"wallet-address": self.wallet_address},
            )
            response.raise_for_status()
        except requests.RequestException as e:
            raise ACPApiError("Failed to fetch ACP jobs (network error)") from e

        try:
            data = response.json()
        except ValueError as e:
            raise ACPApiError("Failed to parse ACP jobs response") from e

        if data.get("error"):
            raise ACPApiError(data["error"]["message"])

        return data.get("data", [])

    def _hydrate_jobs(
        self,
        raw_jobs: List[dict],
        *,
        log_prefix: str = "Skipped",
    ) -> List[ACPJob]:
        jobs: List[ACPJob] = []
        errors: list[dict] = []

        for job in raw_jobs:
            try:
                memos = [
                    ACPMemo(
                        contract_client=self.contract_client_by_address(
                            job.get("contractAddress")
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
                        txn_hash=memo.get("txHash"),
                        signed_txn_hash=memo.get("signedTxHash"),
                        state=ACPMemoState(memo.get("state")) if memo.get("state") else None,
                    )
                    for memo in job.get("memos", [])
                ]

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
                        client_address=job.get("clientAddress"),
                        provider_address=job.get("providerAddress"),
                        evaluator_address=job.get("evaluatorAddress"),
                        price=job.get("price"),
                        price_token_address=job.get("priceTokenAddress"),
                        memos=memos,
                        phase=job.get("phase"),
                        context=context,
                        contract_address=job.get("contractAddress"),
                        net_payable_amount=job.get("netPayableAmount"),
                        deliverable=job.get("deliverable"),
                    )
                )

            except Exception as e:
                errors.append(
                    {
                        "job_id": job.get("id"),
                        "error": e,
                    }
                )

            if errors:
                payload = [
                    {
                        "job_id": e["job_id"],
                        "message": str(e["error"]),
                    }
                    for e in errors
                ]

                logger.warning(
                    "[ACP] %s %d malformed job(s):\n%s",
                    log_prefix,
                    len(errors),
                    json.dumps(payload, indent=2),
                )

        return jobs

    def get_job_by_onchain_id(self, onchain_job_id: int) -> "ACPJob":
        url = f"{self.acp_url}/jobs/{onchain_job_id}"
        headers = {"wallet-address": self.wallet_address}

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
                        contract_client=self.acp_contract_client,
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
                        txn_hash=memo.get("txHash"),
                        signed_txn_hash=memo.get("signedTxHash"),
                        state=ACPMemoState(memo.get("state")) if memo.get("state") else None,
                    )
                )

            context = data.get("data", {}).get("context")
            if isinstance(context, str):
                try:
                    context = json.loads(context)
                except json.JSONDecodeError:
                    context = None

            job = data.get("data", {})
            return ACPJob(
                acp_client=self,
                id=job["id"],
                client_address=job["clientAddress"],
                provider_address=job["providerAddress"],
                evaluator_address=job["evaluatorAddress"],
                price=job["price"],
                price_token_address=job["priceTokenAddress"],
                memos=memos,
                phase=job["phase"],
                context=context,
                contract_address=job.get("contractAddress"),
                net_payable_amount=job.get("netPayableAmount"),
                deliverable=job.get("deliverable"),
            )
        except Exception as e:
            raise ACPApiError(f"Failed to get job by onchain ID: {e}")

    def get_memo_by_id(self, onchain_job_id: int, memo_id: int) -> "ACPMemo":
        url = f"{self.acp_url}/jobs/{onchain_job_id}/memos/{memo_id}"
        headers = {"wallet-address": self.wallet_address}

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            if data.get("error"):
                raise ACPApiError(data["error"]["message"])

            memo = data.get("data", {})

            return ACPMemo(
                contract_client=self.acp_contract_client,
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
                txn_hash=memo.get("txHash"),
                signed_txn_hash=memo.get("signedTxHash"),
                state=ACPMemoState(memo.get("state")) if memo.get("state") else None,
            )

        except Exception as e:
            raise ACPApiError(f"Failed to get memo by ID: {e}")

    def get_agent(self, wallet_address: str, *, show_hidden_offerings: bool = False) -> Optional[IACPAgent]:
        url = f"{self.acp_url}/agents?filters[walletAddress]={wallet_address}"

        if show_hidden_offerings:
            url += f"&showHiddenOfferings=true"

        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            agents_data = data.get("data", [])
            if not agents_data:
                return None

            agent_data = agents_data[0]
            return self._hydrate_agent(agent_data)

        except requests.exceptions.RequestException as e:
            raise ACPApiError(f"Failed to get agent: {e}")
        except Exception as e:
            raise ACPError(f"An unexpected error occurred while getting agent: {e}")

    def get_memo_content(self, url: str) -> str:
        response = self.acp_client.request("GET", url)

        if not response:
            raise ACPApiError("Failed to get memo content")

        return response["content"]


# Rebuild the AcpJob model after VirtualsACP is defined
ACPJob.model_rebuild()
ACPMemo.model_rebuild()
ACPJobOffering.model_rebuild()
ACPResourceOffering.model_rebuild()
