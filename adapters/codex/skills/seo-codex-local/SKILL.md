---
name: seo-codex-local
description: Review local business declarations and contextual name, address and phone consistency in captured source HTML for one to five explicit pages with the native Codex local role. Excludes live GBP, map rankings, citation verification and schema validation.
---

# Captured local business review

Review only the user's explicit page sample and its local business declarations.
Read [references/review.md](references/review.md) for the bounded methodology;
pass it to `seo-codex-local`. Resolve resources from the staged project root and
use the caller's prepared Python and absolute dedicated state root. Do not use
global SEO skills, renderers or provider fallbacks, or install dependencies.

Follow [../seo-codex-audit/SKILL.md](../seo-codex-audit/SKILL.md) for doctor,
input preparation, shared capture, native scheduling, resume and reporting.
For a new dedicated review, select only the local role explicitly:

```text
<prepared-python> -I -B scripts/runtime.py --host codex --state-root <absolute-state-root> run codex_audit.py plan --urls <input-json> --output <new-audit-directory> --roles local --max-workers 2
```

Accept 1–5 explicit URLs or supplied HTML paired with explicit base URLs.
Supplied HTML is fixture evidence, not an HTTP observation. Resolve missing
sample/runtime inputs before capture. Combined reviews must explicitly select
their requested roles. A resumed audit retains its recorded roles; never
re-plan it to change coverage. Use only the native `seo-codex-local` role, its
claimed task descriptor, exact capture hash and assigned `findings/local.json`;
no inline or generic-worker substitute.

Serialize ledger mutations and retain the audit's global cap of two workers.
Claim each task with `start` before native spawn. Release its claim only after
the native run is observed in an actual terminal state; a findings file does
not prove it stopped. Require an early valid partial JSON result and the
completed result when possible. Preserve incomplete work and evidence limits
in the final report.

Report contextual NAP comparisons, declared areas/hours/contact routes and
location/map/directory references with source evidence. Source HTML does not
prove rendered visibility, business operations, GBP ownership, map rank,
review health or verified citations. Address absence alone is not a defect;
service-area businesses may withhold their address. Leave full structured-data
validation to the schema role. Do not score local SEO, invent ranking weights
or impose review cadence or location-count gates.

This review creates local findings and recommendations. It does not follow
links, verify listings, fetch reviews, mutate the site or grant external actions.

## Provenance

Adapted from upstream `skills/seo-local/SKILL.md` and `agents/seo-local.md` by
AgriciDaniel and contributors under the included MIT license. Only bounded
source review is implemented; upstream scoring, live listing/citation checks,
rendering, provider workflows and unsupported thresholds do not apply.
