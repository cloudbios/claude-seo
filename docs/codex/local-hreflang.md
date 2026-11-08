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

Automated checks, independent review and native acceptance results will be
recorded after completion.
