# Biochemical Product Recommendation Report — Frontend Module

Standalone, zero-dependency recommendation report page. Reads data from a local
JSON file and renders a scientific-report-style UI. No backend required.

## Quick Start

```bash
cd frontend
python -m http.server 8080
```

Open `http://localhost:8080` in a modern browser.

> ES modules require HTTP serving — `file://` protocol is not supported.

## File Structure

```
frontend/
  index.html                          # Entry page (Tailwind CDN + FontAwesome CDN)
  data/
    interfaceData.json                # Sample data source
  js/
    app.js                            # Bootstrap, orchestration, error/loading states
    utils/
      dataProvider.js                 # Data access abstraction (local JSON → future API)
      recommendationParser.js         # Parse, merge, validate, PubChem extraction
    components/
      RecommendationReport.js         # Page layout + info cards + recommendation list
      RecommendationCard.js           # Single recommendation card (all 8 sections)
```

## Parser Output (camelCase)

`parseRecommendationData(rawData)` returns:

```js
{
  formatter: {
    rawInput: "我想做玻璃",
    refinedInput: "...",
    verificationScore: 99,
    verificationRules: "...",
    iterationCount: 1
  },
  recommendations: [
    {
      productName: "silica",
      evaluationScore: 99,
      semanticSimilarity: 0.5123,
      recommendationReason: "Silica ...",
      functionalDescriptionClean: "Product: silica\nDescription: ...",  // w/o PubChem block
      descriptionRaw: "Product: silica\n...\nPubChem Data:\nIUPAC: ...", // full original
      doi: "10.1016/j.biortech.2018.03.044",
      iupacName: "dioxosilane",
      pubchemCid: "24261",
      pubchemDescription: "Silicon dioxide is a silicon oxide made up of...",
      tags: "industrial chemical; pharmaceuticals; silica; ...",
      isTop: true,
      isFallback: false
    }
  ],
  warning: null
}
```

## JSON Field → UI Field Mapping

### Top Info Cards

| JSON Path | Parser Field | UI Card |
|-----------|-------------|---------|
| `formatter.raw_input` | `rawInput` | User Input |
| `formatter.refined_input` | `refinedInput` | Refined Input |
| `formatter.verification_score` | `verificationScore` | Verification Score (color-coded) |
| `formatter.iteration_count` | `iterationCount` | Iteration Count |

### Recommendation Card Sections

| Section | Data Source (priority order) |
|---------|------------------------------|
| Product Name | `final_rec.product_name` → `sr.metadata.product_name` → `sr.name` |
| Evaluation Score | `final_rec.score` (progress bar, color-coded: green≥80, amber≥50, red<50) |
| Semantic Similarity | `final_rec.similarity_score` → `sr.similarity` (4 decimal places) |
| Recommendation Reason | `final_rec.reason` |
| Functional Description | `sr.description` — with PubChem block stripped (`functionalDescriptionClean`) |
| PubChem Data | **Parsed from** `sr.description` (see below) |
| DOI | `final_rec.doi` → `sr.metadata.source_doi` |

### PubChem Data Parsing

PubChem fields are extracted from `search_results[].description` using line-based regex:

| PubChem Field | Regex Pattern | Fallback |
|--------------|---------------|----------|
| IUPAC | `/^IUPAC:\s*(.*)$/mi` | `sr.metadata.iupac_name` |
| PubChem CID | `/^PubChem CID:\s*(.*)$/mi` | — |
| PubChem Description | `/^PubChem Description:\s*(.*)$/mi` | — |
| Tags | `/^Tags:\s*(.*)$/mi` | `sr.metadata.tags` |

The PubChem block is identified by the `PubChem Data:` marker line in the
description. Everything before that marker becomes `functionalDescriptionClean`;
everything after is parsed into individual labeled fields.

Invalid values (`""`, `"N/A"`, `"nan"`, `"null"`, `"undefined"`) are treated
as missing — they do not render in the UI.

### Merging Logic

- Products are matched between `final_recommendation` and `search_results` by
  `product_name` (case-insensitive, trimmed).
- The card order follows `final_recommendation` order exactly (no re-sort).
- If `final_recommendation` is missing or fails to parse, fallback cards are
  built from `search_results` alone, and a warning banner is shown.
- Fallback cards also parse PubChem Data from `search_results[].description`.
- The first card is marked "Top Recommendation" with an amber highlight.

### DOI Handling

- DOI values are trimmed.
- Empty string, `"N/A"`, `"nan"`, `"null"`, `"undefined"` are treated as missing.
- Valid DOIs render as `https://doi.org/{doi}` with `target="_blank"` and
  `rel="noopener noreferrer"`.

## Reconnecting to a Real API

When the backend recommendation API is ready, only **one file** needs to change:

**`js/app.js`** — update the `DataProvider` constructor:

```js
// Before (local JSON)
var dataProvider = new DataProvider({
  dataSource: 'local',
  localPath: './data/interfaceData.json'
});

// After (live API)
var dataProvider = new DataProvider({
  dataSource: 'api',
  apiEndpoint: '/api/recommendation/',  // or full URL
  apiMethod: 'POST',
  timeout: 15000
});
```

If the API returns the same JSON shape (a root `formatter` key with
`raw_input`, `refined_input`, `search_results`, `final_recommendation`, etc.),
**no other code changes are needed**. The parser and components consume the
same shape regardless of data source.

If the API returns a different shape, add a transformation step in
`recommendationParser.js` before the merge logic.

## Current Limitations

- **Local JSON only** — reads data exclusively from `frontend/data/interfaceData.json`.
  Does not call any backend API.
- **HTTP required** — ES modules (`type="module"`) cannot load over `file://` protocol.
  Must be served over HTTP (e.g. `python -m http.server 8080`).
- **No build tools** — no npm, webpack, Vite, or TypeScript compilation step.
  All dependencies (Tailwind CSS, FontAwesome) are loaded from CDN.
- **Static data** — page content is static once loaded from JSON. No real-time updates,
  no user input form for new queries (this is a report page, not a search page).

## Styling

- **Layout/colors/spacing**: Tailwind CSS utility classes via CDN.
- **Custom animations**: Defined in the `<style>` block in `index.html`
  (fadeInUp, skeleton pulse, progress bar transition, card staggering).

To replace the Tailwind CDN with compiled/static CSS for production:

1. Generate a static CSS build with `tailwindcss` CLI or PostCSS, configured
   to scan `index.html` and `js/**/*.js` for used classes.
2. Replace the `<script src="https://cdn.tailwindcss.com">` line with a
   `<link rel="stylesheet" href="...">` pointing to the compiled file.
3. The custom `<style>` block in `index.html` is already isolated and can
   remain as-is or be merged into the compiled output.

## Supported Browsers

All modern browsers that support ES modules: Chrome 61+, Firefox 60+,
Safari 11+, Edge 16+.
