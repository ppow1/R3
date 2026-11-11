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

## LL-002 — 2026-11-11 — Do not repackage software to make a configuration-only change

**Category:** Immediate recurrence of LL-001; failure to apply a lesson still present in the active conversation; unnecessary user work.

### Mistake
Less than 40 minutes after documenting LL-001, ChatGPT proposed that the Steward download and extract a new ZIP package to add HR Development as a second B-2 Multi-Target destination. It had just established that the existing bridge reads its target mapping from `Riverview-B2-targets.json`. The proposed package replaced files unnecessarily, requiring download, extraction, and extra user steps for what should have been a configuration-only edit.

### Known evidence ignored
- B-2 Multi-Target already ran successfully with the Administrator Coordinator target.
- The target list was externalized in `Riverview-B2-targets.json` specifically to support multiple window targets.
- The next requested behavior was simply to add `HR Development` → `HR - Vicky | hr-development`.
- LL-001's mandatory preflight and minimal-change rule had just been written and were still in the active conversation.

### Impact
The Steward had to stop the work again. This immediately undermined the purpose of the lessons log and created avoidable installation and replacement risks. The failure was not missing memory or an expired context window; the relevant lesson was readily available and was not applied.

### Correct approach
Inspect the existing target configuration and bridge contract, modify only the target mapping, restart only the affected Multi-Target bridge if configuration is loaded at startup, and run a harmless GitHub dispatch to verify routing. Preserve the original Live Modular instance. Do not ship a new ZIP or script unless an actual code defect is demonstrated. The specific JSON shape must be checked against the installed file before editing, not assumed from an example.

### Mandatory prevention check
Before creating any artifact, download, script, or deployment instruction for an existing system, explicitly check: **Is the requested behavior already supported by the installed code, and can it be accomplished by editing existing configuration?** If yes, use that path and do not manufacture a replacement package. For recurring failures, read the previous lesson and name how the proposed action avoids repeating it **before** proceeding.

### Verification and status
**Documentation:** This entry records the repeat failure and correction. **Runtime configuration and HR target delivery:** Not yet verified by this entry. Do not report the HR routing test as complete until a real GitHub result confirms it.

**Related:** LL-001; https://github.com/ppow1/R3/issues/65

---
## LL-003 — 2026-11-11 — Capture command results explicitly before asking the Steward to paste them

**Category:** Operator ergonomics; missing output capture; avoidable back-and-forth.

### Mistake
During B-2 recovery, ChatGPT supplied a multi-line PowerShell repair script and asked the Steward to show the result, but the script printed its result only to the terminal. It did not collect the result in a variable and place it on the clipboard. The Steward consequently pasted the **exact command** back into ChatGPT instead of the **execution output**. ChatGPT then had to ask again whether the script had succeeded. The failure was in the handoff design, not in the Steward's response.

### Evidence already available
- The Steward works clipboard-first with copy/paste PowerShell commands and frequently returns results to this conversation.
- Earlier B-2 inspection instructions had already demonstrated using `Set-Clipboard` to return diagnostic output.
- The repair script ended in multiple `Write-Host` statements (`B-2 REPAIR INSTALLED`, backup path, syntax errors, etc.), but had **no explicit result variable, output capture, or final `Set-Clipboard`**.
- The Steward posted the command itself; the actual terminal result was supplied only in a subsequent message.

### Impact
An unnecessary extra turn, confusion about whether the command ran, and additional operator work in the middle of a live bridge recovery.

### Correct minimal approach
For an **interactive one-shot PowerShell command whose output the Steward must paste back**, capture a concise, purpose-built result and explicitly copy it to the clipboard **at the end of the command**, for example:

```powershell
$Result = @(
    'B2_REPAIR=SUCCESS'
    "BACKUP=$Backup"
    "PARSE_ERRORS=$($Errors.Count)"
    'BRIDGE_RESTARTED=NO'
) -join [Environment]::NewLine
Write-Host $Result
Set-Clipboard -Value $Result
Write-Host 'Result copied to clipboard; paste into ChatGPT.'
```

For commands that may throw, design the reporting path to capture failure information too, without hiding or falsely reporting errors. Prefer a small explicit status block rather than indiscriminately copying huge source listings or sensitive data.

