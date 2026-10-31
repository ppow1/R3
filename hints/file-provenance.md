<!--
R3 CONTROLLED DOCUMENT
File: hints/file-provenance.md
Component: ENG-FILE-PROVENANCE
File Revision: 1.0.0
Created: 2026-10-31 UTC (date only; exact time not independently verified)
Created By: ChatGPT GPT-6, acting on Steward instruction
Purpose: Preserve file-level authorship, origin, revision, supersession, and recovery provenance
Supersedes: None; adapts historical Riverview~ lifecycle guidance for R3
Changed: 2026-10-31 UTC | R3-PROVENANCE-001 | Initial R3 provenance convention
Authority: Steward instruction; R3 repository engineering guidance
History: Git commit history
-->
# R3 controlled-file provenance

Every new or modified R3 repository file must carry **file-level provenance**. This applies to source, scripts, tests, documentation, and configuration. Keep a concise header in the file's native comment syntax, after any required shebang/directive. Use a tracked **sidecar manifest** for binary files and formats where comments are invalid; never corrupt a binary or JSON file by inserting comments.

## Required header fields

- Repository-relative **File** path; **Component** identifier; **File Revision** (per-file semantic version, new controlled files normally `1.0.0`).
- **Created** timestamp in UTC with known precision; **Created By** (actual known actor/tool, not an assumed human author).
- **Purpose** and operational responsibility; **Execution Model** (or N/A); **Observability** (or N/A); important **Dependencies** and inputs/outputs.
- **Authority** / relevant constraints; **Changed** UTC timestamp, task identifier, actor, and summary.
- **Supersedes** (file, revision, and reason) or `None`; **Superseded By** when applicable. Distinguish replacing a document from simply editing it.
- **Contracts**, **Tests**, and **History/Predecessor** links, or `N/A` with explanation where appropriate.

## Updates and preservation

Before editing, inspect the current file and Git state. Record the existing revision and predecessor blob SHA/commit, preserve a retrievable predecessor, then increment the file revision for **every** content change, including header-only changes. A predecessor reference must be real, not invented. Git history is useful but ordinary mutable branch history alone is not guaranteed immutable backup retention; critical artifacts require an independently restorable backup. Record unknown historical creation timestamps or authors as `Unknown (legacy)` rather than manufacturing facts. Do not rewrite historical provenance as if the current editor created an older file.

For new files, capture the actual creation timestamp and actor when available. The commit records the publication timestamp separately. Use `Supersedes: None` unless the new document explicitly replaces another.

## Example Markdown header

```md
<!--
R3 CONTROLLED DOCUMENT
File: hints/example.md
Component: ENG-EXAMPLE
File Revision: 1.0.0
Created: YYYY-MM-DDTHH:MM:SSZ
Created By: actor/tool
Purpose: ...
Execution Model: N/A
Observability: N/A
Dependencies: ...
Authority: ...
Changed: YYYY-MM-DDTHH:MM:SSZ | TASK-ID | actor | summary
Supersedes: None
Contracts: ...
Tests: N/A
History: Git commit and revision manifest
-->
```

## Source and implementation

Historical reference: [Riverview~ Development Lifecycle Standard](https://github.com/ppow1/Riverview-/blob/main/docs/standards/DEVELOPMENT_LIFECYCLE_STANDARD.md) and [Engineering Records Standard](https://github.com/ppow1/Riverview-/blob/main/docs/standards/ENGINEERING_RECORDS_STANDARD.md). Their historical approval status is not automatically imported into R3. This R3 convention reflects the Steward's explicit direction.

**Compliance status:** R3 legacy files are not automatically compliant. Inventory, sidecar manifests for existing binary artwork, predecessor preservation, and CI/pre-commit validation remain pending until independently implemented and tested. Do not report compliance solely because this document exists.
