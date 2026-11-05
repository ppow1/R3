<!--
R3 CONTROLLED DOCUMENT
File: hints/chatgpt-image-publishing.md
Component: ENG-IMAGE-PUBLISHING
File Revision: 1.0.0
Created: 2026-11-01 UTC (date verified; exact time not independently verified)
Created By: ChatGPT GPT-6, acting on Steward instruction
Purpose: Standard operating procedure for publishing ChatGPT-generated images to R3 using the Windows A: drive and Q2 watcher
Execution Model: User downloads image; Riverview Comms submits PowerShell to Q2; watcher executes; GitHub upload from A:
Observability: Q2 result files, source/destination hashes, GitHub commit and Git blob verification
Dependencies: AI_HINTS.md; hints/q2-script-queue.md; hints/file-provenance.md; Windows desktop-ja3rpnq; authenticated GitHub CLI in Q2 watcher context
Authority: Steward-approved image publishing workflow; restrict writes to approved R3 repository and branch
Changed: 2026-11-01 UTC | R3-IMAGE-PUBLISH-001 | ChatGPT GPT-6 | Initial verified image publishing policy
Supersedes: None
Contracts: hints/file-provenance.md; hints/q2-script-queue.md
Tests: Verified 2026-11-01 using r3_survey_v3_original_corrected.png; Q2 copy SHA-256 matched; GitHub upload commit f0efbd094ce1d83f4e049c9e7ae7d5fa1914ca19; Git blob SHA matched local git hash-object
History/Predecessor: New document; Git history records publication
-->
# ChatGPT-generated image publishing — Download → A: → R3 GitHub

## Policy

For ChatGPT-generated artwork destined for Riverview R3, the **only routine manual action** required of the Steward is to click **Download** in ChatGPT, saving the image to the Windows Downloads directory. Once downloaded, the assistant performs the remainder through authorized Riverview Comms and the existing Q2 watcher. Do not ask the Steward to paste PowerShell commands, manually upload to GitHub, or copy the file to A: when the automated path works.

**Do not claim direct access to a ChatGPT-generated binary in the Windows filesystem until the Steward has downloaded it.** Confirm the downloaded filename before selecting a file, especially when Windows appends a suffix such as `(1)`. Never silently substitute a different image or retrieve a prior GitHub copy instead of the downloaded original.

## Verified execution boundaries

- Windows host: `desktop-ja3rpnq`; source typically `C:\Users\wille\Downloads\<actual-downloaded-name>.png`.
- Durable local image directory: `A:\AI\Riverview\Images\`.
- Q2 submission: `A:\AI\Scripts\Riverview\Q2\<unique-name>.ps1`.
- Watcher result: `A:\AI\Scripts\Riverview\Queue\Results\<unique-name>.ps1.txt`.
- Target repository: `ppow1/R3`; use the Steward-authorized branch and repository-relative artwork path, not a hard-coded assumption about future branches.
- Riverview Comms submits the script; **the Q2 watcher executes it in a separate Windows identity/context**. On 2026-11-01, the copy test reported `DESKTOP-JA3RPNQ\wille`. A direct Comms command's access denial or missing GitHub authentication does not establish the watcher's permissions.
- Q2 execution successfully uploaded the approved image through the authenticated `gh` CLI on 2026-11-01. Do not assume that direct Comms has the same authentication.

## Required agent procedure

1. Read `AI_HINTS.md`, `hints/file-provenance.md`, `hints/q2-script-queue.md`, and this runbook. Confirm the authorized repository, branch, destination path, and actual downloaded filename. Check for an existing identical remote file to avoid unnecessary duplicate commits.
2. Construct a uniquely named PowerShell script beginning with `Clear-Host` and `$ErrorActionPreference='Stop'`. Submit its **text** through authorized Riverview Comms into Q2. **Never manually move a script from Q2 to Queue.**
3. In the Q2 script, verify that the specific downloaded source file exists, create `A:\AI\Riverview\Images` if necessary, copy the image from Downloads to A:, and compare SHA-256 hashes. Stop and report an error if the source is missing, inaccessible, or the hashes differ. Never delete the downloaded original as part of publishing.
4. Read the matching Q2 result file. Missing or empty results are not success. Before retrying a possibly executed script, inspect the result and remote state to avoid duplicate side effects.
5. Upload the **verified A: file** using `gh api` in the Q2 watcher context, with the authorized repository/branch/path. For GitHub Contents API, use a base64-encoded file body; include the current remote content blob SHA for updates. If the remote file already has identical bytes, report `ALREADY_CURRENT` rather than creating a needless commit. Keep credentials out of script files and logs.
6. Verify the committed remote blob using Git's object hash: compare `git hash-object -- <A:-image-path>` with the GitHub blob SHA for the target branch/path. GitHub's Contents API may omit inline base64 content for large images; **an empty `content` field is not proof of a zero-byte upload**. Also record the local SHA-256, byte count, remote path, and commit SHA.
7. Report success only when Q2 execution and remote integrity are verified. Provide the exact GitHub file URL and commit SHA. If blocked or uncertain, preserve the error and follow `hints/comms-failure-recovery.md`.

## Verified acceptance example — 2026-11-01

- Source: `C:\Users\wille\Downloads\r3_survey_v3_original_corrected.png`.
- A: copy: `A:\AI\Riverview\Images\r3_survey_v3_original_corrected.png`.
- Size: `3,382,080` bytes.
- Source and destination SHA-256: `59F087BED0CE5405EF4BC9F52AEC0CFC5D62CD2477C664B70A6CE35AD4F9D7CE`; `MATCH=True`.
- Q2 upload commit: `f0efbd094ce1d83f4e049c9e7ae7d5fa1914ca19`.
- Local and GitHub Git blob SHA: `243ad8595819f2ad2053372ef7056636e9e33ff5`.
- Published image: [R3 numbered Estate survey](https://github.com/ppow1/R3/blob/engineering/institution-runtime-v1-20261101/assets/visual-concepts/r3_survey_v3_original_corrected.png).

## Provenance and restrictions

For newly published binary artwork, add a tracked sidecar manifest as required by `hints/file-provenance.md` documenting original generation, downloaded source filename, publishing actor, revision, checksum, and supersession. Do not inject text headers into PNG files. Preserve originals and predecessor revisions when replacing artwork.

This runbook is a documented, verified **R3** workflow, not permission to modify Riverview 2, alter watcher configuration, grant broad filesystem permissions, or expose GitHub credentials.
