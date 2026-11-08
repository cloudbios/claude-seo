---
name: seo-codex-visual
description: Review an existing verified page capture using offline desktop and mobile screenshots of its saved HTML. Use for an explicitly requested visual supplement; separate from the sampled audit and excludes live-site rendering or full accessibility audits.
---

# Saved-HTML visual supplement

Use this optional staged workflow only for a requested visual review. It adds
separate visual artifacts to an existing verified raw pilot capture; it does
not add a role to the sampled audit, change its four-role plan, or replace raw
technical/schema evidence. Read [references/review.md](references/review.md)
and include that methodology in the native `seo-codex-visual` brief.

Resolve resources from the staged project root. Require the caller's prepared
Python, absolute dedicated state root, explicit absolute browser executable,
existing pilot capture directory and a new visual output directory. Do not
discover a browser, install dependencies, consult credentials, enable a
provider or use a globally installed SEO skill. Missing optional resources
mean this workflow is unavailable; do not substitute a nearby renderer.

## Capture and verify

Every visual command uses this prepared runtime prefix:

```text
<prepared-python> -I -B scripts/runtime.py --host codex --state-root <absolute-state-root> run codex_visual.py
```

1. Run `doctor --browser <absolute-browser-executable>` and inspect its result.
   A failed prerequisite check is a reported limitation, not permission to
   install or search for a browser. Capture requires the supported POSIX host.
2. Use an explicit existing pilot directory with its verified
   `pilot-manifest.json` and raw capture. If no capture exists, use
   [../seo-codex-pilot/SKILL.md](../seo-codex-pilot/SKILL.md) to obtain one within
   the user's authorized target; do not silently fetch a page for this stage.
   Retain whether the source was fetched HTML or a supplied fixture.
3. Run `capture --source <absolute-pilot-directory> --output <absolute-new-visual-directory> --browser <absolute-browser-executable> --timeout 20`.
   The output directory must be new and its parent must exist. The renderer
   verifies the source, renders saved HTML offline at desktop **1280×800** and
   mobile **390×844**, and saves viewport screenshots, DOM, diagnostics,
   geometry and a separate `visual-manifest.json`. All external requests,
   service workers and WebSockets are blocked. Inline HTML/CSS/JS may run;
   external scripts/styles/fonts/images are unavailable.
4. Inspect the capture result and `visual-manifest.json`, then run
   `validate --output <absolute-visual-directory>`. Verify the recorded source
   capture and pilot-manifest hashes and render artifact checks before review.
   A pre-review `captured` state is not a completed visual review. Missing or
   failed viewports remain partial; review only their accepted evidence. On
   capture, hash or validation failure preserve the output and report the
   failure; do not rewrite evidence or automatically recapture.

## One native review

Give the exact `seo-codex-visual` native role the absolute visual directory,
source pilot directory, exact source capture hash, `evidence_sha256`, the
user's question and the review reference. The profile inherits host model and
security settings. Run only one visual reviewer, within the host's observed
available slots. It writes only `findings/visual.json`, first a valid partial
result and then a completed result when possible. Do not substitute a generic
worker or represent an inline review as successful native-role discovery.

The reviewer must open the screenshots with an actual screenshot-view tool
before drawing visual conclusions. If that capability is missing, keep a
partial result with evidence-grounded DOM/metadata findings and state exactly
which screenshots were not inspected. A file listing is not visual inspection.
Read the reference for citations, scope and the result schema.

Observe the reviewer's terminal result before running
`finalize --output <absolute-visual-directory>`, then
`validate --output <absolute-visual-directory>`. Finalization is single-use;
do not edit findings or re-finalize after it records the result. A findings file or elapsed
time does not establish that a worker stopped. If resuming an existing visual
directory, validate it and establish whether the prior reviewer is stopped
before starting another; never overwrite evidence or duplicate a live review.

Report the separate visual output path, actual complete/partial status,
important evidence-linked findings, source identity and limitations. Describe
screenshots as **offline renders of saved HTML**, not live website renders.
Missing external assets can materially alter appearance; conclusions apply
only to these saved-HTML viewports. Preserve capture and review failures in the
final response. This workflow grants no site edits, live browsing, provider
calls or changes to the existing audit's completion state.

## Provenance

Adapted under the included MIT license from AgriciDaniel and contributors'
upstream `agents/seo-visual.md`. This bounded adaptation retains viewport
inspection and evidence persistence, with its own fixed viewports and offline
capture contract. Upstream installation commands, live rendering assumptions,
blanket font/touch thresholds and layout-performance claims do not apply.
