/**
 * Parses raw recommendation data into a clean, structured shape
 * with camelCase field names ready for component rendering.
 *
 * Handles:
 *  - final_recommendation as JSON string OR already-parsed array
 *  - PubChem Data extraction from search_results[].description
 *  - Description split: functionalDescriptionClean vs PubChem block
 *  - DOI sanitization (trim, reject "", "N/A", "nan", "null", "undefined")
 *  - Case-insensitive product name matching (trim + toLowerCase)
 *  - Preserves original final_recommendation order
 */

/* ── generic helpers ─────────────────────────────────── */

function normalizeName(value) {
  return String(value || '').trim().toLowerCase();
}

function isValidDoi(doi) {
  if (typeof doi !== 'string') return false;
  var trimmed = doi.trim();
  if (trimmed === '') return false;
  var upper = trimmed.toUpperCase();
  if (upper === 'N/A') return false;
  var lower = trimmed.toLowerCase();
  if (lower === 'nan' || lower === 'null' || lower === 'undefined') return false;
  return true;
}

function safeDoi(doi) {
  if (!isValidDoi(doi)) return null;
  return doi.trim();
}

function safeScore(value) {
  if (value == null) return null;
  var num = Number(value);
  if (isNaN(num)) return null;
  return num;
}

function safeSimilarity(value) {
  if (value == null) return null;
  var num = Number(value);
  if (isNaN(num)) return null;
  return num;
}

/**
 * Extract a single labelled line value from multi-line text.
 * Pattern: /^Label:\s*(.*)$/mi
 */
function getLineValue(text, label) {
  var escaped = label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  var regex = new RegExp('^' + escaped + ':\\s*(.*)$', 'mi');
  var match = String(text || '').match(regex);
  return match ? match[1].trim() : '';
}

/**
 * Whether a string value should be treated as missing.
 * Rejects empty, "N/A", "nan", "null", "undefined".
 */
function isInvalidValue(val) {
  if (typeof val !== 'string') return true;
  var trimmed = val.trim();
  if (trimmed === '') return true;
  var lower = trimmed.toLowerCase();
  if (lower === 'n/a' || lower === 'nan' || lower === 'null' || lower === 'undefined') return true;
  return false;
}

/* ── PubChem helpers ─────────────────────────────────── */

/**
 * Parse PubChem fields from raw description text.
 * Returns: { iupacName, pubchemCid, pubchemDescription, tags }
 */
function parsePubChemFields(rawDescription) {
  var text = String(rawDescription || '');
  return {
    iupacName: getLineValue(text, 'IUPAC'),
    pubchemCid: getLineValue(text, 'PubChem CID'),
    pubchemDescription: getLineValue(text, 'PubChem Description'),
    tags: getLineValue(text, 'Tags')
  };
}

/**
 * Strip the PubChem Data block from the description.
 * Only strips when "PubChem Data:" marker exists;
 * otherwise returns the original text unchanged.
 */
function stripPubChemBlock(rawDescription) {
  var text = String(rawDescription || '');
  if (!/^PubChem Data:/mi.test(text)) {
    return text;
  }
  var idx = text.search(/^PubChem Data:/mi);
  if (idx === -1) return text;
  var before = text.substring(0, idx);
  return before.replace(/\n+$/, '').trim() || text.trim();
}

/* ── final_recommendation parsing ────────────────────── */

/**
 * Parse final_recommendation from its raw form.
 * Accepts JSON string, already-parsed array, or null/undefined.
 * Returns { items: array|null, warning: string|null }
 */
function parseFinalRecommendation(raw) {
  if (Array.isArray(raw)) {
    return { items: raw, warning: null };
  }

  if (typeof raw === 'string') {
    try {
      var parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        return { items: parsed, warning: null };
      }
      console.error('final_recommendation parsed but is not an array');
      return {
        items: null,
        warning: 'Recommendation ranking unavailable — showing candidate products from search results.'
      };
    } catch (e) {
      console.error('Failed to parse final_recommendation:', e.message);
      return {
        items: null,
        warning: 'Recommendation ranking unavailable — showing candidate products from search results.'
      };
    }
  }

  return { items: null, warning: null };
}

/* ── merge helper ────────────────────────────────────── */

/**
 * Merge a single final_recommendation item with its matched search_result,
 * and extract PubChem fields from description.
 * Returns a camelCase recommendation object.
 */
