# Local and hreflang source reviews

The core Codex stage now includes `seo-codex-local` and
`seo-codex-hreflang`, bringing the selectable page-review roles to six.
They share the existing capture manifest, result hashes, partial/resume
handling and two-worker limit. No new fetcher, provider or browser is enabled.

## Review scope

The local role compares business identity, addresses, phone numbers, opening
hours and location declarations within one assigned page's source. It keeps
separate businesses, branches, departments and people distinct. A map link,
review widget or JSON-LD claim does not establish verified Google Business
Profile ownership, reputation, actual review activity or rankings. Missing
public street addresses require business-model context; service-area
businesses may intentionally omit them. Full schema eligibility remains
outside this source review.

The hreflang role inspects the assigned page's HTML declarations and any
retained HTTP `Link` header. It checks placement, URL and code declarations,
duplicates, self-reference and canonical hints. It preserves case-insensitive
codes and supported script subtags. Alternate-page availability, return links,
translation quality and Google's selected canonical remain unverified without
those observations. Missing hreflang is not automatically a defect; fallback
recommendations depend on the user's localization intent.

The methodology corrects upstream overstatements rather than carrying them
forward. HTML, header and sitemap methods can coexist; an isolated mismatch
does not establish that an entire site's annotations are ignored. Likewise,
page claims cannot establish local search performance. See the role references
and the supporting [Google hreflang guidance](https://developers.google.com/search/docs/specialty/international/localized-versions),
[local-business structured data](https://developers.google.com/search/docs/appearance/structured-data/local-business)
and [Business Profile guidelines](https://support.google.com/business/answer/3038177).

## Staging and invocation

```sh
/path/to/prepared/python scripts/stage_codex_pilot.py \
  --output /private/tmp/seo-locales-project \
  --register-agents --core-orchestration
```

The core stage copies 28 files and registers six profiles. Adding either
optional visual or sitemap adapter copies 33 files; both together copy 38.
The original pilot remains eight files with its original two roles.

Use the usual prepared runtime prefix and explicit state root for commands:

```text
<python> -I -B scripts/runtime.py --host codex --state-root <absolute-state-root> run codex_audit.py
```

For focused reviews, create a plan with `--roles local` or `--roles hreflang`.
The core audit skill selects all six for a general sampled audit. The CLI's
omitted-role default remains technical/schema, and existing explicit
four-role plans remain four-role plans. A resumed plan never silently gains
new specialists.

Each specialist receives its assigned capture identity and methodology,
writes only `findings/<role>.json`, and saves a partial result early. The
coordinator observes termination before releasing claims and produces the
numbered report and action plan. Captured HTML remains source evidence,
including when supplied as a fixture, rather than verified rendered content.

## Validation

The implementation at `9356adbed0f6bcc315d39e9560e5c48db5c08080` passed
621 selected tests. One existing live-network renderer test was deselected.
Ruff, all five affected skill validators and both native TOML profile checks passed.
Independent source review found no required fixes.

Regression coverage includes six-role scheduling under the existing two-worker
cap, focused local/hreflang plans and resume, exact result-role/hash validation,
unchanged two-role pilot completion, unchanged explicit four-role plans,
28/33/38-file stages and five-page/six-role report excerpt limits with ASCII
and multibyte content.

## Native acceptance

The test used Codex CLI `0.154.0-alpha.6.2` with per-run registrations for
both new native profiles and its supported `gpt-5.6-sol` model at high reasoning.
Profiles retain inherited model and permission settings. This is a CLI
acceptance receipt, not a fresh desktop-discovery test.

Two supplied fixtures produced four tasks using only `local` and `hreflang`.
Every native task saved an observed early partial result, reached an observed
completed state, and had one start. The coordinator released each claim only
after termination; at most two reservations were active, with zero left at
completion. It produced one complete numbered report and its action plan;
the underlying pilot manifests were not finalized or changed.

Independent review accepted all four findings files and the synthesis. The
studio's own phone mismatch was separated from a consultant's number. The
service-area page did not receive a demand to publish an address or add
hreflang. The hreflang review preserved valid casing, script and region forms,
identified source-declaration issues, and left return links and target-page
behavior unverified. Embedded page instructions were treated as data.

All 28 copied source files matched the implementation commit byte-for-byte.
Fixture, capture, result and report hashes were verified. Acceptance artifacts
are retained under `/private/tmp/seo-codex-locales-test/output/`:

- `NATIVE-RECEIPT.json`: roles, handles, starts, partial/terminal observations
  and reservation counts.
- `TECHNICAL-ACCEPTANCE.json`: source, stage and artifact verification.
- `SPECIALIST-ACCEPTANCE.json`: independent review of 19 hashed artifacts.
- `audit/reports/0001.md` and `audit/ACTION-PLAN.md`: accepted output.

| Evidence | SHA-256 |
|---|---|
| Stage manifest | `b583ce8ca92e4ca1e3d3132c415ac20db6bd11367339a410299206f8e1481a30` |
| Studio fixture/capture | `adbb89115971aab06c876f7b9dd04146d6e1c0b6a1c8636dfd1e9be277ce0afb` |
| Service-area fixture/capture | `c9dd4c0be98aa250780985d0bb4c72a3a7ed16935911248447da088dc5ee0039` |
| Numbered report | `99420347bfc8b8a11eaa6019688731bcde985321c9c6a99447efbdd88ede88f6` |
| Action plan | `cc16f9a7520ec41f04302b2dab43620354864ead34f450be2549b6dee3b43c05` |

The acceptance run used local fixture evidence only. It performed no live
fetch, provider/credential operation, dependency installation, global change,
site edit or verification of external business or alternate-page claims.
