# Full Codex port

The generated distribution provides 35 skills, 34 native `seo-full-*` profiles,
and supporting resources from all 9 extensions. It adapts the upstream Claude
SEO methodology, including all 19 original specialist definitions and the FLOW
prompt library. The source manifest records original and distributed hashes.
MIT licensing and contributor credits are retained. FLOW framework and prompts
retain Daniel Agrici's attribution and CC BY 4.0 notices.

Final combined validation and approval for this port are pending. Live provider
validation remains unverified. Use the installation guide for build, setup,
project trust, upgrades, and uninstall. [Installation guide](INSTALL.md)

## Coverage

Invoke `$seo-codex` to select a workflow or `$seo-codex-<route>` directly.

| Area | Routes |
|---|---|
| Site and page review | `audit`, `page`, `technical`, `content`, `schema`, `sitemap`, `images`, `performance`, `visual` |
| Content and strategy | `content-brief`, `plan`, `cluster`, `sxo`, `programmatic`, `competitor-pages`, `flow` |
| Search surfaces | `geo`, `agentic`, `local`, `maps`, `hreflang`, `ecommerce`, `drift` |
| Data and extensions | `google`, `backlinks`, `dataforseo`, `image-gen`, `firecrawl`, `ahrefs`, `bing`, `profound`, `seranking`, `matomo`, `unlighthouse` |

`adapters/codex/full/` contains generated native entrypoints, profiles, schema,
assets, extension trees, and provenance. Each native entrypoint links its full
adapted `methodology.md` and supporting references. The installed package also
keeps original skill resources under `source-skills/`, including templates
needed by helpers. Its `skills/` directory contains the discoverable native
entrypoints, which the project installer places under `.agents/skills/`.

The earlier `adapters/codex/skills/` pilot supports bounded saved-capture
workflows, including explicit 1–5 page review. The full distribution adds live
helper dispatch, provider-aware workflows, and the full-site coordinator. Its
profiles inherit the active session's model settings and permissions.

## Full-site audit

The coordinator exposes `plan`, `crawl`, `next`, `start`, `release`, `reconcile`,
and `report` through `run codex_full_audit.py`. A plan accepts `--max-pages`
from 1 through 500, defaults to 100, and accepts `--render auto|always|never`.
`--max-workers` accepts one or two. Optional `--roles` selects specialists.
The default set is technical, content, schema, sitemap, performance, visual,
GEO, and SXO.

The crawler follows same-origin links found in captured HTML. It records
sitemap declarations for specialist analysis. Pages accessible only through
sitemap XML, other origins, interaction, or undiscovered links can remain
outside the sample. The manifest records the page cap, remaining queue,
excluded URLs, transport results, and raw/rendered representations. Rendering
depends on browser availability and the selected mode.

The crawler applies `robots.txt` rules for `CodexSEO/1.0`. A 401 or 403 blocks
crawling. Other 4xx responses except 429 allow crawling. Unavailable, oversized, rate-limited,
server-error, or unresolved responses pause the crawl. A requested crawl delay
above 60 seconds also pauses it. These results belong in the final coverage
statement, together with the pages each specialist actually inspected.

Each worker writes `findings/ROLE.json` with exactly `role`, `site_sha256`,
`status`, `findings`, and `limitations`. Status is `partial`, `complete`, or
`unavailable`. Findings and limitations are arrays of strings. The coordinator
validates source identity and saved evidence references. Workers save partial
progress early. The coordinator observes a worker's stop before release and
explicitly resumes incomplete work when appropriate.

Reports include `FULL-AUDIT-REPORT.md`, `audit-data.json`, and versioned report
snapshots. Missing measurements stay unavailable. Raw HTML, rendered content,
lab diagnostics, field metrics, and account data keep separate evidence labels.

## Runtime and provider access

Use the installed launcher with an absolute `--state-root`. Its `config/`,
`cache/`, and `runtime/` directories contain provider configuration, caches,
and the prepared Python/browser environment. Setup is explicit. The runtime
accepts only allowlisted scripts and script-specific environment inputs.
Sensitive credential-file references must resolve inside its `config/` tree.

| Capability | Required access or configuration |
|---|---|
| HTML and schema analysis | Reachable target URLs and prepared Python dependencies. Rendering and screenshots additionally require the prepared browser. |
| Google APIs | `config/google-api.json`, an applicable API key or OAuth/service-account credentials, and access to the requested property. OAuth and service-account files belong under `config/`. |
| Backlinks and Bing | `config/backlinks-api.json` or supported Moz/Bing environment inputs. Bing comparisons require properties registered to that account. Common Crawl supplies its own public evidence. |
| Matomo | `config/matomo.json` or supported Matomo URL, token, and site-ID inputs. |
| DataForSEO | A matching connector or explicit username/password configuration for supported helpers. Calls can consume paid credits. |
| Image generation | A configured generation connector or the Banana helpers with an explicit Google AI key. Generation has authorization and cost gates. |
| Ahrefs and Firecrawl | An available authenticated connector with the requested capability. Discover its actual tool schema at runtime. |
| Profound and SE Ranking | An available authenticated connector or a currently verified official API contract. Upstream resources supply workflow recipes. Live collection depends on an executable provider capability. |
| Unlighthouse | Available Node and a prepared npm cache. Explicit `run --allow-install` authorizes the pinned package download; ordinary runs are offline and disable install hooks. |

Provider names and example tool names are discovery hints. Verify the actual
connector schema, account access, costs, and returned fields. Report missing
capabilities and continue with supported evidence. Credential migration and
paid calls require applicable user authorization. Use
`run --allow-write SCRIPT.py ...` for an authorized operation that needs the
runtime's mutation permission. [Runtime implementation](../../scripts/codex_runtime.py)

## Validation and review

Regenerate after changing upstream skill, agent, extension, or shared resource
files, then verify the generated hashes.

```bash
python3 scripts/build_codex_skills.py
python3 scripts/build_codex_skills.py --check
```

The final combined check should cover the repository test suite, native profile
parsing, complete route/resource coverage, package provenance, isolated
install/upgrade/uninstall, explicit-state runtime dispatch, fixture-based full
audits, and target-client skill/agent discovery. Dependency setup and any live
provider calls need their own applicable authorization. Fixture results establish
local behavior. Provider and target-client results require observed runs.

The relevant regression coverage lives in `tests/test_codex_full_skills.py`,
`tests/test_codex_full_runtime.py`, `tests/test_codex_provider_paths.py`,
`tests/test_codex_package.py`, and `tests/test_codex_full_audit.py`. Main review
records the actual combined result and any remaining limitations before final
approval. [Test directory](../../tests/)