function buildMergedItem(finalRec, sr, isFirst) {
  // Product name — 3-level fallback
  var productName = finalRec.product_name
    || (sr && sr.metadata && sr.metadata.product_name)
    || (sr && sr.name)
    || '';

  var rawDesc = sr ? (sr.description || '') : '';

  // Parse PubChem from description
  var parsedPubChem = parsePubChemFields(rawDesc);

  // Clean description (w/o PubChem block)
  var cleanDesc = stripPubChemBlock(rawDesc);

  // DOI priority: final_rec.doi > sr.metadata.source_doi
  var doi = safeDoi(finalRec.doi)
    ? safeDoi(finalRec.doi)
    : (sr && sr.metadata ? safeDoi(sr.metadata.source_doi) : null);

  // Similarity priority: final_rec.similarity_score > sr.similarity
  var similarity = safeSimilarity(finalRec.similarity_score) != null
    ? safeSimilarity(finalRec.similarity_score)
    : safeSimilarity(sr ? sr.similarity : null);

  // Score from final_recommendation
  var score = safeScore(finalRec.score);

  // IUPAC: metadata > description-parsed
  var iupacName = (sr && sr.metadata && sr.metadata.iupac_name && !isInvalidValue(sr.metadata.iupac_name))
    ? sr.metadata.iupac_name.trim()
    : (parsedPubChem.iupacName && !isInvalidValue(parsedPubChem.iupacName) ? parsedPubChem.iupacName : null);

  // PubChem CID: description-parsed (metadata usually doesn't have this)
  var pubchemCid = (parsedPubChem.pubchemCid && !isInvalidValue(parsedPubChem.pubchemCid))
    ? parsedPubChem.pubchemCid : null;

  // PubChem Description: description-parsed
  var pubchemDescription = (parsedPubChem.pubchemDescription && !isInvalidValue(parsedPubChem.pubchemDescription))
    ? parsedPubChem.pubchemDescription : null;

  // Tags: metadata > description-parsed
  var tags = (sr && sr.metadata && sr.metadata.tags && !isInvalidValue(sr.metadata.tags))
    ? sr.metadata.tags.trim()
    : (parsedPubChem.tags && !isInvalidValue(parsedPubChem.tags) ? parsedPubChem.tags : null);

  return {
    productName: productName,
    evaluationScore: score,
    semanticSimilarity: similarity,
    recommendationReason: typeof finalRec.reason === 'string' ? finalRec.reason : null,
    functionalDescriptionClean: cleanDesc,
    descriptionRaw: rawDesc,
    doi: doi,
    iupacName: iupacName,
    pubchemCid: pubchemCid,
    pubchemDescription: pubchemDescription,
    tags: tags,
    isTop: isFirst,
    isFallback: false
  };
}

/* ── fallback builder ────────────────────────────────── */

function buildFallbackCards(searchResults) {
  return searchResults.map(function (sr) {
    var name = (sr.metadata && sr.metadata.product_name) || sr.name || '';
    var rawDesc = sr.description || '';
    var parsedPubChem = parsePubChemFields(rawDesc);
    var cleanDesc = stripPubChemBlock(rawDesc);

    var iupacName = (sr.metadata && sr.metadata.iupac_name && !isInvalidValue(sr.metadata.iupac_name))
      ? sr.metadata.iupac_name.trim()
      : (parsedPubChem.iupacName && !isInvalidValue(parsedPubChem.iupacName) ? parsedPubChem.iupacName : null);

    var pubchemCid = (parsedPubChem.pubchemCid && !isInvalidValue(parsedPubChem.pubchemCid))
      ? parsedPubChem.pubchemCid : null;

    var pubchemDescription = (parsedPubChem.pubchemDescription && !isInvalidValue(parsedPubChem.pubchemDescription))
      ? parsedPubChem.pubchemDescription : null;

    var tags = (sr.metadata && sr.metadata.tags && !isInvalidValue(sr.metadata.tags))
      ? sr.metadata.tags.trim()
      : (parsedPubChem.tags && !isInvalidValue(parsedPubChem.tags) ? parsedPubChem.tags : null);

    return {
      productName: name,
      evaluationScore: null,
      semanticSimilarity: safeSimilarity(sr.similarity),
      recommendationReason: null,
      functionalDescriptionClean: cleanDesc,
      descriptionRaw: rawDesc,
      doi: safeDoi((sr.metadata && sr.metadata.source_doi) || ''),
      iupacName: iupacName,
      pubchemCid: pubchemCid,
      pubchemDescription: pubchemDescription,
      tags: tags,
      isTop: false,
      isFallback: true
    };
  });
}

/* ── main entry point ────────────────────────────────── */

/**
 * @param {Object} rawData  - The raw JSON object from the data provider.
 * @param {Object} [options] - Reserved for future use.
 * @returns {{ formatter: Object, recommendations: Array, warning: string|null }}
 */
export function parseRecommendationData(rawData, options) {
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

  // --- Build search_results lookup map ---
  var srMap = {};
  for (var i = 0; i < searchResults.length; i++) {
    var sr = searchResults[i];
    var srName = (sr.metadata && sr.metadata.product_name) || sr.name || '';
    var key = normalizeName(srName);
    if (key) {
      srMap[key] = sr;
    }
  }

  // --- Build formatter info (camelCase) ---
  var formatterInfo = {
    rawInput: formatter.raw_input || '',
    refinedInput: formatter.refined_input || '',
    verificationScore: formatter.verification_score != null ? formatter.verification_score : null,
    verificationRules: formatter.verification_rules || '',
    iterationCount: formatter.iteration_count != null ? formatter.iteration_count : 0
  };

  // --- final_recommendation parsed successfully → merge in order ---
  if (finalRecs !== null && finalRecs.length > 0) {
    var merged = [];

    for (var j = 0; j < finalRecs.length; j++) {
      var finalRec = finalRecs[j];
      var lookupKey = normalizeName(finalRec.product_name || '');
      var sr = srMap[lookupKey] || null;
      merged.push(buildMergedItem(finalRec, sr, j === 0));
    }

    return {
      formatter: formatterInfo,
      recommendations: merged,
      warning: null
    };
  }

  // --- final_recommendation unavailable but search_results exists → fallback ---
  if (searchResults.length > 0) {
    return {
      formatter: formatterInfo,
      recommendations: buildFallbackCards(searchResults),
      warning: warning ||
        'Recommendation ranking unavailable — showing candidate products from search results.'
    };
  }

  // --- Nothing available ---
  return {
    formatter: formatterInfo,
    recommendations: [],
    warning: null
  };
}
