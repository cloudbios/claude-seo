# Review of captured image markup

Read `capture/parsed.json` `images` entries and confirm relevant details in
`capture/page.html`. Cite the image's zero-based index plus field, or a unique
source excerpt. Match raw elements carefully when the same URL is repeated;
the parser may resolve `src` against the base URL. Source HTML is not a render
or a response from an image server.

## Alternative text in context

Distinguish `alt: null` (missing attribute) from `alt: ""` (empty attribute).
Empty alt may be intentional for decoration; inspect `role`, `aria-hidden`,
link/button context and surrounding text before recommending a change. These
signals suggest intent without proving the image is decorative. A functional
image may need an accessible purpose; recommend verifying its actual role.

Flag filename-like, generic, repetitive or apparently stuffed text only with
an excerpt and context. Repeated alt may be appropriate for repeated images.
Do not impose an arbitrary character minimum/maximum or demand keywords.
Without image pixels, neither accurate depiction nor an exact replacement alt
can be verified. Recommend text reflecting the verified image or function,
rather than inventing what an unseen image depicts.

## Declared sizing and delivery

- Inspect `width` and `height` together. They are declared HTML values, not
  measured intrinsic dimensions or proof of a correct aspect ratio. Inspect
  inline `style` for dimensions or `aspect-ratio`; external CSS may reserve
  space even when the element lacks these attributes. Missing declarations
  alone do not prove measured layout shift.
- Read raw `<picture>` / `<source>` markup, `srcset` descriptors and `sizes`
  alongside the fallback `<img>`. The parser does not extract these fields.
  Describe declared alternatives and apparent inconsistencies; actual browser
  selection and appropriateness depend on viewport, layout and file evidence.
- Report `loading` with `lazy_method`. Supported classifications are `native`,
  `perfmatters`, `ewww`, `js-generic` and `none`. The last means no supported
  pattern was detected, not proof that JavaScript never delays loading.
  A detected JS method is not proof the loader executes successfully. Raw
  `data-*` attributes may point to a different resource than placeholder `src`.
- Inspect raw `fetchpriority` and `decoding` as declared hints. A high priority
  value does not identify the LCP element. Do not recommend lazy loading every
  image or diagnose a lazy-loaded image as an LCP defect without a render.
- Filename extensions and declared source `type` are hints only. Do not call a
  file's actual format, MIME type, bytes or compression quality verified.

## Unavailable evidence

No image requests or rendering occur in this review. Do not claim intrinsic
dimensions, file-size savings, visual quality, successful loads, above-fold
placement, LCP timing, CLS, cache/CDN behavior or image search rankings.
CSS backgrounds, script-created images and runtime changes may not appear in
the parsed image list. With no `<img>` elements, report that observation rather
than saying the page has no images. A recommendation can name a later render
or file inspection as a dependency, without performing or claiming that work.

Do not generate images, convert formats, inject metadata, fetch assets, run
provider tools or mutate source HTML. Retain observed limitations even if all
markup checks finish.

## Result contract

Write only the assigned `findings/images.json`, using the exact
`pilot-manifest.json` `capture.sha256`. Save valid JSON early with
`role: "images"`, `status: "partial"`, `findings: []` and a useful
`limitations` array; preserve those fields when completing it with
`status: "complete"`. Findings and limitations are arrays of strings.
Completion means this bounded review finished, not that unavailable checks
passed. Do not modify evidence or coordinator-owned ledgers and reports.

## Attribution

Adapted under MIT from AgriciDaniel and contributors' upstream
`skills/seo-images/SKILL.md`. The source's alt text, responsive markup and
lazy-loader distinctions inform this review. Its image fetching, file-size
thresholds, format conversion, generation and provider workflows are excluded.
