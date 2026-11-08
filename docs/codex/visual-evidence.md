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
review reference. With the local/hreflang batch, it stages 33 copied files.
Without this flag, the core stage has 28 files and six roles, and the original
pilot retains eight files. The acceptance receipt below tested the earlier
27-file visual stage.
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
success, including handled SIGTERM cancellation. No persistent browser profile,
account session, ambient raw HTTP
fetch or provider/auth helper is used.

`doctor` exits nonzero when prerequisites are unavailable. Capture exits
nonzero when rendering is incomplete, and finalization exits nonzero for a
partial review; accepted partial evidence remains on disk. `validate` can
succeed for an internally valid partial bundle and reports its actual state.

## Provenance and validation

The visual instructions adapt upstream `agents/seo-visual.md`; the rendering
seam reuses the existing renderer and guarded browser context.
[Playwright request routing](https://playwright.dev/python/docs/network) and
[BrowserContext routing](https://playwright.dev/python/docs/api/class-browsercontext)
were cross-checked through Context7. Runtime-specific acceptance is recorded
separately below; documentation alone does not prove the installed browser works.

The implementation at `cf3ab6d1ef2e993d49a5f8a3543c88b697011958` passed
509 selected tests, with the existing live-network renderer test deselected.
Ruff and the visual skill validator passed. Independent source review covered
isolated execution, cancellation, source/artifact validation, charset/browser
provenance and optional staging.

Real-browser acceptance used prepared Python 3.12.14, Playwright 1.63.0 and
Chromium headless shell 153.0.8010.12 on macOS. The first sandboxed launch was
blocked by macOS Mach-port permissions and correctly saved partial evidence;
the same offline render succeeded after a normal host permission escalation.
Both viewport PNGs were inspected. Inline JavaScript text and UTF-8 characters
rendered, external image/API attempts were rejected by CSP, and the mobile
fixture's fixed-width panel produced recorded 740px document width against a
390px viewport. Desktop document width was 1280px against a 1280px viewport.

A separate infinite-loop fixture hit the four-second process timeout, returned
exit code 1 with two partial viewports, and left zero live members of its
observed worker process group (six descendants observed; 4.41 seconds total).
The original fixture capture was preserved. These checks establish this
prepared environment's behavior, not compatibility with every browser or OS.

Native acceptance used Codex CLI `0.154.0-alpha.6.2` with the per-run native
role registration and `gpt-5.6-sol`, high reasoning, supported by that installed
CLI. The role files continue to inherit the caller's model and permissions;
these test overrides do not change them. This is a CLI acceptance receipt,
not an additional fresh desktop-discovery test.

The staged `visual` route returned available. One fresh-context native
`seo-codex-visual` task (`/root/harbor_visual_review`) saved an early partial
result, reached an observed completed state, and then passed finalization and
validation. Its terminal result reported `view_image` inspection of both PNGs;
the coordinator could not observe the child's underlying tool-call stream.
An independent reviewer actually opened both PNGs and accepted all six
findings and the final report, with no required fixes. Heading/CTA visibility,
mobile text cutoff and measured overflow were supported; blocked images and
the injected HTML instruction were handled as evidence, not commands.

The 27 staged source files were compared byte-for-byte with the implementation
commit. Acceptance artifacts live under
`/private/tmp/seo-codex-visual-test/output/` on the test host:

- `NATIVE-RECEIPT.json`: observed native workflow and visibility limits.
- `BROWSER-ACCEPTANCE.json`: source/stage/artifact verification.
- `VISUAL-ACCEPTANCE.json`: independent pixel/findings/report review.
- `TIMEOUT-ACCEPTANCE.json`: real browser timeout and process cleanup.
- `native-visual/REPORT.md`: complete bounded visual report.

Exact identities:

| Evidence | SHA-256 |
|---|---|
| Stage manifest | `182e7e693811ae8ac7335593534a4b7b478a2ae61aabc5e467143a7cb4eca9bd` |
| Original fixture HTML (2,138 bytes) | `8b6745c4196c960eb7cbfe277f299189af0fa02c8e04f2dc2fd71ac5b6dc3409` |
| Original pilot manifest | `1c70266663ddd1b546a3418133aec4d31188e9ee550d6656a746289d3b98bb35` |
| Render evidence identity | `46e87758154329f06a6c26b9850368a636d03df1961848de3a1a27e2dfdadf6c` |
| Final report | `87e3445a38d0db9dd1e380415de0680df72447ea30b09b917f2170f5e0ba48c4` |

The source capture and its manifest remained unchanged. No global SEO
installation, dependency installation, provider enablement or live-page fetch
was performed in this acceptance run. Performance, live rendering and provider
adapters remain separate future batches.
