/**
 * Parses raw recommendation data from the data provider into a clean,
 * structured shape ready for component rendering.
 *
 * Handles:
 *  - final_recommendation as JSON string OR already-parsed array
 *  - Graceful fallback to search_results when final_recommendation is missing/broken
 *  - Field priority: final_recommendation > search_results
 *  - DOI sanitization (trims, rejects "N/A" / "nan" / empty)
 *  - Case-insensitive product name matching (trim + toLowerCase)
 *  - Preserves original final_recommendation order
 */

function normalizeName(name) {
  if (typeof name !== 'string') return '';
  return name.trim().toLowerCase();
}

function isValidDoi(doi) {
  if (typeof doi !== 'string') return false;
  var trimmed = doi.trim();
  if (trimmed === '') return false;
  if (trimmed.toUpperCase() === 'N/A') return false;
  if (trimmed.toLowerCase() === 'nan') return false;
  return true;
}

function safeDoi(doi) {
  if (!isValidDoi(doi)) return null;
  return doi.trim();
}

function safeSimilarity(value) {
  if (value == null) return null;
  var num = Number(value);
  if (isNaN(num)) return null;
  return num;
}

function safeScore(value) {
  if (value == null) return null;
  var num = Number(value);
  if (isNaN(num)) return null;
  return num;
}

/**
 * Parse final_recommendation from its raw form.
 * Accepts JSON string, already-parsed array, or null.
 * Returns { items: [], warning: null | string }
 */
function parseFinalRecommendation(raw) {
  if (typeof raw === 'string') {
    try {
      var parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        return { items: parsed, warning: null };
      }
      console.error('final_recommendation parsed but is not an array');
      return { items: null, warning: 'Recommendation ranking unavailable — showing candidate products from search results.' };
    } catch (e) {
      console.error('Failed to parse final_recommendation:', e.message);
      return { items: null, warning: 'Recommendation ranking unavailable — showing candidate products from search results.' };
    }
  }

  if (Array.isArray(raw)) {
    return { items: raw, warning: null };
  }

  return { items: null, warning: null };
}

/**
 * Build fallback recommendation cards from search_results only.
 */
function buildFallbackCards(searchResults) {
  return searchResults.map(function (sr) {
    var name =
      (sr.metadata && sr.metadata.product_name) || sr.name || '';
    return {
      product_name: name,
      score: null,
      similarity: safeSimilarity(sr.similarity),
      reason: null,
      doi: safeDoi((sr.metadata && sr.metadata.source_doi) || ''),
      description_raw: sr.description || '',
      iupac_name: (sr.metadata && sr.metadata.iupac_name) || null,
      tags: (sr.metadata && sr.metadata.tags) || null,
      isTop: false
    };
  });
}

/**
 * Main entry point.
 *
 * @param {Object} rawData  - The raw JSON object from the data provider.
 * @returns {{ formatter: Object, recommendations: Array, warning: string|null }}
 */
export function parseRecommendationData(rawData) {
  if (!rawData || !rawData.formatter) {
    throw new Error('Invalid data format: missing "formatter" root key');
  }

  var formatter = rawData.formatter;
  var searchResults = Array.isArray(formatter.search_results)
    ? formatter.search_results
    : [];

  // --- Parse final_recommendation ---
  var parseResult = parseFinalRecommendation(formatter.final_recommendation);
  var finalRecs = parseResult.items;
  var warning = parseResult.warning;

  // --- Build search_results lookup map by normalized name ---
  var srMap = {};
  for (var i = 0; i < searchResults.length; i++) {
    var sr = searchResults[i];
    var srName = (sr.metadata && sr.metadata.product_name) || sr.name || '';
    var key = normalizeName(srName);
    if (key) {
      srMap[key] = sr;
    }
  }

  // --- If final_recommendation parsed successfully, merge in order ---
  if (finalRecs !== null && finalRecs.length > 0) {
    var merged = [];

    for (var j = 0; j < finalRecs.length; j++) {
      var finalRec = finalRecs[j];
      var productName = finalRec.product_name || '';
      var lookupKey = normalizeName(productName);
      var sr = srMap[lookupKey] || null;

      var doi = safeDoi(finalRec.doi)
        ? safeDoi(finalRec.doi)
        : (sr && sr.metadata ? safeDoi(sr.metadata.source_doi) : null);

      var similarity = safeSimilarity(finalRec.similarity_score) != null
        ? safeSimilarity(finalRec.similarity_score)
        : safeSimilarity(sr ? sr.similarity : null);

      var score = safeScore(finalRec.score);

      merged.push({
        product_name: productName,
        score: score,
        similarity: similarity,
        reason: typeof finalRec.reason === 'string' ? finalRec.reason : null,
        doi: doi,
        description_raw: sr ? (sr.description || '') : '',
        iupac_name: (sr && sr.metadata && sr.metadata.iupac_name) || null,
        tags: (sr && sr.metadata && sr.metadata.tags) || null,
        isTop: j === 0
      });
    }

    return {
      formatter: {
        raw_input: formatter.raw_input || '',
        refined_input: formatter.refined_input || '',
        verification_score:
          formatter.verification_score != null ? formatter.verification_score : null,
        verification_rules: formatter.verification_rules || '',
        iteration_count:
          formatter.iteration_count != null ? formatter.iteration_count : 0
      },
      recommendations: merged,
      warning: null
    };
  }

  // --- final_recommendation unavailable → fallback to search_results ---
  if (searchResults.length > 0) {
    return {
      formatter: {
        raw_input: formatter.raw_input || '',
        refined_input: formatter.refined_input || '',
        verification_score:
          formatter.verification_score != null ? formatter.verification_score : null,
        verification_rules: formatter.verification_rules || '',
        iteration_count:
          formatter.iteration_count != null ? formatter.iteration_count : 0
      },
      recommendations: buildFallbackCards(searchResults),
      warning:
        warning ||
        'Recommendation ranking unavailable — showing candidate products from search results.'
    };
  }

  // --- Nothing available ---
  return {
    formatter: {
      raw_input: formatter.raw_input || '',
      refined_input: formatter.refined_input || '',
      verification_score:
        formatter.verification_score != null ? formatter.verification_score : null,
      verification_rules: formatter.verification_rules || '',
      iteration_count:
        formatter.iteration_count != null ? formatter.iteration_count : 0
    },
    recommendations: [],
    warning: null
  };
}
