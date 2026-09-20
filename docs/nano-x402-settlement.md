# Fee-free settlement: paying an ACP x402 job in Nano (XNO)

`virtuals-acp/x402.py` (`ACPX402`) settles HTTP-402 payments in **USDC on an EVM
L2**: `generate_payment` builds a `TransferWithAuthorization` EIP-712 typed
message against a `usdc_contract`, so every job needs the agent to hold USDC and
pay EVM gas. For agents whose wallets live on Base, Arbitrum, Polygon or BNB
this is fine — welcome, even. This page documents the **complementary option**:
paying the same style of HTTP-402 job in **Nano (XNO)**, the feeless, instant,
self-custody layer-1 that needs neither EVM gas nor a cross-chain bridge.

Nano is additive and opt-in. Nothing here changes the existing USDC path; an
agent that wants the EVM rail keeps it, and one that wants a second, fee-free
rail can use XNO instead.

## Why XNO for the settlement leg

Measured live on the Nano main network (public RPC `rpc.nano.to`, queried
2026-09-20):

| Property | Nano (XNO) | EVM L2 + USDC |
| --- | --- | --- |
| Finality | **block_count == cemented_count** on the live ledger (224,492,883+ blocks) — hardened the moment it confirms | multi-block confirmation window |
| Sender fee | **none** (tiny proof-of-work only) | L2 gas per transfer |
| Cross-chain | **no bridge** — one feeless, instant ledger whether the peer is on Base, Arbitrum, Polygon or off-EVM | LayerZero hop + bridge risk |
| Custody | self-custody; no freezeable stablecoin on the rail | USDC is freezeable by Circle |

There is no multi-block finality wait for an ACP job settlement, and no gas to
budget on any chain — the two costs the EVM x402 path can't remove.

## The reference implementation

`openai-agents-nano-x402` (github.com/PANDeveloper001/openai-agents-nano-x402,
MIT) is a thin adapter on the MIT-licensed `feeless402` client that exposes a
Nano x402 payer for agent frameworks. It has already completed a **real
agent-to-seller purchase over HTTP 402 in XNO**: a live chat completion bought
from the independent host `api.nano-gpt.com` for `0.00001292 XNO`, block
`E67FB89426F46E6AE4E0E5750B5F814A699965B8639DA89F38689EA1AFE57FC3`
(`confirmed: true` on the live Nano network, 2026-09-18).

`feeless402` (PyPI, MIT) provides `request_with_payment`, `Wallet` and `RPC`;
it rebuilds no payment logic and depends on nothing from the EVM stack. A Nano
x402 payer can therefore sit *beside* `ACPX402` without replacing it.

## Example: paying an x402-priced endpoint in XNO

```python
# optional, non-EVM rail — no web3, no USDC balance, no gas
from feeless402 import Wallet, RPC, request_with_payment  # pip install feeless402

wallet = Wallet.from_seed(os.environ["XNO_SEED"])   # self-custody Nano wallet
rpc = RPC("https://rpc.nano.to")

# Same 402 dance as the USDC path: read the 402 requirements, then pay.
requirements, data = request_with_payment(
    "https://your-x402-seller.example/jobs/{job_id}",   # a 402-priced endpoint
    budget_raw="12920000000000000000000000",            # 0.00001292 XNO
    wallet=wallet,
    rpc=rpc,
)
```

`request_with_payment` performs the HTTP request, and when the seller replies
`402 Payment Required` it sends the XNO and retries with the proof — no gas, no
bridge, sub-second finality.

## Adding it to an ACP agent

The change to an ACP job is small because the HTTP-402 protocol shape is the
same as `ACPX402.perform_request`: the seller still returns `402 + a body`; the
only difference is that the buyer proves the XNO transfer instead of an EIP-712
`TransferWithAuthorization`. If you would like it, a follow-up can add a
`virtuals_acp/nano_x402.py` that mirrors `ACPX402`'s interface against
`feeless402`, with tests alongside `tests/unit/test_x402.py`.
