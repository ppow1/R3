# R3A — ChatGPT Lessons Learned Log

**Owner:** ChatGPT coordinating R3A work under the Steward's direction  
**Purpose:** A durable, inspectable record of recurring assistant mistakes, their demonstrated corrections, and concrete preflight checks.  
**Index/discussion:** https://github.com/ppow1/R3/issues/65

## How to use this log

When the Steward says **"What did you learn? Put it in the lessons learned log"**, ChatGPT must add a numbered, dated entry to this file, recording: mistake; ignored prior instructions/evidence; consequence; correct minimal approach; a reusable prevention check; and verification links. Update the issue with the commit.

When the Steward says **"Read your lessons learned log"**, ChatGPT must retrieve this actual repository file, not merely claim to remember it, and apply the relevant lessons to the pending task. If retrieval fails, say so rather than guessing.

**Important:** Writing an entry does not establish future compliance. Future repeated mistakes must be called out and linked back to the earlier entry; corrections are evaluated by observable behavior.

---

## LL-001 — 2026-11-11 — Do not build a new subsystem around an already-proven capability

**Category:** Unnecessary complexity; failure to reuse existing implementation; repeated disregard of corrections.

### Mistake
While expanding Bridge v2 (B-2) from the Live Modular Codex window to an Administrator PowerShell window, ChatGPT repeatedly proposed a new listener, service, or communication mechanism. It also suggested redundant checks and attributed an activation failure to missing elevation even though the bridge window visibly said Administrator. These proposals disregarded the user's repeated explanations and prior end-to-end evidence.

### Already-known facts that should have governed the decision
- GitHub Issue #61 was already a working dispatch channel.
- B-2 polled GitHub and used SendKeys to wake an existing terminal.
- The existing terminal could act on the assignment and post results to GitHub.
- Live Modular had already acknowledged multiple assignments.
- The missing capability was routing to another target, not creating a second transport.
- A PowerShell window could be addressed by a unique title; no listener was required.

### Cost of the mistake
Wasted the Steward's time, created needless deployment and maintenance possibilities, and risked a second competing communications subsystem. The Steward had to interrupt the design repeatedly to restore focus.

### Correct solution and actual evidence
Extend the existing B-2 target selection and preserve the GitHub polling/SendKeys/return loop. Keep the original Live Modular bridge running. Set a unique Administrator window title, then use the Multi-Target bridge to route a read-only inventory assignment.

- Dispatch: https://github.com/ppow1/R3/issues/61#issuecomment-6798754879
- Successful result: https://github.com/ppow1/R3/issues/61#issuecomment-6798932664
- Demonstrated loop: ChatGPT → GitHub → B-2 → Administrator PowerShell → GitHub → ChatGPT.
- Initial `AppActivate=False` retries resulted from the intended window not yet having the configured title; once renamed, the assignment executed.
- Original B-2 correctly ignored the Administrator assignment, demonstrating target isolation.

### Mandatory preflight before proposing infrastructure
1. **Inventory:** What implementation already exists in the project and prior conversation?
2. **Evidence:** What has actually worked end-to-end, not just been designed?
3. **Gap:** What exact behavior is missing?
4. **Minimal change:** Can configuration, routing, or a small extension close that gap?
5. **Necessity:** What specific evidence proves a new subsystem is required?

**Rule:** Reuse demonstrated capabilities before introducing a listener, service, API, database, registry, authorization framework, or other parallel infrastructure. Do not reopen a proven architectural decision without new evidence.

### Verification and status
**Solution verified:** 2026-11-11, by GitHub result comment 6798932664.  
**Behavioral correction:** Not automatically verified by documenting this entry. Recheck on future R3A assignments. If repeated, cite LL-001 and record the recurrence.

---
