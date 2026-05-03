import json
import os
import time
from django.shortcuts import render
from .search_service import hybrid_search


def search_view(request):
    raw_query = request.GET.get('q', '').strip()

    if raw_query:
        # --- Live search: query the database ---
        results = []
        search_time = 0.0
        ai_feedback = {}

        try:
            t0 = time.time()
            results, ai_feedback = hybrid_search(raw_query)
            search_time = round(time.time() - t0, 3)
        except Exception as e:
            print(f"Search Error: {e}")
            results = []

        # Format results into the frontend JSON schema
        data = _build_formatter_data(raw_query, results, ai_feedback)

        return render(request, 'search.html', {
            'query': raw_query,
            'data_json': json.dumps(data, ensure_ascii=False),
            'search_time': search_time,
            'result_count': len(results),
        })

    # --- No query: load demo data from interfaceData.json ---
    json_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'frontend', 'data', 'interfaceData.json'
    )
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        data_json = json.dumps(data, ensure_ascii=False)
    except Exception as e:
        print(f"Error loading interfaceData.json: {e}")
        data_json = 'null'

    return render(request, 'search.html', {
        'query': '',
        'data_json': data_json,
        'search_time': 0,
        'result_count': 0,
    })


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_formatter_data(raw_query, results, ai_feedback):
    """Convert hybrid_search results into the { formatter: {...} } JSON schema."""
    refined_input = ai_feedback.get('english_query', raw_query)

    # ---- search_results ----
    search_results = []
    for product in results:
        tags_str = _collect_tags(product)
        source_doi = _collect_doi(product)
        pubchem = _collect_pubchem(product)
        score = getattr(product, 'match_score', 0) or 0

        # Build enriched description with PubChem Data block
        description = _build_enriched_description(product, pubchem)

        search_results.append({
            'name': product.product_name or '',
            'description': description,
            'metadata': {
                'product_name': product.product_name or '',
                'iupac_name': pubchem.get('iupac_name', ''),
                'pubchem_cid': pubchem.get('pubchem_cid', ''),
                'pubchem_description': pubchem.get('pubchem_description', ''),
                'tags': tags_str,
                'source_doi': source_doi,
            },
            'similarity': round(score / 100.0, 6),
        })

    # ---- final_recommendation ----
    final_recs = []
    for product in results:
        score = int(getattr(product, 'match_score', 0) or 0)
        doi = _collect_doi(product)

        final_recs.append({
            'product_name': product.product_name or '',
            'score': score,
            'reason': '',
            'doi': doi,
            'similarity_score': round(score / 100.0, 4),
        })

    return {
        'formatter': {
            'raw_input': raw_query,
            'refined_input': refined_input,
            'verification_score': None,
            'verification_rules': '',
            'search_results': search_results,
            'iteration_count': 1,
            'final_recommendation': json.dumps(final_recs, ensure_ascii=False),
        }
    }


def _collect_tags(product):
    """Return semicolon-separated tag names for a product."""
    tag_names = []
    try:
        for t in product.tags.all():
            tag_names.append(t.tag_name)
    except Exception:
        pass
    return '; '.join(tag_names)


def _collect_doi(product):
    """Return the best available DOI for a product."""
    # Try the product's own source_doi field first
    if product.source_doi and product.source_doi.strip():
        return product.source_doi.strip()
    # Fall back to the first related source
    try:
        sources = list(product.sources.all())
        if sources and sources[0].doi and sources[0].doi.strip():
            return sources[0].doi.strip()
    except Exception:
        pass
    return ''


def _collect_pubchem(product):
    """Collect PubChem data from YeastPubChemData if available."""
    pubchem = {
        'iupac_name': '',
        'pubchem_cid': '',
        'pubchem_description': '',
    }
    try:
        pubchem_data = getattr(product, 'pubchem_data', None)
        if pubchem_data:
            pubchem['iupac_name'] = pubchem_data.iupac_name or ''
            pubchem['pubchem_cid'] = str(pubchem_data.pubchem_cid) if pubchem_data.pubchem_cid else ''
            pubchem['pubchem_description'] = pubchem_data.functional_description or ''
    except Exception:
        pass
    return pubchem


def _pubchem_has_data(pubchem):
    """Return True if any PubChem field has a value."""
    return bool(
        pubchem.get('iupac_name') or
        pubchem.get('pubchem_cid') or
        pubchem.get('pubchem_description')
    )


def _build_enriched_description(product, pubchem):
    """Build description with PubChem Data block for frontend parser compatibility.

    Preserves the original product.description content, and appends a
    structured PubChem Data block when PubChem fields are available.
    """
    desc = product.description or ''

    if not _pubchem_has_data(pubchem):
        return desc

    # Append PubChem Data block in the format expected by recommendationParser.js
    pubchem_lines = ['PubChem Data:']
    if pubchem['iupac_name']:
        pubchem_lines.append(f"IUPAC: {pubchem['iupac_name']}")
    if pubchem['pubchem_cid']:
        pubchem_lines.append(f"PubChem CID: {pubchem['pubchem_cid']}")
    if pubchem['pubchem_description']:
        pubchem_lines.append(f"PubChem Description: {pubchem['pubchem_description']}")

    return desc + '\n' + '\n'.join(pubchem_lines)
