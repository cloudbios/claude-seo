---
name: seo-codex-hreflang
description: Review declared hreflang in shared source captures of one to five explicit pages using the native Codex hreflang role. Use for bounded alternate-language annotation checks; excludes alternate fetching, translation review, full-graph validation and tag generation.
---

# Captured hreflang review

Review each explicit page separately using its existing shared capture. Read
[references/review.md](references/review.md) and pass that methodology to the
native `seo-codex-hreflang` role. Resolve staged resources from the project
root and use the caller's prepared Python and absolute dedicated state root.
Do not use global SEO skills, providers, install dependencies or follow
alternate targets.

Follow [../seo-codex-audit/SKILL.md](../seo-codex-audit/SKILL.md) for doctor,
input preparation, capture, native scheduling, resume and reporting. For a
new review, select only the hreflang role explicitly:

```text
<prepared-python> -I -B scripts/runtime.py --host codex --state-root <absolute-state-root> run codex_audit.py plan --urls <input-json> --output <new-audit-directory> --roles hreflang --max-workers 2
```

Accept 1–5 explicit URLs or supplied HTML paired with explicit base URLs.
Supplied HTML is fixture evidence, not an HTTP observation. A resumed audit
retains its recorded roles; do not re-plan it to change coverage. Use only
the native role with its claimed descriptor, exact capture hash and assigned
`findings/hreflang.json`; no generic or inline substitute. Each reviewer may
read only its own page, even when other sampled pages appear to be alternates.

Serialize ledger mutations and preserve the global cap of two workers.
Claim each task before spawning; require an early valid partial result.
Observe the native run's terminal result before releasing its claim, then
reconcile and report through the shared audit workflow. A findings file or
elapsed time alone does not establish termination. Preserve missing evidence
and incomplete work in the report.

This review covers source declarations, supported syntax examples, local
conflicts, self-reference and canonical hints. Missing hreflang is not itself
a defect without localization intent. Full alternate relationships and live
target behavior remain unverified. It creates local findings only; it does
not generate tags, edit the site or authorize external actions.

## Provenance

Adapted under the included MIT license from AgriciDaniel and contributors'
`skills/seo-hreflang/SKILL.md`. This adapter narrows the upstream workflow to
assigned source evidence and corrects blanket invalidation, casing, script,
region-code and implementation-method claims; cultural scoring, parity
ratios, discovery and generation do not apply.
