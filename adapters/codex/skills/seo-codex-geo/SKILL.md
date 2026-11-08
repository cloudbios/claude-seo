---
name: seo-codex-geo
description: Review saved source HTML for self-contained answers, attribution, entity clarity and declared snippet controls on one to five explicit pages using the native Codex GEO role. Excludes live crawler access, AI visibility research and factual verification.
---

# Captured GEO review

Review the user's explicit page sample and stated reader question. Read
[references/review.md](references/review.md) and pass that methodology to
`seo-codex-geo`. Resolve resources from the staged project root and use the
caller's prepared Python and absolute dedicated state root.

Follow [../seo-codex-audit/SKILL.md](../seo-codex-audit/SKILL.md) for doctor,
input preparation, shared capture, native scheduling, resume and reporting.
For a new dedicated review, explicitly select GEO with the existing helper.

```text
<prepared-python> -I -B scripts/runtime.py --host codex --state-root <absolute-state-root> run codex_audit.py plan --urls <input-json> --output <new-audit-directory> --roles geo --max-workers 2
```

Accept 1–5 explicit URLs or supplied HTML paired with explicit base URLs.
Fixtures are supplied evidence, never HTTP observations. Resolve missing
sample/runtime inputs before capture. Combined reviews must explicitly select
their requested roles. A resumed audit retains its recorded roles. Reuse its
directory rather than re-planning to change coverage.

Use `capture`, `next`, `start`, `reconcile`, `release` and `report` from the
audit lifecycle. Serialize ledger mutations and retain the global cap of two
workers. Claim each task with `start` before spawning the exact native
`seo-codex-geo` role with its descriptor, assigned result path and capture
hash. Require an early valid partial result and one Update File/direct
overwrite for completion, without delete-and-add. Observe the actual native
terminal state before releasing a claim. A findings file alone never proves
the run stopped. Retain incomplete work and capture failures in the report.

Keep recommendations tied to saved-source evidence. Preserve metadata scope
and conflicts without declaring an effective crawler policy. No successful
page review may be inferred from an error-response body. Ask the coordinator
to consolidate duplicate content/GEO recommendations while preserving each
role's native artifact.

This workflow produces local `findings/geo.json` and audit recommendations.
Its scope excludes rendering, factual verification, live platform visibility,
brand-mention research, robots.txt/llms.txt retrieval, scores, citation
guarantees and numeric passage-length or recency quotas. Use no provider,
credential, site-edit or global SEO fallback.

## Provenance

Adapted from upstream `skills/seo-geo/SKILL.md` and `agents/seo-geo.md` by
AgriciDaniel and contributors under the included MIT license notice. The
adapter selectively retains passage clarity, attribution, entity and
source-metadata review. Upstream statistics, scoring weights, quotas and
external research workflows are excluded.