**Crucial distinction:** This lesson applies to **one-shot operator commands requesting returned output**. It does **not** reverse the Steward's separate requirement to disable **automatic clipboard copying on every B-2 polling cycle**. Background bridge processes must not overwrite the user's clipboard.

### Mandatory prevention check
Before sending any copy/paste command, ask: **Will I need the execution result back in this conversation?** If yes, the command must produce a clear result variable and a deliberate final clipboard copy, and say explicitly what the Steward should paste. Do not make the Steward manually select terminal output or infer success from a command echo.

### Verification and status
- Observed incident: B-2 repair command reposted verbatim, followed by actual output `B-2 REPAIR INSTALLED`, `Syntax errors: 0`.
- Recovery verified by subsequent screenshot and GitHub receipts for Steps 19 and 20: https://github.com/ppow1/R3/issues/61#issuecomment-6799995606
- **Behavioral correction is not yet verified**; test on the next one-shot PowerShell command that requests output.

**Related:** LL-001, LL-002.

---

## LL-004 — 2026-11-11 — Multi-Target dispatch must match the target's executable contract

**Category:** Repeat of known dispatch-format failure; confusing target selection with payload execution.

### Mistake
ChatGPT posted Step 24 to Issue #61 with `TARGET: Administrator Coordinator` and `DELIVERY: STEER`, but supplied only prose instructions. The running B-2 Multi-Target bridge found the planned step and correctly rejected it: `ERROR: Rejected malformed dispatch 6800865400 (missing fenced powershell command)`. ChatGPT had already seen this exact validation behavior in Step 18 and the subsequent fail-closed repair. The bridge was not broken; the assignment was malformed.

### Known evidence ignored
- The Multi-Target JSON maps logical target names to exact existing Windows titles; it does not convert arbitrary prose into executable PowerShell.
- Administrator Coordinator is a PowerShell terminal. Its dispatch requires a fenced `powershell` code block containing the actual executable command.
- HR Development and other Codex terminals can receive natural-language instructions, but that does not establish that a PowerShell target accepts prose-only instructions.
- Step 18 repeatedly failed on missing fenced PowerShell until the bridge was corrected to reject malformed steps once and continue.
- The bridge is polling GitHub Issue #61, and an accepted step requires the proper planned-step header, exact configured target, delivery marker, and target-appropriate payload.
- `FOUND`, `WAKE-UP SUBMITTED`, GitHub receipt, and target task completion are distinct evidence levels; none should be conflated.

### Impact
The Steward had to report another screenshot and wait for a corrected dispatch. Step 24 performed no Windows inventory, despite the bridge working as designed.

### Correct minimal approach
Before posting any planned step, determine the **actual target execution contract**, not just its display name. For `Administrator Coordinator`, provide the expected ```powershell fenced block, including an executable, read-only command when the task is inspection. For Codex targets, use instructions suited to the Codex session and verify delivery separately. Check the installed bridge's parser/contract if uncertain; never assume all targets consume the same payload format.

For the window inventory, Step 25 was posted with the required PowerShell block: https://github.com/ppow1/R3/issues/61#issuecomment-6800893787 . **Posting the correction does not prove execution; wait for a target result.**

### Mandatory dispatch preflight
1. Confirm `PLANNED STEP <number>`, `TARGET: <configured logical name>`, and `DELIVERY: STEER` exactly match the installed bridge contract.
2. Confirm the logical target maps to the exact, currently open terminal window title in `Riverview-B2-targets.json`; adding a new window requires a config edit and any necessary reload, not a new bridge.
3. Identify whether the target is **PowerShell command execution** or **Codex natural-language instruction**. For Administrator Coordinator, include an actual fenced `powershell` block.
4. Check the command is safe, scoped, and minimally invasive. For read-only tasks, avoid window movement, focus changes, service changes, and clipboard overwrite.
5. Check for duplicate/rejected prior steps; use a fresh step number rather than reusing a rejected ID. Verify bridge found/submitted/receipt and separately verify actual completion.
6. Do not change the bridge to compensate for a malformed dispatch. Fix the assignment payload first.

### Verification and status
- Rejection screenshot: Step 24, comment `6800865400`, missing fenced PowerShell.
- Corrected dispatch: Step 25, comment `6800893787`.
- **Step 25 completion remains unverified in this entry.** The lesson's behavioral compliance must be checked on subsequent dispatches.

**Related:** LL-001, LL-002, LL-003.

---
