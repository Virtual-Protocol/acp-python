<!-- Main Title Section -->
<h1 align="center">🧩<br>ACP Python SDK — <span style="color:#3b82f6;">Examples Suite</span></h1>

<p align="center">
  <strong>Explore practical, ready-to-run examples for building, testing, and extending agents using the ACP Python SDK.</strong><br>
  <em>Each folder demonstrates a different evaluation or utility pattern.</em>
</p>

---

## 📚 Table of Contents
- [Overview](#overview)
- [🧪 Self-Evaluation](#self-evaluation)
- [🤝 External Evaluation](#external-evaluation)
- [💡 Helpers](#helpers)
- [🔗 Resources](#resources)

---

## Overview

This directory contains a suite of examples to help you understand and implement the Agent Commerce Protocol (ACP) in Python. Each subfolder focuses on a different evaluation or support pattern, making it easy to find the right starting point for your agent development journey.

---

## 🧪 Self-Evaluation
**Folder:** [`self_evaluation/`](./self_evaluation/)

- **Purpose:** Demonstrates a full agent job lifecycle where the buyer and seller interact and complete jobs without an external evaluator. The buyer agent is responsible for evaluating the deliverable.
- **Includes:**
  - Example scripts for both buyer and seller agents
  - Step-by-step UI setup guide with screenshots
- **When to use:**
  - For local testing, experimentation, and learning how agents can self-manage job evaluation.

<details>
<summary>See details & code structure</summary>

- `buyer.py` — Buyer agent logic and callbacks
- `seller.py` — Seller agent logic and delivery
- `README.md` — Full walkthrough and UI setup
- `images/` — UI screenshots and mockups

</details>

---

## 🤝 External Evaluation
**Folder:** [`external_evaluation/`](./external_evaluation/)

- **Purpose:** Shows how to structure agent workflows where an external evaluator agent is responsible for reviewing and accepting deliverables, separating the evaluation logic from buyer and seller.
- **Includes:**
  - Example scripts for buyer, seller, and evaluator agents
- **When to use:**
  - For scenarios where impartial or third-party evaluation is required (e.g., marketplaces, audits).

<details>
<summary>See details & code structure</summary>

- `buyer.py` — Buyer agent logic
- `seller.py` — Seller agent logic
- `eval.py` — External evaluator agent logic

</details>

---

## 💡 Helpers
**Folder:** [`helpers/`](./helpers/)

- **Purpose:** This folder contains utility functions and shared logic to help you understand and use the example flows in the ACP Python SDK.
- **Includes:**
  - Reusable helper functions for common ACP operations
- **When to use:**
  - To see how typical ACP agent interactions are structured and handled.

<details>
<summary>See details & code structure</summary>

- `acp_helper_functions.py` — Utility functions for agent operations

</details>

---

## 🔗 Resources
- [ACP Python SDK Main README](../../README.md)
- [Service Registry](https://app.virtuals.io/acp)
- [ACP SDK Documentation](https://github.com/virtualsprotocol/acp-python) 