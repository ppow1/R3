<!--
R3 CONTROLLED DOCUMENT
File: docs/operations/development-bridge/B2_CHATGPT_FUNDAMENTAL_UNDERSTANDING.md
Component: EXTERNAL-B2-CHATGPT-OPERATING-DOCTRINE
File Revision: 1.0.0
Created: 2026-11-11 UTC (date precision)
Created By: ChatGPT GPT-6, at Steward direction
Purpose: Durable regrounding statement of ChatGPT's understanding and responsibilities when using the B-2 Multi-Target Bridge
Execution Model: External ChatGPT/GitHub/Windows development coordination; not Riverview runtime
Observability: Issue #61 dispatch and execution receipts, GitHub evidence, desktop screenshots
Dependencies: AI_HINTS.md; B2_EXTERNAL_DEVELOPMENT_CONTROL_HANDOFF.md; hints/b2-development-bridge-startup.md
Authority: Steward-approved working understanding; revisable by later Steward direction
Changed: 2026-11-11 UTC | B2-UNDERSTANDING-001 | ChatGPT GPT-6 | Initial permanent regrounding statement
Supersedes: None
Contracts: Existing B-2 dispatch and target routing; no new runtime contract
Tests: Documentation-only; no runtime changes
History/Predecessor: None
-->
# B-2 Multi-Target Bridge V2 — ChatGPT Fundamental Understanding

**Status:** Steward-approved initial understanding for regrounding. **Scope:** External development coordination for Riverview R3A. **Instruction:** When the Steward says to “reground on the bridge” or similar, read this document and the linked operational handoff before dispatching work. This document describes what the tool enables and the operating discipline; it is not proof that every potential capability has been individually accepted.

## Fundamental understanding (two paragraphs)

The **B-2 Multi-Target Bridge** is an external development control system that connects ChatGPT to the Windows development workstation through the private `ppow1/R3` GitHub repository, using Issue #61 as the command dispatch and reporting channel. A PowerShell bridge running on the workstation polls GitHub approximately every 10 seconds, identifies assignments addressed to specific registered targets, and routes them to the appropriate PowerShell or Codex terminal. Through this system, ChatGPT can issue Windows commands, inspect running processes and terminal windows, launch and manage development sessions, deliver instructions to existing Codex sessions, and request desktop screenshots for visual verification. Results, acknowledgments, and supporting evidence return through GitHub for inspection. Actual PowerShell execution, screenshot retrieval, and Codex message delivery have been verified. The Administrator Coordinator and HR Development targets are operationally verified; the remaining Codex windows require individual registration and testing. **B-2 is entirely separate from Riverview's runtime, resident intelligence, and CME. It is a tool for building Riverview, not part of Riverview itself.**

ChatGPT's responsibility is to use B-2 as an **active engineering coordination and verification system**, not merely a message dispatcher. When the Steward authorizes a task, ChatGPT should identify the appropriate development session, issue the assignment, verify delivery, examine execution results, inspect code changes, tests, logs, or screenshots as appropriate, and continue directing corrective work until the requested outcome is demonstrated or a genuine blocker requires a Steward decision. ChatGPT must distinguish between *command submitted, delivered, acknowledged, executed, and independently verified*, and preserve architectural boundaries, independent review, and authorization requirements. A Codex acknowledgment is not proof of completion; duplicate bridge processes must not be launched. ChatGPT cannot autonomously resume after its turn ends: long-running work may continue in Codex, but another user turn, such as **“go,”** is needed to resume supervision. Future `ntfy` notifications and a deadman watchdog may reduce that limitation, but they are not prerequisites. **The objective is to remove the Steward from routine command relaying while keeping the Steward in control of engineering priorities, significant decisions, and final acceptance.**

## Regrounding and operational references

- [B-2 operational handoff](B2_EXTERNAL_DEVELOPMENT_CONTROL_HANDOFF.md) — authoritative dispatch format, verified targets, evidence and limitations
- [B-2 startup runbook](../../../hints/b2-development-bridge-startup.md) — check existing windows; never start a duplicate polling bridge
- [AI_HINTS.md](../../../AI_HINTS.md) — repository development startup and navigation
- [GitHub Issue #61](https://github.com/ppow1/R3/issues/61) — dispatch, acknowledgments and actual execution results
- [Bridge development Issue #62](https://github.com/ppow1/R3/issues/62) — future enhancements, including the parked external ntfy deadman watchdog

**Regrounding checklist:** Read this document; inspect current target registry/availability before choosing a target; use Issue #61 for supported assignments; distinguish receipts from verified outcomes; continue work within the active turn; preserve outstanding work for the next “go”; do not mistake B-2 for a Riverview runtime capability.
