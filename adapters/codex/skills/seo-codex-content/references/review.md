# Qualitative review of captured content

Use `capture/page.html` for source text and document order,
`capture/parsed.json` for convenient extracted fields, and
`capture/schema.json` only for structured claims. Cite the actual file and
field or a short source excerpt in every finding. These are source-HTML
observations: hidden, template or client-rendered content may differ from what
readers see. Do not describe source text as confirmed visible content.

## Intent and structure

Use the user's supplied audience, page purpose and question. If absent, state
a narrow inference from the title and page text; do not invent keyword demand
or search intent research. Check whether the opening answers the principal
question, sections help readers find related answers, and terms are explained
for that audience. Read heading sequence from HTML: the parsed `h1`, `h2` and
`h3` arrays group levels and do not preserve their interleaving or all levels.
A skipped heading level alone is not proof of poor usefulness or a penalty.

Identify confusing passages, unexplained terms, redundant statements and
specific unanswered questions with excerpts. Suggest a concrete clarification
or topic to investigate. Do not invent the missing answer, clinical claims,
business policies, prices, credentials or outcome statistics. Compare duplicate
phrasing only within the supplied evidence; do not infer site-wide uniqueness.

## Observable Who / How / Why

- **Who:** report any byline, author bio link, reviewer attribution and claimed
  qualifications. A name or credential string is evidence of attribution,
  not verification of identity, licensure, experience or expertise.
- **How:** report descriptions of methods, research, first-hand experience,
  review process, dates, corrections and citations where present. A case study
  or testimonial is a page claim; its accuracy and provenance remain unverified.
- **Why:** assess whether the text serves the stated reader question and makes
  its commercial purpose understandable. Do not infer the author's motives.

Distinguish dates in article text, metadata and structured data. Report their
labels and any inconsistency; a date alone cannot establish freshness, a real
revision, factual currency or a required update cadence. Cite actual links and
their nearby claim context when discussing sourcing. Do not fetch destinations
or treat a domain name as proof of authority. For consequential claims, propose
qualified review or source verification as a dependency rather than certifying
accuracy from this capture.

## Evidence limits

The parser's `word_count` is a crude count that can include head text and
navigation/footer boilerplate. It is not a main-content word count, readability
calculation or thin-content verdict. Do not apply word minimums or numeric
E-E-A-T, content-quality, readability or AI-citation scores.

The parser's internal/external link lists can contain `mailto:` and `tel:`
links as well as navigation, promotions and citations. Their lengths do not
measure citation quality or count. Inspect relevant anchors in context.

Clarity, first-hand claims and attribution can be described qualitatively;
external reputation, factual accuracy, author authenticity, AI authorship,
search/AI citations and ranking effects cannot be established here. Missing
source text may reflect rendering or access limitations. State that limit
instead of declaring the live page empty or deficient.

## Result contract

Write only the assigned `findings/content.json`, using the exact
`pilot-manifest.json` `capture.sha256`. Save valid JSON early with
`role: "content"`, `status: "partial"`, `findings: []` and a useful
`limitations` array; preserve those fields when completing it with
`status: "complete"`. Findings and limitations are arrays of strings.
Completion means this bounded review finished, not that unavailable checks
passed. Do not modify evidence or coordinator-owned ledgers and reports.

## Attribution

Adapted under MIT from AgriciDaniel and contributors' upstream
`skills/seo-content/SKILL.md`, `agents/seo-content.md` and
`skills/seo/references/eeat-framework.md`. The upstream qualitative attribution
and usefulness dimensions inform this review; numeric scores, word floors,
AI-authorship heuristics and external verification claims are excluded.
