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
must exist, be acyclic and end by the dependent task's start week. Calendar
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
their shared `codex_planning.py` helper is copied once. All nine optional
workflows together copy 73 files and register fifteen profiles. The core stage
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

## Native acceptance

The implementation at `95ef77f48a23efe94e2cfcd0a6e0638eeef42326` was staged
with both planning workflows. The 39 copied files were compared with that
commit, and all 63 original stage, input, fixture and capture files remained
unchanged. The five strategy reports and the brief use their saved evidence
and result hashes.

A recorded Codex CLI `0.154.0-alpha.6.2` session used explicit per-run native
registrations with the supported `gpt-5.6-sol` model configured at high
reasoning. The profiles inherit model and permission settings. This is CLI
acceptance, not fresh desktop registration verification; child model identity
and some lifecycle details are limited to what the runtime exposes.

Three native cases exercised the final staged code:

- An existing-site strategy used two site captures and one reference capture.
  It retained the business's drawing-service scope, left budget and capacity
  unresolved, proposed a six-week sequence with an early confirmation gate,
  and preserved captured URLs. It did not borrow the reference company's
  construction or engineering services.
- A new SaaS strategy used requirements only. It treated the product as a
  concept, kept all pages proposed and respected limited founder time and
  unknown implementation capacity. It invented no customers, features,
  integrations, prices or measured results.
- The content-brief regression used its original nine-section contract and
  source captures. It preserved the target URL and useful content, kept
  source citations and distinguished keep/strengthen/add recommendations.

Independent review accepted the content, citations, dependency graphs,
relative schedules and measurement definitions. Baselines remained
unavailable, and targets were unset or explicitly proposed. Embedded page
instructions were treated as data. Each writer saved an observed early partial
result; the coordinator observed termination before finalization. The maximum
observed number of active native authors was two, with none remaining after
completion. All three jobs completed without correction turns or approval
rejections, and the recorded CLI session exited successfully.

No live site, account, provider integration or actual performance baseline was
tested. Saved examples establish the bounded workflows and artifact handling;
they do not establish business results or universal plan quality.

Acceptance files are retained under `/private/tmp/seo-codex-strategy-test/output/`:

- `NATIVE-RECEIPT.json`: native handles, partial and terminal observations,
  completion states and lifecycle visibility limits.
- `TECHNICAL-ACCEPTANCE.json`: exact staged-source, baseline and output hashes.
- `SPECIALIST-ACCEPTANCE.json`: independent content, citation and receipt review.
- `existing/` and `new/`: each strategy's five reports and supporting evidence.
- `brief-regression/`: the validated content-brief regression output.


| Evidence | SHA-256 |
| --- | --- |
| Stage manifest | `5cbff49658c530b83aaf7fed8b83d42ea241e837082a2885651363bb1217a150` |
| Existing-site strategy | `63af2fb09b8d824522c938fcffe34e9a04d5fa476edd5a8348852e15e92ef53b` |
| New-site strategy | `c02a217443bf18c2edcd7a26c315193683d4dc44b999f69844a6fec02a2da66b` |
| Content-brief regression | `a5375e3604dc6b23250a460cd4769ffd553894f6b3cddeac21ff42c2e31d0c1e` |
