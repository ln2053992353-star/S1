from django.shortcuts import render
import time
from .search_service import hybrid_search


def search_view(request):
    raw_query = request.GET.get('q', '').strip()

    results = []
    search_time = 0.0
    ai_feedback = {}

    if raw_query:
        t0 = time.time()
        try:
            # 调用 search_service 中的混合搜索
            results, ai_feedback = hybrid_search(raw_query)
        except Exception as e:
            print(f"Search Error: {e}")
            results = []
        search_time = round(time.time() - t0, 3)

    return render(request, 'search.html', {
        'query': raw_query,
        'results': results,
        'time': search_time,
        'count': len(results),
        # 将 AI 的“思考过程”传给前端展示
        'rewritten_query': ai_feedback.get('english_query', ''),
        'filter_tags': ai_feedback.get('filter_tags', []),
    })