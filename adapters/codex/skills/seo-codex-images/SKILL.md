---
name: seo-codex-images
description: Review on-page image markup in captured source HTML for one to five explicit pages with the native Codex images role. Use for alt text and delivery markup; excludes image-file analysis, rendering, generation and conversion.
---

# Captured image-markup review

Review only image markup in the user's explicit page sample. Read
[references/review.md](references/review.md) for the bounded methodology; pass
that methodology to `seo-codex-images`. Resolve resources from the staged
project root and use the caller's prepared Python and absolute dedicated state
root. Do not use global SEO skills or renderer/provider fallbacks. Do not
install parser dependencies; the bundled parser may inspect the saved HTML.

Follow [../seo-codex-audit/SKILL.md](../seo-codex-audit/SKILL.md) for doctor,
input preparation, capture, native scheduling, resume and report procedures.
For a new review, select only the images role explicitly:

```text
<prepared-python> -I -B scripts/runtime.py --host codex --state-root <absolute-state-root> run codex_audit.py plan --urls <input-json> --output <new-audit-directory> --roles images --max-workers 2
```

Accept 1–5 explicit URLs or supplied HTML paired with explicit base URLs.
Supplied HTML is fixture evidence, not an HTTP observation. Resolve missing
sample or runtime inputs before capture. Use only `seo-codex-images` and its
descriptor, exact capture hash and assigned `findings/images.json`; no inline
or generic-worker substitute. A resumed audit retains its recorded roles;
never re-plan it to change coverage.

Serialize ledger mutations and retain the global cap of two workers. Release
each claim only after its native run is observed to have stopped. Require an
early valid partial JSON result and the completed result when possible.
Preserve incomplete work and capture limitations in the final report.

Report missing versus empty alt, contextual wording and declared loading,
responsive and sizing markup. Do not assert visual accuracy, intrinsic size,
actual format or bytes, above-fold placement, LCP, CLS or compression savings.
This review produces local findings and recommendations; it does not fetch,
generate, convert or mutate image assets or the target site.

## Provenance

Adapted from upstream `skills/seo-images/SKILL.md` by AgriciDaniel and
contributors under the included MIT license. Only on-page markup review is
implemented; upstream file optimization, rendering and provider paths do not
apply.
