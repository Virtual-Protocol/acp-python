## Fee-free, bridge-free settlement option (Nano XNO) for x402 jobs

Adds an opt-in, zero-risk docs + example for paying an HTTP-402-priced ACP job in **Nano (XNO)** — alongside, not instead of, the existing EVM/USDC `ACPX402` path in `virtuals_acp/x402.py`.

### Why

`ACPX402.generate_payment` settles in **USDC on an EVM L2** (EIP-712 `TransferWithAuthorization` against a `usdc_contract`), so every x402 job needs the agent to hold USDC and pay L2 gas; a cross-chain job adds a LayerZero hop. XNO is the one rail that removes all three costs on the settlement leg:

- **Instant finality** — on the live Nano ledger `block_count == cemented_count` (224,492,883+ at measurement), so there is no multi-block wait for an ACP job to settle.
- **Fee-less** — no sender fee and no gas on any chain, only a tiny proof-of-work.
- **No bridge** — XNO is its own layer-1 DAG, so a buyer on Base and a seller on Arbitrum settle with identical cost and finality, never touching a bridge.

### It is real, not hypothetical

A thin MIT adapter on the `feeless402` client already completed a **live agent-to-seller HTTP-402 purchase in XNO**: a chat completion bought from the independent host `api.nano-gpt.com` for `0.00001292 XNO`, block `E67FB89426F46E6AE4E0E5750B5F814A699965B8639DA89F38689EA1AFE57FC3` (`confirmed: true`, Nano mainnet, 2026-09-18). Full docs in `docs/nano-x402-settlement.md`.

### Scope

- `docs/nano-x402-settlement.md` — new guide with measured live numbers and a `feeless402` example.
- `README.md` — one link added under "Useful Resources".
- Nothing changes the USDC path, no new runtime dependency, no tests (docs/example only). A follow-up can add a `virtuals_acp/nano_x402.py` mirroring `ACPX402` with tests under `tests/unit/` if the direction is welcome.
