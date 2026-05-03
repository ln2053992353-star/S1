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
      dataProvider.js                 # Data access abstraction
      recommendationParser.js         # Parse, merge, validate, sort
    components/
      RecommendationReport.js         # Page layout + info cards + recommendation list
      RecommendationCard.js           # Single recommendation card
```

## JSON Field → UI Field Mapping

### Top Info Cards

| JSON Path | UI Card |
|-----------|---------|
| `formatter.raw_input` | User Input |
| `formatter.refined_input` | Refined Input |
| `formatter.verification_score` | Verification Score (color-coded badge) |
| `formatter.iteration_count` | Iteration Count |

### Recommendation Cards

| UI Field | Data Source (priority order) |
|----------|------------------------------|
| Product Name | `final_recommendation[].product_name` |
| Evaluation Score | `final_recommendation[].score` |
| Semantic Similarity | `final_recommendation[].similarity_score` → `search_results[].similarity` |
| Recommendation Reason | `final_recommendation[].reason` |
| Functional Description | `search_results[].description` (matched by product name) |
| DOI | `final_recommendation[].doi` → `search_results[].metadata.source_doi` |
| IUPAC Name | `search_results[].metadata.iupac_name` |
| Tags | `search_results[].metadata.tags` |

### Merging Logic

- Products are matched between `final_recommendation` and `search_results` by
  `product_name` (case-insensitive, trimmed).
- The card order follows `final_recommendation` order exactly (no re-sort).
- If `final_recommendation` is missing or fails to parse, fallback cards are
  built from `search_results` alone, and a warning banner is shown.
- The first card is marked "Top Recommendation" with an amber highlight.

### DOI Handling

- DOI values are trimmed.
- Empty string, `"N/A"`, and `"nan"` are treated as missing (no link rendered).
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
  apiMethod: 'POST',                     // if needed
  timeout: 15000
});
```

If the API returns the same JSON shape (a root `formatter` key with
`raw_input`, `refined_input`, `search_results`, `final_recommendation`, etc.),
**no other code changes are needed**. The parser and components consume the
same shape regardless of data source.

If the API returns a different shape, add a transformation step in
`recommendationParser.js` before the merge logic.

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
