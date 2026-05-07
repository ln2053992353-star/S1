"""
Nutrition recommendation service — wraps 师姐's LangGraph workflow.

The LangGraph app lives in nutritionRecommend/main.py (heavy models, ChromaDB).
This module provides a clean interface for Django views to call.

IMPORTANT: 师姐's main.py uses a relative path "../database/embeddingDB" for
ChromaDB. The CWD MUST be nutritionRecommend/ whenever ChromaDB operations
happen (both at import/init time AND at query time).
"""
import json
import logging
import sys
import os
import io

logger = logging.getLogger(__name__)

# Force UTF-8 mode on Windows to handle emoji prints in output_formatter
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_app = None
_nutrition_path = None


def _resolve_nutrition_path():
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'nutritionRecommend'
    )


def _get_app():
    """Lazy-load the LangGraph workflow. CWD must be nutritionRecommend/ during import."""
    global _app, _nutrition_path

    if _app is not None:
        return _app

    _nutrition_path = _resolve_nutrition_path()
    if _nutrition_path not in sys.path:
        sys.path.insert(0, _nutrition_path)

    saved_cwd = os.getcwd()
    try:
        os.chdir(_nutrition_path)
        import main as nutrition_main
        _app = nutrition_main.app
        logger.info("LangGraph nutrition workflow loaded successfully")
    finally:
        os.chdir(saved_cwd)

    return _app


def _nutrition_path_dir():
    global _nutrition_path
    if _nutrition_path is None:
        _nutrition_path = _resolve_nutrition_path()
    return _nutrition_path


def run_nutrition_search(raw_query: str, top_k: int = 20) -> dict:
    """
    Run the LangGraph nutrition recommendation workflow.

    Returns a dict with a 'formatter' key matching the frontend JSON schema:
        {
            formatter: {
                raw_input, refined_input, verification_score,
                verification_rules, search_results, iteration_count,
                final_recommendation
            }
        }

    CWD is temporarily switched to nutritionRecommend/ so that ChromaDB's
    relative path "../database/embeddingDB" resolves correctly.
    """
    if not raw_query or not raw_query.strip():
        return _empty_result(raw_query)

    try:
        app = _get_app()
        if app is None:
            return _error_result(raw_query, "LangGraph workflow failed to initialize")

        initial_state = {
            "raw_input": raw_query.strip(),
            "iteration_count": 0,
        }

        # ChromaDB uses relative path — CWD must be nutritionRecommend/
        saved_cwd = os.getcwd()
        try:
            os.chdir(_nutrition_path_dir())
            final_state = app.invoke(initial_state)
        finally:
            os.chdir(saved_cwd)

        search_results = final_state.get("search_results", [])
        final_rec_raw = final_state.get("final_recommendation", "")

        # abort_node returns a plain error-message string (not JSON)
        if isinstance(final_rec_raw, str) and final_rec_raw.startswith("After"):
            return _error_result(raw_query, final_rec_raw)

        return {
            "formatter": {
                "raw_input": raw_query.strip(),
                "refined_input": final_state.get("refined_input", raw_query),
                "verification_score": final_state.get("verification_score"),
                "verification_rules": final_state.get("verification_rules", ""),
                "search_results": search_results,
                "iteration_count": final_state.get("iteration_count", 1),
                "final_recommendation": final_rec_raw,
            }
        }

    except Exception as e:
        logger.error(f"Nutrition search failed: {e}")
        import traceback
        traceback.print_exc()
        return _error_result(raw_query, str(e))


def _empty_result(query: str) -> dict:
    return {
        "formatter": {
            "raw_input": query or "",
            "refined_input": "",
            "verification_score": None,
            "verification_rules": "",
            "search_results": [],
            "iteration_count": 0,
            "final_recommendation": json.dumps([], ensure_ascii=False),
        }
    }


def _error_result(query: str, message: str) -> dict:
    return {
        "formatter": {
            "raw_input": query or "",
            "refined_input": query or "",
            "verification_score": 0,
            "verification_rules": message,
            "search_results": [],
            "iteration_count": 1,
            "final_recommendation": json.dumps([], ensure_ascii=False),
        }
    }
