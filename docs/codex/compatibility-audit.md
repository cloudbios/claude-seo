# Codex compatibility audit

Status: source audit complete; implementation and live compatibility tests not started.
Date: November 8, 2026 (America/Los_Angeles).

## Baseline and scope

Repository: [cloudbios/claude-seo](https://github.com/cloudbios/claude-seo), forked from
[AgriciDaniel/claude-seo](https://github.com/AgriciDaniel/claude-seo).
Audited source: `6be93f45064ffbadced572b5d5c95f55fd263af0`; plugin version: `2.5.0`.
Both remotes had that same `main` commit when inspected. All source references below
refer to that baseline, not to future upstream changes.

Danny authorized a compatibility audit and a concrete pilot plan. This document
does not authorize implementation, installation, credential migration, paid API
requests, publication, or changes to existing Codex configuration. The intended
product is a Codex adaptation maintained against the Claude SEO upstream; maintaining
Claude as a second supported runtime is not a product requirement.

The audit used three independent source reviews, a static file inventory, and
current official OpenAI documentation. The 60 core Python files parsed successfully
with Python's `ast.parse`; no repository module was imported or executed. No SEO
audit, installer, hook, test suite, browser, or external SEO provider was run.
Installed skills and credentials were not changed or used.

## Decision

Proceed with a small Codex adapter and an isolated, credential-free pilot. Preserve
the SEO methodology, scripts, schemas, and regression tests wherever their behavior
is appropriate. Prove the existing compatibility paths before replacing them.

The current source is not verified as a working Codex installation. However, a
wholesale runtime rewrite is also unjustified: its core is ordinary Python, and
current Codex supports several relevant compatibility features. Changes should
address observed contract differences, rather than rename every occurrence of
"Claude" or copy the older installed Codex port wholesale.

## Inventory

| Component | Observed count | Assessment |
| --- | ---: | --- |
| Top-level skills | 26 | Reuse SEO procedures; adapt discovery, paths, routing and scope boundaries. |
| Top-level agent definitions | 19 | Convert Claude frontmatter to native Codex profiles or explicit delegated instructions. |
| Core Python files | 60 | Reuse candidates; 57 are in the managed runtime's dispatch allowlist. |
| Optional extension directories / skills | 9 / 9 | Separate integration projects; not nine interchangeable MCP servers. |
| Agent definitions under extensions | 3 | DataForSEO and image-gen mirror root roles; Matomo adds another role. |
| Python test modules | 76 | Existing regression inventory, not a passing result from this audit. |
| Files under `tests/fixtures` | 2 | Preserve existing fixture evidence. |
| Shared references under `skills/seo/references` | 17 | Preserve alongside skill-specific references and assets. |

[compatibility-inventory.csv](compatibility-inventory.csv) lists every core skill,
agent and Python script, every extension skill/agent, and the main packaging/hook
entry points. Its classifications are static triage, not runtime certifications.

Static scans found no imports of `anthropic`, `openai`, `claude`, or `claude_code`
in the 60 core Python files. Textual Claude references occur in 35 of those files;
their presence alone does not imply a runtime dependency. Conversely, an absence
of that text does not prove that a script is safe to run without credentials or
cannot mutate state.

## Official Codex contracts checked

These documents were fetched on November 8, 2026. They describe supported product
contracts; the exact installed host must still pass the pilot.

| Contract | Implication for this fork |
| --- | --- |
| [Skills and customization](https://learn.chatgpt.com/docs/customization/overview#skills) | `SKILL.md`, supporting scripts and references are reusable; project skills belong under `.agents/skills` or a supported plugin package. |
| [Custom agents](https://learn.chatgpt.com/docs/agent-configuration/subagents#custom-agents) | Native standalone TOML profiles require `name`, `description`, and `developer_instructions`; they inherit parent permissions, provider and MCP servers. |
| [Plugin packaging](https://developers.openai.com/plugins/build/plugins#plugin-structure) | Root `plugin.json` is the preferred portable manifest; compatibility manifests also exist. Do not assume `agents/*.md` becomes native Codex agents through packaging. |
| [Plugin hooks](https://developers.openai.com/plugins/build/plugins#bundled-mcp-servers-and-lifecycle-hooks) | Hook processes receive `PLUGIN_ROOT` / `PLUGIN_DATA` plus Claude compatibility aliases. This does not by itself establish expansion of variables in skill-body prose. |
| [PostToolUse](https://learn.chatgpt.com/docs/hooks#posttooluse) | `Edit` and `Write` match `apply_patch`, but its input uses `tool_input.command`, not `tool_input.file_path`. `additionalContext` and exit-2 feedback are supported. |
| [Hook trust](https://learn.chatgpt.com/docs/hooks#review-and-trust-hooks) | New or changed non-managed hooks require trust review. Installation must not bypass it. |
| [Claude plugin adaptation](https://developers.openai.com/plugins/guides/submit-claude-plugin) | Skills/resources can be retained; agents, settings and other host-specific behavior need deliberate adaptation. Public-directory submission has separate restrictions and is outside this pilot. |

The upstream `AGENTS.md` describes cross-host aliases at lines 33 and 44-53.
Its portability checker validates a limited source format, not actual Codex
discovery, permission enforcement, execution or report quality.

## Findings and required treatment

### 1. The core can be retained; runtime and installation paths need verification

`scripts/runtime.py:73` resolves the source root; `:77` discovers version metadata;
`:103` detects plugin mode; `:122` selects writable runtime storage. These decisions
currently recognize Claude variables and manifests. The reusable parts include
allowlisted dispatch, supported interpreter selection, staged setup/rollback,
argument-array subprocess execution, exit codes and signal handling.

The first pilot should pass explicit temporary runtime paths through the existing
interface and verify behavior. Introduce a shared host/path resolver only where a
measured gap requires it. Preserve the safety properties of `runtime.py` and
`url_safety.py`; do not replace the launcher with arbitrary shell execution.

The existing installers still clone **AgriciDaniel/claude-seo** and target
`.claude/skills` / `.claude/agents` (`install.sh:8-15`, `install.ps1:140-147`).
Running an installer from this fork does not mean it installs this fork.
Uninstallers use broad `seo-*` deletion patterns (`uninstall.sh:35-44`,
`uninstall.ps1:39-48`). A future installer needs explicit source identity and a
manifest of files it owns; it must preserve unrelated or older installations.
Installation and uninstallation are excluded from the pilot.

### 2. Native agent definitions and bounded orchestration are needed

All 19 root agents specify Claude model aliases, turn limits, and tool lists.
Five select `opus`, 14 select `sonnet`; neither is a Codex model choice.
See `agents/seo-content.md:1-7`, `agents/seo-technical.md:1-7`, and
`agents/seo-dataforseo.md:6` for the MCP-specific grant.

Native Codex profiles should preserve specialist instructions while using the
parent's available model unless a deliberate model/effort policy is configured.
Do not translate a tool list into a claim of independent sandbox enforcement:
profiles inherit the parent's permissions and integrations.

The full audit covers up to 500 pages and has ten effectively always-on specialist
paths plus conditional providers (`skills/seo-audit/SKILL.md:17-50`). A scheduler
must respect the host's available concurrency and retain the existing sequential
fallback. The pilot uses two roles only: technical and schema.

Use unique pilot names so the already-installed `seo-*` skills and agents cannot
silently satisfy discovery checks. Retain partial findings before an agent runs
out of budget; 17 of 19 root agents already specify this persistence pattern.

### 3. Schema feedback has a specific input mismatch and limited validation

The hook's matcher and feedback format are not fundamentally incompatible with
current Codex. The actionable mismatch is file discovery:
`hooks/validate-schema.py:264-282` reads an argv file or `tool_input.file_path`,
while Codex `apply_patch` supplies a patch in `tool_input.command`. The existing
handler can silently skip that event.

The validator also skips unsupported files, unreadable paths and files over
10 MiB; `.astro` and standalone `.json` are outside its extension list
(`hooks/validate-schema.py:288-316`). Invalid JSON and missing context/type produce
warning feedback with exit 0; only selected placeholder/deprecated/retired
findings produce exit 2 (`:318-337`). An exit 0 cannot be equated with a clean
schema validation result.

Source review additionally identifies a possible unhandled `TypeError` for legal
array-valued `@type`: list values reach membership checks at `:221-232`. This is
a source inference, not a reproduced failure. Add a fixture and reproduce it
before changing the validator.

The pilot must explicitly validate captured/emitted HTML and report parsed,
failed and skipped blocks. Cover `@graph`, inherited context, `@type` arrays,
bad JSON and reference integrity. Do not claim full Schema.org validation or
Google rich-result eligibility from the current hook. Automatic hook adaptation
can follow, with a test proving that feedback reaches the model; it must not
replace the explicit acceptance step.

### 4. A read-only workflow needs stronger scope and evidence boundaries

Some shared instructions progress from analysis into implementation, drift
capture and recurring monitoring (`skills/seo/references/thinking-framework-validate-act.md:48-72`).
Other paths generate images, submit URLs, write metadata, or call paid services.
The Codex adapter must make those proposed next steps unless separately authorized.

`seo-page` has a scorecard but no named capture/evidence contract. It also asks
questions such as orphan status and uniqueness that one fetched URL cannot
establish (`skills/seo-page/SKILL.md:20-33,67-87`). The pilot needs a shared capture
manifest with URLs, time, status, headers, hashes, tool versions, representation
and explicit performed/failed/skipped checks. Findings must reference evidence.
No full-site score, measured CWV claim, traffic claim or indexing confirmation
should be synthesized from source inspection alone.

### 5. Runtime isolation does not isolate credentials and caches

State is spread across `google_auth.py:30`, `backlinks_auth.py:52`,
`matomo_auth.py:55`, `dataforseo_costs.py:50`, `drift_baseline.py:35`,
`moz_api.py:47`, and `keyword_planner.py:90`. Some nominal credential reads can
change file permissions. Runtime subprocesses inherit the parent environment
(`runtime.py:215`); setup-error redaction does not sanitize all child output.

The pilot must use an explicit child environment and temporary state roots and
must not invoke auth-discovery modules. A later provider phase should consolidate
path policy and test configuration precedence, secret-safe errors and no silent
fallback into another host's credentials. Do not copy Danny's existing credentials
or installation files into the fork or a test package.

### 6. Optional integrations need individual acceptance

| Extension | Actual integration | Codex treatment |
| --- | --- | --- |
| DataForSEO | MCP plus Python helpers and USD cost ledger | Discover exact tools; preserve narrow grants and pre-call cost controls. |
| Banana | MCP and Python image helpers | Separate audit from paid generation/editing; generation is outside pilot. |
| Firecrawl | MCP crawl/map/search | Verify tools and paid-request boundaries; no automatic setup. |
| Ahrefs | MCP, with exact tool contracts not enumerated in the skill | Bind available tools explicitly; do not assume the existing connector has the same interface. |
| Bing Webmaster | Python reporting and IndexNow submission | Separate reporting from URL-submission authority. |
| Matomo | Authenticated Python reporting | Verify endpoint/path policy and read-only behavior separately. |
| Unlighthouse | Local Python/npx wrapper | Browser, dependency-download and output-write prerequisites; not MCP. |
| SE Ranking | Skill plus stored key; no supplied client/MCP transport | Incomplete integration recipe; unavailable until implemented and tested. |
| Profound | Skill plus stored key; no supplied client/MCP transport | Incomplete integration recipe; unavailable until implemented and tested. |

Extension installers edit Claude settings or configuration. Do not run them as
Codex setup. The Ahrefs and SE Ranking skills describe cross-vendor use of the
DataForSEO ledger, but that implementation prices DataForSEO endpoints in USD;
it does not implement Ahrefs unit accounting or general vendor pricing
(`extensions/ahrefs/skills/seo-ahrefs/SKILL.md:45`,
`extensions/seranking/skills/seo-seranking/SKILL.md:42`,
`scripts/dataforseo_costs.py:276,393,548`). Those claims need correction before
the affected integration is enabled.

### 7. CI and notices must be adapted deliberately

Existing CI covers Linux Python 3.11/3.12/3.14, macOS/Windows 3.11, lint, secret
scanning and dependency auditing. Some legs enable live GitHub tests. Keep an
offline fixture baseline separate from network integration results.

Two source findings should be addressed before using their affected paths:

- `.github/workflows/v2.yml:133` interpolates free-text workflow input directly
  into shell source. Pass it via an environment variable before dispatching it.
- `.github/workflows/windows-smoke.yml:53-55` validates a ref against the author's
  repository; fork-only branches require the intended repository identity.

No workflow was dispatched or enabled during this audit. Neither finding was
exploited. Fixing them is a later scoped change, not part of this documentation PR.

Preserve the MIT copyright and permission notice in `LICENSE`. FLOW references
have separate CC BY 4.0 attribution (`skills/seo-flow/references/prompts/README.md`,
`skills/seo-flow/SKILL.md:117-125`); the blanket MIT frontmatter is not a substitute.
Use the author's public source only. The private repository topology described
in `CLAUDE.md` does not grant access or publishing authority for this fork.

## Implementation order

1. Build and verify the [single-page pilot](pilot-plan.md) in a temporary project.
2. Adapt schema feedback and host state/configuration, reproducing the source
   findings first and retaining existing safety regressions.
3. Expand native routing and bounded orchestration to the full skill/agent set.
4. Accept optional integrations one by one, including cost and mutation controls.
5. Build ownership-aware installation, packaging and upstream-sync procedures.
6. Only after acceptance, propose replacing the installed legacy suite. Keep a
   recovery copy and an exact inventory; no global replacement is implied now.

## Verification and limits

- Confirmed fork identity, upstream identity, clean baseline and exact source SHA.
- Enumerated source components and parsed all 60 core Python files without import.
- Independently reviewed runtime, workflow, hook, extension and test contracts.
- Compared the identified host seams with fetched official Codex documentation.
- No functional test, dependency install, provider call, browser review or model
  accuracy benchmark was performed. All component statuses remain unverified at runtime.

This audit establishes a feasible, bounded adaptation plan. It does not establish
feature parity or authorize the proposed implementation phases.
