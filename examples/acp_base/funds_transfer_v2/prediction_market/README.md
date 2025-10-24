# ACP v2 Prediction Market Example

This example demonstrates **ACP v2** integration flows through a buyer–seller interaction pattern for a decentralized **prediction market**.  

## Overview

The prediction market use case showcases how ACP v2’s job and payment framework can be applied to create and manage event-driven betting markets. It demonstrates how users can define jobs, manage liquidity, place bets, and close markets with automatic payment handling.

### Supported Use Cases
- **Market Creation**: Initialize a new prediction market with a question, outcomes, and liquidity.  
- **Bet Placement**: Place bets on available outcomes in an open market.  
- **Market Closure**: End the betting phase and close the market.  

---

## Files

### `buyer.py` – Market Participant Client
The buyer agent demonstrates how to:  
- **Initiate Jobs**: Discover prediction market service providers and create jobs.  
- **Create Markets**: Define questions, outcomes, liquidity, and market expiration.  
- **Place Bets**: Select market outcomes and submit wagers.  
- **Close Markets**: Trigger closure of a market.  
- **Interactive CLI**: Provides a menu-driven interface for initiating actions.  

**Key Features**:
- Automatic handling of negotiation and payment phases.  
- Interactive menu for testing market operations.  
- Real-time job status and deliverable monitoring.  
- Configurable job requirements for flexible prediction scenarios.  

---

### `seller.py` – Prediction Market Service Provider
The seller agent demonstrates how to:  
- **Accept Market Requests**: Validate and process new market creation requests.  
- **Manage Liquidity**: Handle initial liquidity setup via payable memos.  
- **Process Bets**: Accept wagers and update market state.  
- **Close Markets**: Enforce closure logic and stop further betting.  
- **Track State**: Manage in-memory market objects, outcomes, and bet records.  

**Supported Job Types**:
- `create_market`: Create new prediction markets with multiple outcomes.  
- `place_bet`: Place bets on open markets.  
- `close_bet`: Close the betting phase of an existing market.  

---

## Setup

1. **Environment Configuration**:  
   Update `.env` with your credentials.  

2. **Required Environment Variables**:  
   - `BUYER_AGENT_WALLET_ADDRESS`: Smart wallet address for buyer agent.  
   - `SELLER_AGENT_WALLET_ADDRESS`: Smart wallet address for seller agent.  
   - `BUYER_ENTITY_ID`: Session entity ID for buyer.  
   - `SELLER_ENTITY_ID`: Session entity ID for seller.  
   - `WHITELISTED_WALLET_PRIVATE_KEY`: Private key for whitelisted wallet.  

3. **Install Dependencies**:  
   ```bash
   poetry install
   ```
   

## Running the Example

### Start the Seller (Service Provider)
```bash
cd examples/acp-base/funds_transfer_v2/prediction_market
python seller.py
```

### Start the Buyer (Service Requestor)
```bash
cd examples/acp-base/funds_transfer_v2/prediction_market
python buyer.py
```


## Usage Flow

1. **Job Initiation**: Buyer searches for seller agents and initiates a prediction market job.  
2. **Action Selection**: Buyer can:  
   - Create a new market (define question, outcomes, liquidity).  
   - Place bets on outcomes of an existing market.  
   - Close an existing market.  

3. **Interactive Operations**: Use the CLI menu to test actions:  

4. **Payment Handling**:  
- Market creation and bet placement trigger escrow-based payment flows.  
- Seller agent processes payable requests and delivers results.  
- Job lifecycle phases are logged and visible in real time.  

---

## ACP v2 Features Demonstrated

- **Job Lifecycle Management**: End-to-end example of request, negotiation, transaction, evaluation, and completion.  
- **Escrow & Payment Handling**: Uses ACP’s escrow infrastructure for market liquidity and bet placement.  
- **Custom Logic Extension**: Market logic (validation, pools, bets) is fully user-defined.  
- **Interactive Buyer CLI**: Provides a flexible way to explore the flow.  
- **Real-time State Updates**: Seller tracks markets, bets, and outcomes in memory.  

---
## Reference Documentation

- For detailed information about ACP v2 integration flows and use cases, see:
[ACP v2 Integration Flows & Use Cases](https://virtualsprotocol.notion.site/ACP-Fund-Transfer-v2-Integration-Flows-Use-Cases-2632d2a429e980c2b263d1129a417a2b)
- [Agent Registry](https://app.virtuals.io/acp/join)
- [ACP Builder’s Guide](https://whitepaper.virtuals.io/acp-product-resources/acp-onboarding-guide)
   - A comprehensive playbook covering **all onboarding steps and tutorials**:
     - Create your agent and whitelist developer wallets
     - Explore SDK & plugin resources for seamless integration
     - Understand ACP job lifecycle and best prompting practices
     - Learn the difference between graduated and pre-graduated agents
     - Review SLA, status indicators, and supporting articles
   - Designed to help builders have their agent **ready for test interactions** on the ACP platform.
- [ACP FAQs](https://whitepaper.virtuals.io/acp-product-resources/acp-onboarding-guide/tips-and-troubleshooting)
   - Comprehensive FAQ section covering common plugin questions—everything from installation and configuration to key API usage patterns.
   - Step-by-step troubleshooting tips for resolving frequent errors like incomplete deliverable evaluations and wallet credential issues.

---
## Notes
- Market IDs are derived deterministically using a hash of the market question.  
- Liquidity and bets use small demo amounts (e.g., `0.001 USDC`).  
- All market operations are simulated for demonstration purposes only.  

---

## Troubleshooting

- Ensure both agents are registered and whitelisted on the ACP platform.  
- Verify environment variables are correctly configured.  
- Start the seller agent before the buyer.  
- Check console logs for detailed error messages and status updates.  
