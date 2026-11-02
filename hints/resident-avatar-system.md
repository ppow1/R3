<!--
R3 CONTROLLED DOCUMENT
File: hints/resident-avatar-system.md
Component: R3-RESIDENT-AVATAR
File Revision: 1.0.0
Created: 2026-11-02T20:11:07.271Z
Created By: ChatGPT GPT-6
Purpose: Record the initial reusable website avatar component, asset provenance, API seam, and remaining authorized resident integration.
Execution Model: Browser-side Three.js module loaded lazily by the R3 estate page.
Observability: UI load/error state, model identity/license, supported animation names, and active clip.
Dependencies: R3 FastAPI website service; pinned Three.js 0.180.0 CDN modules; Gobkit OfficeLady GLB over HTTPS.
Authority: Steward's Resident Avatar System brief; R3 Charter Revision 2; temporary appearance only.
Changed: 2026-11-02T20:11:07.271Z | R3-AVATAR-001 | ChatGPT GPT-6 | Define initial web avatar architecture and implementation boundary.
Supersedes: None
Contracts: docs/IMPLEMENTATION_HANDOFF.md; hints/engineering-test-policy.md; hints/file-provenance.md
Tests: Not run; visible browser loading and animation acceptance remain pending.
History/Predecessor: New document.
-->
# R3 resident avatar system — initial implementation

## Objective and current scope

The shared resident identity and reasoning stay in R3. This first implementation adds a replaceable website rendering component for Grace's temporary avatar. It does not place resident reasoning, memory, permissions, or conversations inside the character model.

The estate navigation gains a compact **Grace** entry. Opening it lazily creates the Three.js renderer and loads Gobkit's Office Lady GLB. The interface identifies the appearance as temporary and says that conversation and authorized resident control are not connected. No synthetic conversation, resident telemetry, voice, facial expression, or lip-sync is displayed.

## Reusable browser command surface

The module exposes the active resident registry to the page as window.r3Residents. A website client can read status and submit an animation command:

    const grace = window.r3Residents.get('Grace');
    grace.avatar.status();
    await window.r3Residents.command({
      type: 'play-animation',
      residentId: 'Grace',
      animation: 'Walk'
    });

The API validates that a resident exists and that the requested named clip was loaded from the GLB. It reports available clips from the asset at runtime; it does not invent or slice clip ranges. Animation commands support optional loop and fade settings. The command may also be initiated from the component's compact controls.

This is a **browser-client API**, not an authorization boundary. Page scripts and developer tools can call it. Grace's server-side runtime and other clients do not yet have a transport to this browser API. Do not wire it to the resident backend until the shared, authenticated Resident Interaction API and browser-session routing are designed against the current R3 runtime, identity, permissions, audit, and continuation contracts.

## Asset and renderer dependencies

- Temporary appearance: [Gobkit Free Character Pack Vol. 1](https://gobkit.itch.io/gobkit-free-character-pack-vol-1), model OfficeLady.glb, direct asset URL https://gobkit.com/freebies/human001/OfficeLady.glb.
- The creator's current manifest lists the model as rigged, with named Idle, Walk, Run, Death, Hit, Attack, and Special clips at 30 FPS, and CC0 1.0. The website uses the author-provided direct URL and exact clip names.
- Three.js 0.180.0 is pinned through jsDelivr import-map URLs. These external origins require browser network access. If either dependency fails, the component shows an unavailable state and preserves the rest of the estate page.
- The GLB is not yet vendored into R3. A later deployment-hardening step should preserve the exact CC0 source asset and checksum in R3 once the repository's binary asset workflow is available. Until then, rendering depends on the creator's host remaining reachable.

The creator's animation manifest does not establish facial morph targets or a lip-sync rig. Those capabilities remain unverified and are intentionally not exposed.

## Current status and acceptance evidence

Implemented in source: compact navigation entry; lazy avatar panel; replaceable GLB URL/configuration; named animation playback; browser API surface; bounded failure display; static-module serving route; provenance and license notes.

Not yet verified: page import on the deployed FastAPI version; WebGL rendering in the deployed browser; cross-origin model fetch; actual play transitions for each clip; per-device performance; Grace or another authorized resident issuing a command through a backend bridge. The implementation is source-only until review and deployment. No one-time or timing-sensitive test has been added.

## Next engineering step

After source review, verify the persistent feature in the deployed R3 website and record the actual commit and browser result. Then design the authenticated bidirectional Resident Interaction API around the existing resident runtime and tool authorization. That bridge must route commands only to an authorized active browser session, persist or explicitly report delivery state, preserve resident continuity when the page closes, and expose no unauthenticated operational command route. Desktop and Quest clients should consume that same interaction contract through client-specific presentation adapters.
