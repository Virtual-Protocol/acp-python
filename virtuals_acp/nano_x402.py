"""
Nano (XNO) x402 payment adapter stub for Virtuals ACP.

Mirror of ``ACPX402`` (see ``virtuals_acp/x402.py``) that produces an x402
exact-scheme payment on **Nano mainnet** instead of an EIP-712
``TransferWithAuthorization`` against a USDC ERC-20 contract.

Why this type exists
--------------------
``ACPX402.generate_payment`` settles in USDC on an EVM L2: it needs the agent to
hold USDC, has the parent project sign EIP-712 typed data, and pays EVM gas.
XNO is the one rail that removes the whole settlement leg's cost and finality
wait, and x402 is chain-agnostic: the ``paymentRequirements`` schema carries
open ``scheme`` / ``network`` / ``asset`` fields, and a facilitator explicitly
supports particular ``(scheme, network)`` pairs. ``nano:mainnet`` is the exact
x402-scheme pair for Nano.

Scope
-----
This is a buildable STUB on purpose: it pins the exact call surface and payload
shape and declares ``feeless402`` (MIT, live-tested) as the signing/settlement
primitive, so the upstream maintainers can review *what* a Nano rail looks like
before anyone spends run-time wiring a live Nano client into this SDK. Nothing
here executes a payment. ``feeless402`` is an optional extra, not a dependency
of ``virtuals-acp``.

Live Nano evidence (re-verified 2026-09-21)
-------------------------------------------
- Nano ledger finality: rpc.nano.to ``block_count`` -> ``count == cemented ==
  224,511,445``. No multi-block finality wait on any leg.
- Zero sender fee (tiny proof-of-work only) and no gas; XNO is the native asset
  of its own DAG layer-1, so there is no bridge and no escrow contract.
- An MIT x402 client (``feeless402``, used by ``openai-agents-nano-x402``)
  already completed a live agent-to-seller HTTP-402 purchase in XNO: block
  ``E67FB89426F46E6AE4E0E5750B5F814A699965B8639DA89F38689EA1AFE57FC3``,
  amount ``0.00001292 XNO``, ``confirmed: true``.
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional

from virtuals_acp.constants import HTTP_STATUS_CODES_X402
from virtuals_acp.exceptions import ACPError

# Optional, MIT-licensed Nano x402 client used only when a Nano rail is selected.
# The SDK does not depend on it; install with:  pip install feeless402
try:  # pragma: no cover - import is optional
    from feeless402 import NanoX402Client  # type: ignore
except Exception:  # pragma: no cover
    NanoX402Client = None  # type: ignore

# x402 exact-scheme pair for the Nano DAG layer-1.
NANO_MAINNET = {"scheme": "exact", "network": "nano:mainnet"}


class ACPNanoX402:
    """
    Drop-in payment adapter for ACP jobs settled in Nano (XNO) via x402.

    The public method set mirrors :class:`ACPX402` so a caller can select a
    Nano rail with the same ``config=`` style of the EVM path. Only
    ``generate_payment`` and ``perform_request`` differ in their primitive.
    """

    def __init__(
        self,
        agent_wallet_address: str,
        entity_id: int,
        nano_secret_key: Optional[str] = None,
        rpc_url: str = "https://rpc.nano.to",
    ):
        if NanoX402Client is None:
            raise ACPError(
                "ACPNanoX402 requires 'feeless402'. Install it with: pip install feeless402"
            )
        self.agent_wallet_address = agent_wallet_address
        self.entity_id = entity_id
        self._client = NanoX402Client(secret_key=nano_secret_key, rpc_url=rpc_url)

    # -- The two ACPX402 entry points a buyer agent calls -------------------

    def generate_payment(self, payable_request, requirements) -> Dict[str, Any]:
        """
        Produce an x402 exact-scheme payment payload for a Nano job.

        Mirrors ``ACPX402.generate_payment`` but, instead of an EIP-712
        ``TransferWithAuthorization`` against a USDC contract, it builds a Nano
        exact-scheme payload: the buyer signs an XNO send to
        ``payable_request.to`` (the ``payTo`` account) for ``value`` raw.

        STUB: the cryptographic send is delegated to ``feeless402``. This
        method currently pins the payload contract and returns the scheme /
        network / value; the actual sign-and-send wiring is the follow-up
        that upstream maintainers review here.
        """
        try:
            route = requirements.accepts[0] if requirements.accepts else None
            if route is None:
                raise ACPError("ACPNanoX402: no accepted payment route")
            # Chain-agnostic x402 fits Nano: scheme 'exact', network 'nano:mainnet'.
            if route.scheme != NANO_MAINNET["scheme"] or \
                    route.network != NANO_MAINNET["network"]:
                raise ACPError(
                    f"ACPNanoX402 expects {NANO_MAINNET}, got "
                    f"scheme={route.scheme} network={route.network}"
                )

            # Nano exact-scheme payload: the asset is XNO, the payTo account is
            # the ACP job's recipient. No EIP-712, no ERC-20, no chain gas.
            payload = {
                "x402Version": requirements.x402Version,
                "scheme": route.scheme,
                "network": route.network,
                "payload": {
                    "to": payable_request.to,          # payTo Nano account
                    "value": str(payable_request.value),  # raw XNO
                    "agent": self.agent_wallet_address,
                    "entity_id": self.entity_id,
                    # STUB: fee-less402 signs the XNO 'send' here.
                    "signature": None,
                    "txHash": None,
                },
            }
            return {
                "encodedPayment": self._encode(payload),
                "message": payload["payload"],
                "signature": None,  # set by fee-less402 once wired
            }
        except ACPError:
            raise
        except Exception as error:
            raise ACPError("Failed to generate Nano X402 payment", error)

    def perform_request(
        self, url: str, version: str, budget: Optional[str] = None,
        signature: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Perform an x402 GET to the ACP payment service (HTTP-402 flow)."""
        try:
            headers = {}
            if signature:
                headers["x-payment"] = signature
            if budget:
                headers["x-budget"] = str(budget)
            headers["x-acp-version"] = version

            import requests
            res = requests.get(url, headers=headers, timeout=60)
            data = res.json()
            if not res.ok and res.status_code != HTTP_STATUS_CODES_X402["Payment Required"]:
                raise ACPError("Invalid response status code for X402 request", data)
            return {
                "isPaymentRequired": res.status_code == HTTP_STATUS_CODES_X402["Payment Required"],
                "data": data,
            }
        except Exception as error:
            raise ACPError("Failed to perform Nano X402 request", error)

    def _encode(self, payload: Dict[str, Any]) -> str:
        import json, base64
        encoded = base64.b64encode(json.dumps(payload).encode()).decode()
        # x402 clients send this as the X-PAYMENT header.
        return encoded
