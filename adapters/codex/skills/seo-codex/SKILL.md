---
name: seo-codex
description: Route staged Codex SEO requests to source-based page reviews, sampled audits of up to five explicit pages, optional GEO, visual, sitemap or saved Lighthouse analysis, content briefs, strategy plans, saved-capture comparisons, and prepared-runtime diagnosis. Use when the workflow is unclear or the user names this adapter.
---

# Codex SEO router

This adapter supports technical, structured-data, content, image-markup, local
and hreflang evidence from explicit pages. It does not register a `/seo` slash
command or replace installed SEO skills. Use staged resources only; never fall
back to a global `seo-*` skill.

Resolve resources from the staged project root. Use the caller's prepared
Python and explicit absolute, dedicated state root. Do not infer either from
global configuration. Run the route helper through the isolated runtime:

```text
<prepared-python> -I -B scripts/runtime.py --host codex --state-root <absolute-state-root> run codex_audit.py route <workflow>
```

Read its structured result before proceeding. Routing does not itself capture
pages, spawn agents, diagnose the runtime or grant permission for those actions.

| Requested workflow | Supported destination |
| --- | --- |
| `page` | Read `../seo-codex-pilot/SKILL.md`; retain both native roles and its capture/check contract. |
| `technical` | The same page pilot, emphasizing the user's technical question in the role briefs and final response. |
| `schema` | The same page pilot, emphasizing the user's structured-data question. |
| `content` | Read `../seo-codex-content/SKILL.md`; qualitative source-HTML review of 1–5 explicit pages using only the content role. |
| `images` | Read `../seo-codex-images/SKILL.md`; image-markup review of 1–5 explicit pages using only the images role. |
| `local` | Read `../seo-codex-local/SKILL.md`; source-based business identity and location declarations using only the local role. |
| `hreflang` | Read `../seo-codex-hreflang/SKILL.md`; one-page language and alternate-URL declarations using only the hreflang role. |
| `geo` | When the optional stage is available, read `../seo-codex-geo/SKILL.md`; review saved answer passages, attribution and declared preview controls using the GEO role. |
| `audit` | Read `../seo-codex-audit/SKILL.md`; sampled audit of 1–5 explicit pages, selecting all six roles unless the user requests narrower coverage. |
| `visual` | When the optional stage is installed, read `../seo-codex-visual/SKILL.md`; separate offline viewport review of an existing verified pilot capture. It does not add a role to the sampled audit. |
| `sitemap` | When the optional stage is installed, read `../seo-codex-sitemap/SKILL.md`; standalone review of supplied XML and up to five existing verified page captures. It does not add a role to the sampled audit. |
| `agentic` | When the optional stage is installed, read `../seo-codex-agentic/SKILL.md`; standalone interpretation of a supplied Lighthouse/PSI JSON report. It does not run Lighthouse or add a role to the sampled audit. |
| `content-brief` | When the optional stage is installed, read `../seo-codex-content-brief/SKILL.md`; standalone new/improve page planning from supplied requirements and up to five existing verified captures. It does not add a role to the sampled audit. |
| `plan` | When the optional stage is installed, read `../seo-codex-plan/SKILL.md`; a strategy, roadmap, calendar, site structure and measurement plan using supplied resources and up to five captures. |
| `drift` | When the optional stage is installed, read `../seo-codex-drift/SKILL.md`; compare two existing captures of the same recorded requested URL and interpret observed changes. No live monitoring or history database is included. |
| `doctor` | Run the prepared runtime's `doctor --json` with the same `--host codex` and explicit `--state-root`. |

Use `page` for one-page requests and `audit` for an explicit page sample or
resuming a sampled audit. A broad site-audit request still needs a bounded
sample: explain the available coverage and obtain the page list rather than
silently claiming a full-site audit. Ask only for missing target, workflow or
runtime inputs; do not make the user repeat an already supplied choice.

For `technical` and `schema`, keep both existing roles and validations. A
focused question changes the emphasis, not the evidence contract. Page-pilot
invocations must also use the prepared Codex runtime to dispatch
`codex_pilot.py`; preserve the pilot's arguments and artifact checks.

## Unavailable routes

Pass other requested workflows to `route` and preserve its structured
unavailable result. Explain the stated limitation and offer only a supported
workflow that addresses the user's intent. Do not invoke a nearby capability
without telling the user how its coverage differs.

This includes unported `programmatic`, `competitor-pages`, `maps`,
`google`, `backlinks`, `cluster`, `sxo`, `ecommerce`,
`flow`, provider extensions and `setup`. Missing implementation is not evidence
of missing credentials. Never inspect credentials, install dependencies,
enable providers, submit URLs, generate images or modify the target site to
make a route work.

If the route helper or required staged resource is absent, report that this
adapter is incomplete. Do not bypass the runtime allowlist or fetch a different
implementation. Report diagnostic failure without automatic setup or retries.

## Provenance

New Codex routing adapter based on the workflow distinctions in upstream
`skills/seo/SKILL.md`. Only the routes above are implemented here. Source
identities and file hashes are recorded by the staged manifest; preserve the
included MIT license. Host discovery and delegation require separate observed
verification, not a successful route response.
