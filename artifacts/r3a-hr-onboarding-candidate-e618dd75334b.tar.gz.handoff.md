# Coordinator handoff — R3A HR onboarding source candidate

- Package: `r3a-hr-onboarding-candidate-e618dd75334b.tar.gz`
- SHA-256: `47de58e08c453749a9e68a558c365f31beafa5b1c603fa0e578728e5b1938ea6`
- Source revision: `e618dd75334b3b7d5ed8216a4d2ca5867d83c2c0`
- Coordinator baseline: `2cc3fe3aabad88c95a5e6489c633cb01472f7c7f`
- Manifest: `r3a-hr-onboarding-candidate-e618dd75334b.tar.gz.manifest.json`
- Readiness: **SOURCE CANDIDATE — NOT DEPLOYABLE / NOT APPROVED FOR SHARED MIGRATION**

## Configuration and install prerequisites

See the package manifest for the complete file-level digest list and configuration contract. Before installation, Auditor must PASS this exact source and package. Coordinator must approve service composition, the migration/DB role grants, the controlled release window, and its application rollback procedure. Host composition requires authenticated actor and authorization providers, authoritative domain/activation verifiers, and the Coordinator packet repository. Security, HR, character, runtime, and communications remain separate authorities.

The verified HR host lacks `associate_authority_principal_with_provenance`; the accountable HR writer owner is not identified. The directory capability is read-only and no authorized resident/office-binding writer or named owner is identified. No production service API is composed in this source candidate. Consequently this bundle is an immutable integration handoff, not an installable/activated service.

## Install/rollback contract

After all gates, Coordinator applies migration 019 only through its checksummed `Store.migrate()` release path and deploys the reviewed host composition. Application rollback preserves packet/event tables. The 019 down migration is restricted to an approved procedure when both tables are empty and deliberately refuses populated evidence. Never use the disposable-test schema reset on shared R3A.

## Verification

The archive was rebuilt from a clean committed tree, its SHA-256 recorded, and every in-band file hash verified after writing. Focused tests and isolated PostgreSQL evidence are enumerated in `PACKAGE-MANIFEST.json`.
