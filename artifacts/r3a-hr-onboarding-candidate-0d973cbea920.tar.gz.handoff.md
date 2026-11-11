# Coordinator handoff — R3A HR onboarding source candidate

- Package: `r3a-hr-onboarding-candidate-0d973cbea920.tar.gz`
- SHA-256: `418190d96090eb8c5b71084145fda6f5b62c47875ef6e2b98b1792e96d41a6ed`
- Source revision: `0d973cbea920ff0518f696b7de0baf4e41867359`
- Coordinator baseline: `2cc3fe3aabad88c95a5e6489c633cb01472f7c7f`
- Manifest: `r3a-hr-onboarding-candidate-0d973cbea920.tar.gz.manifest.json`
- Readiness: **SOURCE CANDIDATE — NOT DEPLOYABLE / NOT APPROVED FOR SHARED MIGRATION**

## Configuration and install prerequisites

See the package manifest for the complete file-level digest list and configuration contract. Before installation, Auditor must PASS this exact source and package. Coordinator must approve service composition, the migration/DB role grants, the controlled release window, and its application rollback procedure. Host composition requires authenticated actor and authorization providers, authoritative domain/activation verifiers, and the Coordinator packet repository. Security, HR, character, runtime, and communications remain separate authorities.

The verified HR host lacks `associate_authority_principal_with_provenance`; the accountable HR writer owner is not identified. The directory capability is read-only and no authorized resident/office-binding writer or named owner is identified. The bundle contains an installable R3A runtime library and versioned `r3a.resident.onboarding.host-composition.v1` façade, but no production route is registered or deployed. Consequently this bundle remains a source/integration handoff, not an activated production service.

## Install/rollback contract

After all gates, Coordinator applies migration 019 only through its checksummed `Store.migrate()` release path and deploys the reviewed host composition. Application rollback preserves packet/event tables. The 019 down migration is restricted to an approved procedure when both tables are empty and deliberately refuses populated evidence. Never use the disposable-test schema reset on shared R3A.

## Verification

The archive was rebuilt from a clean committed tree, its SHA-256 recorded, and every in-band file hash verified after writing. Focused tests and isolated PostgreSQL evidence are enumerated in `PACKAGE-MANIFEST.json`.
