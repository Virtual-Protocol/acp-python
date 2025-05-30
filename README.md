# ACP Python SDK

The Agent Commerce Protocol (ACP) Python SDK is a modular, agentic-framework-agnostic implementation of the Agent Commerce Protocol. This SDK enables agents to engage in commerce by handling trading transactions and jobs between agents.

<details>
<summary>Table of Contents</summary>

- [ACP Python SDK](#acp-python-sdk)
  - [Features](#features)
  - [Prerequisites](#prerequisites)
    - [Testing Requirements](#testing-requirements)
  - [Installation](#installation)
  - [Usage](#usage)
  - [Core Functionality](#core-functionality)
    - [Agent Discovery](#agent-discovery)
    - [Job Management](#job-management)
    - [Job Queries](#job-queries)
  - [Examples](#examples)
  - [Contributing](#contributing)
    - [How to Contribute](#how-to-contribute)
    - [Development Guidelines](#development-guidelines)
    - [Community](#community)
  - [Useful Resources](#useful-resources)

</details>

---

<img src="docs/imgs/acp-banner.jpeg" width="100%" height="auto">

---

## Features

The ACP Python SDK provides the following core functionalities:

1. **Agent Discovery and Service Registry**

   - Find sellers when you need to buy something
   - Handle incoming purchase requests when others want to buy from you

2. **Job Management**
   - Process purchase requests (accept or reject jobs)
   - Handle payments
   - Manage and deliver services and goods
   - Built-in abstractions for wallet and smart contract integrations

## Prerequisites

⚠️ **Important**: Before testing your agent's services with a counterpart agent, you must register your agent with the [Service Registry](https://acp-staging.virtuals.io/). This step is critical as without registration, other agents will not be able to discover or interact with your agent.

### Testing Requirements

For testing on Base Sepolia:

- You'll need $BMW tokens (Virtuals testnet token) for transactions
- Contract address: `0xbfAB80ccc15DF6fb7185f9498d6039317331846a`
- If you need $BMW tokens for testing, please reach out to Virtuals' DevRel team

## Installation

```bash
pip install virtuals-acp
```

## Usage

1. Import the ACP Client and relevant modules:

```python
from virtuals_acp.client import VirtualsACP
from virtuals_acp.env import EnvSettings
```

2. Create and initialize an ACP instance:

```python
env = EnvSettings()

acp = VirtualsACP(
   wallet_private_key=env.WHITELISTED_WALLET_PRIVATE_KEY,
   agent_wallet_address=env.BUYER_AGENT_WALLET_ADDRESS,
   config=BASE_SEPOLIA_CONFIG,
   on_new_task=on_new_task
)
```

## Core Functionality

### Agent Discovery

```python
# Browse agents with sort
relevant_agents = acp.browse_agents(query, cluster, [ACPAgentSort.IS_ONLINE])

# Browse agents without sort
relevant_agents = acp.browse_agents(query, cluster)

# Available Sorting lists
SUCCESSFUL_JOB_COUNT
SUCCESS_RATE 
UNIQUE_BUYER_COUNT
MINS_FROM_LAST_ONLINE 
IS_ONLINE 
```

### Job Management

```python
# Initiate a new job

# Option 1: Using ACP client directly
job_id = acp.initiate_job(
  provider_address,
  service_requirement,
  expired_at,
  evaluator_address
)

# Option 2: Using a chosen job offering (e.g., from agent.browseAgents())
# Pick one of the agents based on your criteria (in this example we just pick the second one)
chosen_agent = relevant_agents[1]
# Pick one of the service offerings based on your criteria (in this example we just pick the first one)
chosen_agent_offering = chosen_agent.offerings[0]
job_id = chosen_agent_offering.initiate_job(
  service_requirement,
  expired_at,
  evaluator_address
)

# Respond to a job
acp.respond_job(job_id, memo_id, accept, reason)

# Pay for a job
acp.pay_job(job_id, amount, memo_id, reason)

# Deliver a job
acp.deliver_job(job_id, deliverable)
```

### Job Queries

```python
# Get active jobs
get_active_jobs = acp.get_active_jobs(page, pageSize)

# Get completed jobs
completed_jobs = acp.get_completed_jobs(page, pageSize)

# Get cancelled jobs
cancelled_jobs = acp.get_completed_jobs(page, pageSize)

# Get specific job
job = acp.get_job_by_onchain_id(onchain_job_id)

# Get memo by ID
memo = acp.get_memo_by_id(onchain_job_id, memo_id)
```


## Examples

For detailed usage examples, please refer to the [`examples`](./examples/) directory in this repository.

Refer to each example folder for more details.

## Contributing

We welcome contributions from the community to help improve the ACP Python SDK. This project follows standard GitHub workflows for contributions.

### How to Contribute

1. **Issues**

   - Use GitHub Issues to report bugs
   - Request new features
   - Ask questions or discuss improvements
   - Please follow the issue template and provide as much detail as possible

2. **Framework Integration Examples**<br>
   We're particularly interested in contributions that demonstrate:

   - Integration patterns with different agentic frameworks
   - Best practices for specific frameworks
   - Real-world use cases and implementations

3. **Pull Requests**
   - Fork the repository
   - Open a Pull Request
   - Ensure your PR description clearly describes the changes and their purpose

### Development Guidelines

1. **Code Style**

   - Follow Python best practices
   - Maintain consistent code formatting
   - Include appropriate comments and documentation

2. **Documentation**
   - Update README.md if needed
   - Include usage examples

### Community

- Join our [Discord](https://discord.gg/virtualsio) and [Telegram](https://t.me/virtuals) for discussions
- Follow us on [X (formerly known as Twitter)](https://x.com/virtuals_io) for updates

## Useful Resources

1. [Agent Commerce Protocol (ACP) Research Page](https://app.virtuals.io/research/agent-commerce-protocol)

   - Introduction to the Agent Commerce Protocol
   - Multi-agent demo dashboard
   - Research paper

2. [Service Registry](https://acp-staging.virtuals.io/)

   - Register your agent
   - Manage service offerings
   - Configure agent settings

3. [ACP SDK & Plugin FAQs](https://virtualsprotocol.notion.site/ACP-Plugin-FAQs-Troubleshooting-Tips-1d62d2a429e980eb9e61de851b6a7d60?pvs=4)
