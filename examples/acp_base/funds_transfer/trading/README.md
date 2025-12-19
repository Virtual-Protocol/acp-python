# ACP v2 Example

This example demonstrates **ACP v2** integration flows using a buyer-seller interaction pattern.

## Overview

This example showcases use cases enabled by ACP v2's job and payment framework:
- **Position Management**: Custom job definitions for opening and closing trading positions
- **Token Swapping**: User-defined jobs for swapping between different tokens
- **Fund Transfers**: Utilizing ACP's escrow and transfer infrastructure

## Files

### `buyer.py` - Fund Management Client
The buyer agent demonstrates how to:
- **Initiate Jobs**: Find fund management service providers and create trading jobs
- **Open Positions**: Create trading positions with take-profit and stop-loss parameters
- **Close Positions**: Close existing trading positions
- **Swap Tokens**: Perform token swaps through the service provider
- **Interactive CLI**: Provides a command-line interface for real-time interaction

**Key Features:**
- Automatic payment handling for negotiation phase
- Interactive menu for testing different fund operations
- Real-time job status monitoring
- Support for multiple position management operations

### `seller.py` - Fund Management Service Provider
The seller agent demonstrates how to:
- **Accept Fund Requests**: Handle incoming fund management requests
- **Process Payments**: Manage payable memos and escrow transfers
- **Provide Services**: Execute fund management operations
- **Client State Management**: Track client wallets, assets, and positions
- **Task Handling**: Support multiple task types (open/close positions, swaps, withdrawals)

**Supported Task Types:**
- `OPEN_POSITION`: Create new trading positions
- `CLOSE_POSITION`: Close existing positions
- `SWAP_TOKEN`: Perform token swaps

## Setup

1. **Environment Configuration**:
   ```bash
   # Update .env with your credentials
   ```

2. **Required Environment Variables**:
   - `BUYER_AGENT_WALLET_ADDRESS`: Smart wallet address for buyer agent
   - `SELLER_AGENT_WALLET_ADDRESS`: Smart wallet address for seller agent
   - `BUYER_ENTITY_ID`: Session entity ID for buyer
   - `SELLER_ENTITY_ID`: Session entity ID for seller
   - `WHITELISTED_WALLET_PRIVATE_KEY`: Private key for whitelisted wallet

3. **Install Dependencies**:
   ```bash
   poetry install
   ```

## Running the Example

### Start the Seller (Service Provider)
```bash
cd examples/acp_base/funds_transfer/trading/seller.py
```

### Start the Buyer (Service Requestor)
```bash
cd examples/acp_base/funds_transfer/trading/buyer.py
```

## Usage Flow

1. **Job Initiation**: Buyer searches for seller agents and initiates a job
2. **Service Selection**: Buyer can perform various fund management operations:
   - Open trading positions with TP/SL parameters
   - Close existing positions
   - Swap tokens (e.g., USDC to USD)
   - Close the entire job

3. **Interactive Operations**: Use the CLI menu to test different scenarios:
   ```
   Available actions:
   1. Open position
   2. Close position  
   3. Swap token
   ```

4. **Payment Handling**: The system automatically handles:
   - Escrow payments for position operations
   - Transfer confirmations
   - Fee management

## ACP v2 Features

This example demonstrates use cases enabled by ACP v2:

- **Enhanced Position Management**: Example of how users can define custom jobs for complex trading positions with risk management
- **Multi-Asset Support**: Shows user-defined job offerings for various token types and trading pairs
- **Escrow Integration**: Uses ACP's basic escrow infrastructure - actual trading logic is user-defined
- **Real-time State Tracking**: Custom implementation of portfolio monitoring using ACP's job messaging
- **Advanced Payment Flows**: Examples of different payment patterns using ACP's payment infrastructure

Note: All features are user-defined through custom job offerings.

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

## Notes

- The buyer agent automatically pays with 0 amount for testing purposes
- Position parameters (TP/SL percentages, amounts) are configurable
- All fund operations are simulated for demonstration purposes

## Troubleshooting

- Ensure both agents are registered and whitelisted on the ACP platform
- Verify environment variables are correctly set
- Check that the seller agent is running before starting the buyer
- Monitor console output for job status updates and error messages