# Offline visual evidence

This opt-in adapter renders an existing verified page capture and gives one
native visual specialist the resulting desktop/mobile screenshots and DOM.
It preserves the raw capture and the existing sampled audit contracts.

## Scope

The browser receives the saved HTML at its declared page URL. The main
navigation is fulfilled from those bytes; other requests are blocked.
Inline HTML, CSS and JavaScript can affect the result, but external styles,
scripts, fonts and images are not loaded. This is an offline rendering of
saved evidence, not a new live-site observation.

The visual role can review the captured viewport's heading/CTA visibility,
overlap, clipping, readable layout and differences between desktop and mobile.
It must inspect the actual screenshots before making visual claims. DOM and
geometry alone cannot substitute for image inspection; missing image-view
capability leaves the review partial.

This workflow does not establish field Core Web Vitals, actual LCP/CLS,
image-file quality, complete accessibility conformance, live network behavior,
search-engine rendering or site-wide health. Blocked assets and unsettled
content remain limitations.

## Prepare and run

Use an existing prepared Python/Playwright installation and matching Chromium
executable. No dependency or browser installation is performed. The initial
worker-supervision implementation supports POSIX hosts; other platforms must
report unavailable rather than assume equivalent process cleanup.

```sh
/path/to/prepared/python scripts/stage_codex_pilot.py \
  --output /private/tmp/seo-visual-project \
  --register-agents --visual-evidence
```

`--visual-evidence` includes the core adapter plus five explicitly listed
files: the visual helper, upstream renderer module, native role, skill and
review reference. It stages 27 copied files. Without this flag, the core stage
retains its 22 files and four roles, and the original pilot retains eight files.
The `visual` route is available only when the optional staged resources exist.

Supply a successful existing `codex_pilot.py` capture directory, a new visual
output directory, the prepared browser executable and the usual dedicated
state root. The visual skill runs commands through this prefix:

```text
/path/to/prepared/python -I -B scripts/runtime.py --host codex --state-root ABSOLUTE_STATE run codex_visual.py
```

Run the visual helper's `doctor --browser ABSOLUTE_BROWSER` first, then use
`capture --source PILOT_DIRECTORY --output NEW_DIRECTORY --browser ABSOLUTE_BROWSER`.
Doctor checks prerequisites; a successful browser launch is separate evidence.
Use `validate --output DIRECTORY` to check the result. The native role writes
`findings/visual.json`; after it has stopped, the coordinator runs
`finalize --output DIRECTORY`.

Rendering uses fixed desktop 1280×800 and mobile 390×844 viewports at DPR 1.
Screenshots cover those viewports, not the full page. A bounded observation
cannot prove the document is permanently settled or that every state was tested.

## Integrity and process boundaries

The supplement has its own `visual-manifest.json`, linking both the original
HTML hash and source pilot-manifest hash. It records viewport/browser metadata,
DOM/PNG artifact hashes and a stable `evidence_sha256`. Native findings must
match both the raw `capture_sha256` and `render_sha256` identity.

The helper revalidates the source and output evidence before accepting or
finalizing findings. It refuses changed artifacts, symlinked paths, reused
output directories and repeated finalization. Partial rendering or missing
review results remain partial.

Each capture runs in a supervised child process. Fresh browser contexts block
service workers and WebSocket connections, while routing fulfills only the
saved main document and aborts other requests. A whole-worker timeout bounds
JavaScript stalls, and browser/process cleanup runs on failure as well as
success. No persistent browser profile, account session, ambient raw HTTP
fetch or provider/auth helper is used.

## Provenance and validation

The visual instructions adapt upstream `agents/seo-visual.md`; the rendering
seam reuses the existing renderer and guarded browser context.
[Playwright request routing](https://playwright.dev/python/docs/network) and
[BrowserContext routing](https://playwright.dev/python/docs/api/class-browsercontext)
were cross-checked through Context7. Runtime-specific acceptance is recorded
separately below; documentation alone does not prove the installed browser works.

Validation results and exact tested source identities will be recorded after
the automated, real-browser and native-role checks complete.
