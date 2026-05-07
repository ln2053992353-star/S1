import json
import os
import time
from django.shortcuts import render
from .nutrition_service import run_nutrition_search


def search_view(request):
    raw_query = request.GET.get('q', '').strip()

    if raw_query:
        # --- Live search: query via nutrition LangGraph workflow ---
        search_time = 0.0
        data = None

        try:
            t0 = time.time()
            data = run_nutrition_search(raw_query)
            search_time = round(time.time() - t0, 3)
        except Exception as e:
            print(f"Search Error: {e}")
            data = None

        if data is None:
            data_json = 'null'
            result_count = 0
        else:
            data_json = json.dumps(data, ensure_ascii=False)
            result_count = len(data.get('formatter', {}).get('search_results', []))

        return render(request, 'search.html', {
            'query': raw_query,
            'data_json': data_json,
            'search_time': search_time,
            'result_count': result_count,
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
