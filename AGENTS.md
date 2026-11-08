# Claude SEO: Multi-Platform Agent Instructions

> For **Cursor**, **Cursor Cloud Agents**, **Google Antigravity**, **Gemini CLI**,
> **Grok Build**,
> **OpenAI Codex CLI**, **Cline**, **Aider**, and any other agent harness that
> reads project-root agent instructions.
>
> Claude Code users: see `CLAUDE.md` instead.

## Codex full distribution

Use the generated Codex distribution for this host. Build and install it with
the [Codex installation guide](docs/codex/INSTALL.md), then load the installed
`$seo-codex` entrypoint or the matching `$seo-codex-<route>` skill. The generated
set contains 35 skills, 34 native `seo-full-*` profiles, and all 9 extension
resource trees. Full-port coverage and final validation status are recorded in
[FULL-PORT.md](docs/codex/FULL-PORT.md).

Run helpers through the installed `scripts/codex-seo` launcher with an explicit
absolute `--state-root`. Native `SKILL.md` contracts govern runtime commands,
provider discovery, authorization, and audit result formats. Full audit jobs
use `scripts/codex_full_audit.py`, a 1–500 page cap, same-origin HTML-link
discovery, and one or two concurrent specialists. Report robots exclusions,
uncaptured URLs, rendering gaps, and unavailable provider evidence.

The package keeps original skill resources in `source-skills/` for helpers
that need them. Discoverable native skills live in its `skills/` tree and are
installed under `.agents/skills/`. Generate them with
`python3 scripts/build_codex_skills.py` and verify reproducibility with `--check`.
Keep upstream `skills/` and `agents/` available for the other hosts.

Discover tools from the active Codex session's descriptions and schemas.
Select native `spawn_agent` profiles when available, or execute the assigned
methodology inline and record that mode. Skills and agent profiles inherit the
session's permissions and provider access. Keep secrets in the explicit state
root's `config/` directory or use supported provider environment inputs.
Credential migration, paid calls, installation, and external mutations each
require the user's applicable authorization.

## Cross-platform portability (v2.0.0)

Every skill in `skills/*/SKILL.md` is authored to a portable subset of the
Claude Code skill spec. Validate compatibility with your harness via:

```bash
./scripts/claude-seo run portability_check.py
```

The check confirms each `SKILL.md` has the minimum frontmatter every harness
expects (`name`, `description`, optional `model`, optional `tools`) and warns
on Claude-Code-specific features (`maxTurns`, multi-line tool list with
descriptive comments) that other harnesses may ignore but do not reject.

### Per-harness notes

