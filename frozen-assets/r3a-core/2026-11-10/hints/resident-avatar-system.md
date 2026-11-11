<!--
R3 CONTROLLED DOCUMENT
File: hints/resident-avatar-system.md
Component: R3-RESIDENT-AVATAR
File Revision: 1.0.1
Created: 2026-11-02T20:11:07.271Z
Created By: ChatGPT GPT-6
Purpose: Record the reusable website avatar component, replaceable asset adapter, API seam, provenance, and remaining resident integration.
Execution Model: Browser-side Three.js module loaded lazily by the R3 estate page.
Observability: UI load/error state, model identity/license, configured and loaded animation clips, and active clip.
Dependencies: R3 FastAPI website service; pinned Three.js 0.180.0 CDN modules; models.codelove.in Businesswoman 04 model and female Biped animation GLBs over HTTPS.
Authority: Steward's Resident Avatar System brief; R3 Charter Revision 2; temporary appearance only.
Changed: 2026-11-02 UTC | R3-AVATAR-003 | ChatGPT GPT-6 | Replace the mismatched Gobkit placeholder with a human-looking rigged businesswoman and separate female Biped clip adapter.
Supersedes: None; updates revision 1.0.0 in place.
Contracts: docs/IMPLEMENTATION_HANDOFF.md; hints/file-provenance.md
Tests: Not run; deployed WebGL rendering, external clip playback, and Steward visual acceptance are pending.
History/Predecessor: Revision 1.0.0, blob 89350f2550fd553551072cbdf99c220b57fd71f6.
-->
# R3 resident avatar system

## Objective and current scope

Grace's identity, reasoning, memory, permissions, and conversations remain in R3. The website component is a replaceable presentation client. It does not put resident intelligence or ongoing operation inside the character model.

The estate navigation opens a lazy Three.js avatar panel. The previous Gobkit Office Lady asset rendered as an unintended blocky, toy-like character and has been replaced in this branch with CodeLove's Businesswoman 04: an adult female business character with a textured business suit. The source classifies this model as low-poly, 8,270 triangles, and provides an 80-bone Biped skeleton. It is a temporary visual candidate, not Grace's definitive appearance. The Steward still decides whether its appearance is acceptable.

The model page's downloadable model-only GLB is separate from the 10 MIT-licensed motion clips. The current adapter configures the female Biped clip set and loads clips individually when requested, using the published matching skeleton convention and Meshopt decoder. This keeps initial loading bounded to the character plus idle clip, instead of fetching every motion at panel open. The compact controls expose Idle, Talk, Wave, Walk, and Run; the browser API can request any configured clip, including Look around, Thoughtful, Cheer, Clap, and Dance.

## Reusable browser command surface

The module exposes the resident registry as `window.r3Residents`. A website client can read avatar status and submit a named animation command:

```js
const grace = window.r3Residents.get('Grace');
grace.avatar.status();
await window.r3Residents.command({
  type: 'play-animation',
  residentId: 'Grace',
  animation: 'Talk'
});
```

The browser API returns configured clip names, loaded clip names, and the active clip. Loop and crossfade settings remain command parameters. Animation playback is a presentation command only; it does not represent a resident emotional state, conversation, voice, or backend authorization.

This is not an authorization boundary. Page scripts and developer tools can call the API. Grace's server-side runtime and other clients do not yet have a transport to this browser API. Do not wire it to the resident backend until the shared authenticated Resident Interaction API and browser-session routing are reconciled with R3 runtime identity, permissions, audit, and continuation contracts.

## Asset, licensing, and renderer

- Model: [Businesswoman 04 GLB](https://models.codelove.in/models/business-female-04/), currently referenced at `https://models.codelove.in/models/business-female-04.glb`.
- Animation set: female skeleton-only Biped clips under [the animation library](https://models.codelove.in/animations/). Clip names and URLs are a fixed module manifest; the animation adapter loads only requested clips.
- License: MIT, according to the asset and animation source pages. The source says to retain the included license file when shipping or sharing the assets. The website references the host's assets and does not vendor the binary files in this change. Preserve license notices if the binary asset workflow later vendors them.
- Three.js 0.180.0 and MeshoptDecoder are loaded through the existing pinned jsDelivr import map. The model host documents CORS access and `EXT_meshopt_compression` / `EXT_texture_webp`. Rendering therefore still depends on browser access to both external origins and compatible browser decoders.
- The model page describes the character as low-poly and shows a fallback image when WebGL is unavailable. That listing view does not establish the deployed R3 render or animation behavior.

The model page offers no evidence of facial morph targets or lip-sync. Those capabilities remain unverified and are not exposed.

## Status and acceptance evidence

This change updates the persistent avatar component and its asset documentation. It preserves the resident registry and named-command API while adapting model and animation loading to a separate model/clip set.

Not yet verified: deployed R3 WebGL rendering; cross-origin model and clip fetch from the R3 browser; idle, talk, wave, walk, and run playback on the deployed renderer; per-device performance; and whether the Steward accepts this temporary character's appearance. The public model listing confirms the file format, rig, clip set, source license, and intended matching skeleton convention, but the R3 browser preview did not have WebGL available for direct inspection. Do not describe the model as live or accepted until those checks are complete.

No standalone or disposable demo has been added. This change extends the component already used by the website.

## Next engineering step

Review this focused branch, then deploy it through the established R3 queue. Verify the existing R3 panel in the browser with the model and one or more actual clips. Record the deployed commit and visual result. After that, continue designing the authenticated bidirectional Resident Interaction API against the existing resident runtime. Browser closure must not terminate Grace's autonomous operation or ongoing conversations. Website, desktop, and Quest clients should share that interaction contract and resident state while keeping their rendering adapters independent.
