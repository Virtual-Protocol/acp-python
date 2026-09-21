"""Unit tests for ACPNanoX402 - the fee-free Nano (XNO) x402 rail for Virtuals ACP.

The adapter is a buildable STUB: it pins the exact call surface and payload shape
and declares feeless402 as the signing primitive, without executing a payment.
These tests prove the parts that CAN and MUST be correct before the stub is
shown to upstream maintainers:

1. generate_payment builds the Nano exact-scheme payload (scheme/network/to/value)
   and validates that the accepted route is nano:mainnet.
2. perform_request detects a 402 (payment required) response and passes through
   a 2xx response.
3. The optional feeless402 client is wired (constructor accepts it when present).

The actual XNO sign-and-send is (by design) the follow-up that upstream reviews;
it is not covered here and must not be claimed as covered.
"""
import json
import base64
from unittest.mock import MagicMock, patch

import pytest

from virtuals_acp.nano_x402 import ACPNanoX402, NANO_MAINNET
from virtuals_acp.models import (
    X402PayableRequest,
    X402PayableRequirements,
    X402Requirement,
    X402RequirementExtra,
)
from virtuals_acp.exceptions import ACPError


NANO_TEST_ACCT = "nano_3vsxftu3ufxzo1pnnbc3o8bm47c1w3r3ok8shw3sxn6fmnxk44g8fpb3drbk"
NANO_AGENT = "nano_3agent00000000000000000000000000000000000000000000000000"


def _make_adapter():
    # The optional feeless402 signing primitive (nano_pay.x402.request_with_payment)
    # may be absent in a minimal env; mock it so the stub constructor resolves.
    with patch("virtuals_acp.nano_x402.request_with_payment", MagicMock()):
        return ACPNanoX402(agent_wallet_address=NANO_AGENT, entity_id=42)


def _nano_requirements(route_scheme="exact", route_network="nano:mainnet"):
    return X402PayableRequirements(
        x402Version=1,
        error="",
        accepts=[
            X402Requirement(
                scheme=route_scheme,
                network=route_network,
                maxAmountRequired="1292",
                resource="https://agent.example/infer",
                description="Nano-settled AI service",
                mimeType="application/json",
                payTo=NANO_TEST_ACCT,
                maxTimeoutSeconds=300,
                asset="XNO",
                extra=X402RequirementExtra(name="AI Service", version="1.0.0"),
                outputSchema={},
            )
        ],
    )


def _nano_payable_request():
    return X402PayableRequest(
        to=NANO_TEST_ACCT,
        value=1292,
        maxTimeoutSeconds=300,
        asset="XNO",
    )


class TestACPNanoX402GeneratePayment:
    """Prove the Nano exact-scheme payload shape and scheme/network validation."""

    def test_nano_mainnet_constant_is_the_exact_pair(self):
        assert NANO_MAINNET == {"scheme": "exact", "network": "nano:mainnet"}

    def test_generate_payment_builds_exact_nano_payload(self):
        adapter = _make_adapter()
        result = adapter.generate_payment(_nano_payable_request(), _nano_requirements())
        decoded = json.loads(base64.b64decode(result["encodedPayment"]))
        assert decoded["scheme"] == "exact"
        assert decoded["network"] == "nano:mainnet"
        payload = decoded["payload"]
        assert payload["to"] == NANO_TEST_ACCT
        assert payload["value"] == "1292"
        assert payload["agent"] == NANO_AGENT
        assert payload["entity_id"] == 42

    def test_generate_payment_rejects_non_nano_route(self):
        adapter = _make_adapter()
        reqs = _nano_requirements(route_scheme="eip-3009", route_network="base")
        with pytest.raises(ACPError, match="expects.*nano:mainnet.*got scheme=eip-3009"):
            adapter.generate_payment(_nano_payable_request(), reqs)


class TestACPNanoX402PerformRequest:
    """Prove the 402/payment-required detection shared with the EVM path."""

    def test_returns_is_payment_required_on_402(self):
        adapter = _make_adapter()
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 402
        mock_resp.json.return_value = {"accepts": []}
        with patch("requests.get", return_value=mock_resp) as mg:
            result = adapter.perform_request(
                url="https://agent.example/infer", version="1.0.0")
        assert result["isPaymentRequired"] is True
        assert result["data"] == {"accepts": []}
        headers = mg.call_args[1]["headers"]
        assert headers["x-acp-version"] == "1.0.0"

    def test_returns_not_payment_required_on_200(self):
        adapter = _make_adapter()
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": "ok"}
        with patch("requests.get", return_value=mock_resp):
            result = adapter.perform_request(
                url="https://agent.example/infer", version="1.0.0")
        assert result["isPaymentRequired"] is False
        assert result["data"] == {"result": "ok"}
