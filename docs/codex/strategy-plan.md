# SEO strategy from supplied evidence

The optional `seo-codex-plan` workflow produces five planning documents from
explicit business goals, resources and up to five existing verified page
captures. It supports a new site or an existing site's supplied page sample.
It performs no live research, audit import, account setup or publishing.

## Requirements and evidence

Input JSON requires `mode` (`new` or `existing`), `business_context`, `audience`,
`goals`, `resources`, `horizon_weeks` and `sources`. Resources explicitly
describe `team`, `capacity` and `budget`; `unknown` is an acceptable answer
that remains a planning dependency. The horizon is 1–52 relative weeks, so
the planner need not invent a start date. Optional `industry` and
`constraints` guide the plan.

Each source has a unique `id`, a `kind` (`site` or `reference`) and an absolute
`capture` path to an existing pilot capture. Existing mode requires at least
one site capture. New mode permits no sources and clearly labels the result
as input-only planning. Reference sites do not establish the target business's
services, credentials or market position. Neither mode establishes search
demand, current rankings or a complete inventory of a live site.

The adapter preserves the original input-file identity, normalized
`input.json`, capture and source-manifest hashes, and implementation provenance.
The original input and capture directories must remain available and unchanged
for validation. Rechecking evidence never silently refreshes the plan from the
live site.

## Structured plan and outputs

The native planner first creates labelled notes that separate user claims,
source observations, inferences and proposals. Roadmap and content-calendar
items reference those notes. Each roadmap task has an owner role, priority,
week window, dependencies and observable completion criteria. Dependency IDs
must exist, be acyclic and finish before their dependent tasks begin. Calendar
items stay within their associated roadmap task's window.

The site structure separates captured site URLs from proposed relative paths.
Observed pages must match a supplied site capture; a proposed path has no
verified availability. Parent and link relationships reference known page IDs.
Existing URLs are not changed merely to fit an industry template.

Measurement items define a business question, metric, scope, collection source,
owner and cadence. Baselines remain explicitly unavailable. Targets are unset
or labelled proposals, never forecasts. Unknown capacity prevents claiming that
the schedule is feasible. Planned analytics work does not authorize account
changes or collection of real data.

The coordinator renders five documents from the validated native result:

- `SEO-STRATEGY.md`: requirements, evidence notes, priorities and limitations.
- `IMPLEMENTATION-ROADMAP.md`: sequenced tasks and completion evidence.
- `CONTENT-CALENDAR.md`: proposed content work and required evidence.
- `SITE-STRUCTURE.md`: observed and proposed pages and relationships.
- `MEASUREMENT-PLAN.md`: definitions and proposed measurement work.

Industry guidance retains the upstream planning distinctions for SaaS, local
services, e-commerce, publishers, agencies and general businesses. It omits
fixed publication quotas, minimum word counts, speculative growth numbers,
location-page thresholds and unverified platform claims. The repository's MIT
license and attribution to AgriciDaniel and contributors are preserved.

## Staging and lifecycle

```sh
/path/to/prepared/python scripts/stage_codex_pilot.py \
  --output /private/tmp/seo-strategy-project \
  --register-agents --strategy-plan
```

The strategy stage copies 34 files and registers seven profiles. Staging both
strategy and content briefs copies 39 files and registers eight profiles;
their shared `codex_planning.py` helper is copied once. All five optional
workflows together copy 54 files and register eleven profiles. The core stage
remains 28 files with six page-review roles; the original pilot remains eight.

The shared helper contains JSON, path, evidence, provenance and escaping
functions. The brief and strategy adapters retain separate schemas,
lifecycles and outputs. The helper is not a runtime command. The brief's
existing command names and nine-section result contract are preserved.

Use the caller's prepared Python and absolute dedicated state root:

```text
<python> -I -B scripts/runtime.py --host codex --state-root <absolute-state-root> run codex_plan.py prepare --input <absolute-requirements.json> --output <new-absolute-output>
```

Validate before handing the evidence and exact hashes to the native planner.
Only that planner writes `findings/plan.json`; it saves a valid partial result
early. Observe its actual termination before the coordinator finalizes all five
documents, then validate again. A failed or incomplete native result stays
partial. Finalization does not overwrite an earlier output.

## Validation

The implementation passed 992 selected tests, including 120 strategy tests
and the existing content-brief regressions. One existing live-network renderer
test was deselected. Ruff, both affected skill validators and independent
source review passed.

Native acceptance is recorded below after the isolated run completes.