| Harness | How to load claude-seo |
|---|---|
| **Cursor** | Symlink or copy `skills/` and `agents/` into `.cursor/rules/`. Commands are invoked as text prompts; the harness reads `SKILL.md` body as system context. |
| **Cursor Cloud Agents** | Push the repo; Cloud Agents read `AGENTS.md` automatically at session start. |
| **Google Antigravity** | Point the workspace at this repo root; Antigravity reads `AGENTS.md` first, falls back to `skills/`. |
| **Gemini CLI** | `gemini init` in this repo loads `AGENTS.md`. Skills are activated via `activate_skill <name>` in conversation. |
| **Grok Build** | Open this repository in Grok Build. It reads `AGENTS.md` and Claude Code compatible plugins and skills without a separate layout. Use `grok inspect` to verify discovery. See the [official compatibility guide](https://docs.x.ai/build/features/skills-plugins-marketplaces). |
| **OpenAI Codex CLI** | Reads project instructions and uses the generated native distribution. Follow `docs/codex/INSTALL.md`, then invoke `$seo-codex` or a route skill and discover available tools from the active session. |
| **Cline** | Loads `AGENTS.md` from project root. Skills appear as system messages; subagent delegation falls back to in-context expansion. |
| **Aider** | Reads `AGENTS.md` if present; otherwise falls back to README. Aider does not support sub-agent dispatch; the seo-* skills run inline. |

### Tool-name compatibility

Upstream tool names express required capabilities. Resolve file reads, edits,
shell commands, searches, web fetching, and agent dispatch against the current
harness's actual tool descriptions and argument schemas. Availability and
spelling vary by host and session. The Codex adapter translates runtime and
skill references and supplies native agent profiles. A provider's presence
must be established before using its examples as executable instructions.

For example, Claude's `Read`, `Write`, `Edit`, `Bash`, and `WebFetch` names
describe file reading, file writing, editing, shell execution, and fetching.
Codex, Cline, and Aider users must choose their session's actual equivalents;
these names are not automatic tool aliases.

## Overview

Claude SEO is a Tier 4 SEO analysis skill with 26 sub-skills (22 core + 1 orchestrator +
1 framework integration + 2 extension mirrors), 19 sub-agents (16 core + 1 framework
integration + 2 extension mirrors), and 79 Python execution scripts.

Those counts describe the upstream edition. The full Codex edition has 35
generated skills and 34 native profiles. The earlier bounded pilot remains in
`adapters/codex/skills/` for its documented saved-capture workflows.

## Upstream Quick Reference

For Codex, use `$seo-codex-<route>` for the corresponding workflow in this table.
Runtime setup and diagnostics use `$seo-codex setup` and `$seo-codex doctor`.

| Command | What it does |
|---------|-------------|
| `/seo audit <url>` | Full website audit with parallel subagent delegation |
| `/seo page <url>` | Deep single-page analysis |
| `/seo technical <url>` | Technical SEO audit (9 categories) |
| `/seo content <url>` | E-E-A-T and content quality analysis |
| `/seo content-brief <topic>` | Generate a content brief for a topic |
| `/seo schema <url>` | Schema.org detection, validation, generation |
| `/seo sitemap <url>` | XML sitemap analysis or generation |
| `/seo images <url>` | Image SEO: on-page audit, SERP analysis, file optimization |
| `/seo geo <url>` | AI Overviews / Generative Engine Optimization |
| `/seo plan <type>` | Strategic SEO planning |
| `/seo cluster <keyword>` | SERP-based semantic clustering and content architecture |
| `/seo sxo <url>` | Search Experience Optimization: page-type analysis, personas |
| `/seo drift baseline <url>` | Capture SEO baseline for change monitoring |
| `/seo drift compare <url>` | Compare current state to stored baseline |
| `/seo drift history <url>` | Show drift history over time |
| `/seo ecommerce <url>` | E-commerce SEO: product schema, marketplace intelligence |
| `/seo programmatic [url]` | Programmatic SEO at scale |
| `/seo competitor-pages [url]` | Competitor comparison pages |
| `/seo flow [stage]` | FLOW framework prompts (Find, Leverage, Optimize, Win, Local; prompts/sync utilities.) |
| `/seo local <url>` | Local SEO analysis (GBP, citations, reviews) |
| `/seo maps [cmd] [args]` | Maps intelligence (geo-grid, GBP audit, competitors) |
| `/seo hreflang <url>` | Hreflang/i18n SEO audit, cultural profiles, content parity |
| `/seo google [cmd] [url]` | Google SEO APIs (GSC, PageSpeed, CrUX, Indexing, GA4) |
| `/seo backlinks <url>` | Backlink profile analysis |
| `/seo backlinks setup` | Setup free backlink APIs |
| `/seo backlinks verify <url>` | Verify known backlinks still exist |
| `/seo dataforseo [cmd]` | Live SEO data via DataForSEO (extension) |
| `/seo image-gen [use-case]` | AI image generation for SEO assets (extension) |
| `/seo firecrawl [cmd] <url>` | Full-site crawling and site mapping (extension) |
| `/seo ahrefs [cmd] <target>` | Ahrefs backlink and keyword data (extension) |
| `/seo bing [cmd] <url>` | Bing Webmaster data and IndexNow (extension) |
| `/seo profound [cmd]` | LLM brand-citation tracking (extension) |
| `/seo seranking [cmd]` | AI share-of-voice tracking (extension) |
| `/seo matomo [cmd] [args]` | Matomo Reporting API: GA4 alternative or supplement (extension) |
| `/seo unlighthouse <url>` | Multi-page Lighthouse audits (extension) |

## Using with Cursor / Cursor Cloud

Cursor reads this file automatically. All SKILL.md files contain the full
analysis logic as natural language instructions. Python scripts in `scripts/`
provide execution capabilities.

**Running scripts directly** (Cursor doesn't have MCP):
```bash
# Page fetching with SSRF protection
./scripts/claude-seo run fetch_page.py https://example.com

# HTML parsing for SEO elements
./scripts/claude-seo run parse_html.py https://example.com

# PageSpeed Insights
./scripts/claude-seo run pagespeed_check.py https://example.com --json

# Drift baseline
./scripts/claude-seo run drift_baseline.py https://example.com

# DataForSEO (requires credentials)
DATAFORSEO_USERNAME=user DATAFORSEO_PASSWORD=pass ./scripts/claude-seo run dataforseo_merchant.py search "keyword"
```

**Cursor Cloud gotchas:**
- SSL certificates may not resolve for some domains. Investigate the certificate issue rather than disabling verification.
- Run bundled tools through `claude-seo`; never call the venv interpreter directly.
- Screenshots save to `/tmp/` not CWD. Check absolute paths.

## Using with Google Antigravity

Antigravity discovers this project via `.claude-plugin/plugin.json`.
Place the repo in `~/.gemini/antigravity/plugins/claude-seo/` or install via:

```bash
bash install.sh
```

## Architecture

```
skills/                    # 26 sub-skills (auto-discovered)
  seo/SKILL.md            # Main orchestrator + routing
  seo-cluster/            # Semantic clustering (v1.9.0)
  seo-sxo/                # Search Experience Optimization (v1.9.0)
  seo-drift/              # SEO drift monitoring (v1.9.0)
  seo-ecommerce/          # E-commerce SEO (v1.9.0)
  seo-audit/              # Full site audit
  seo-page/               # Single-page analysis
  seo-technical/          # Technical SEO
  seo-content/            # E-E-A-T quality
  seo-content-brief/      # Content brief generation
  seo-schema/             # Schema.org markup
  seo-sitemap/            # XML sitemaps
  seo-images/             # Image optimization
  seo-geo/                # AI search / GEO
  seo-agentic/            # Agent readiness (Lighthouse Agentic Browsing, WebMCP)
  seo-local/              # Local SEO
  seo-maps/               # Maps intelligence
  seo-plan/               # Strategic planning
  seo-hreflang/           # International SEO
  seo-google/             # Google APIs
  seo-backlinks/          # Backlink analysis
  seo-programmatic/       # Programmatic SEO
  seo-competitor-pages/   # Competitor pages
  seo-flow/               # FLOW framework integration
  seo-dataforseo/         # DataForSEO (extension)
  seo-image-gen/          # AI images (extension)
agents/                    # 19 subagents
scripts/                   # 79 Python scripts, including runtime and Codex adapter tools
schema/                    # JSON-LD templates
extensions/                # 9 MCP extensions: DataForSEO, Firecrawl, Banana, Ahrefs, SE Ranking, Profound, Bing Webmaster, Matomo, Unlighthouse
adapters/codex/full/        # Generated Codex skills, native profiles, resources, provenance
scripts/codex_runtime.py   # Explicit-state Codex helper dispatch and setup
scripts/codex_full_audit.py # Full-site crawl and specialist coordination
```

## Key Principles

1. **Progressive Disclosure**: Read SKILL.md for routing, load references on demand
2. **Industry Detection**: Auto-detect SaaS, e-commerce, local, publisher, agency
3. **Security**. Use the bundled URL-validation and fetching helpers for external URLs
4. **Config location**. Upstream uses `~/.config/claude-seo/`. Codex uses `config/` under its explicit state root

## Credits

Created by [@AgriciDaniel](https://github.com/AgriciDaniel).
v1.9.0 community contributions by Lutfiya Miller, Chris Muller, Florian Schmitz,
Dan Colta, and Matej Marjanovic. See [CONTRIBUTORS.md](CONTRIBUTORS.md).
