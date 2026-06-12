"""Unit tests for the pure (no LLM, no engine) helpers in pipeline.py.

These guard the resilient scenario-matching fallback chain
(LLM match -> keyword overlap -> default) that runs when the DB/LLM layer
returns nothing useful.
"""
import pipeline


def test_normalize_name_strips_parens_and_collapses_separators():
    assert pipeline._normalize_name("Multi-Front Defense") == "multi_front_defense"
    assert pipeline._normalize_name("Siege Planning (v2)") == "siege_planning"
    assert pipeline._normalize_name("time__phased  production") == "time_phased_production"


def test_resolve_db_name_exact_match_wins():
    candidates = ["Multi-Front Defense", "Siege Planning"]
    assert pipeline._resolve_db_name("Multi-Front Defense", candidates) == "Multi-Front Defense"


def test_resolve_db_name_fuzzy_match_on_casing_and_separators():
    candidates = ["Multi-Front Defense", "Siege Planning"]
    # LLM may return a differently-cased / spaced variant of the DB key.
    assert pipeline._resolve_db_name("multi front defense", candidates) == "Multi-Front Defense"


def test_resolve_db_name_unknown_returns_input_unchanged():
    candidates = ["Multi-Front Defense"]
    assert pipeline._resolve_db_name("Totally Unknown Mode", candidates) == "Totally Unknown Mode"


def test_keyword_fallback_picks_highest_overlap():
    details = {
        "Multi-Front Defense": {"description": "defend multiple fronts against waves"},
        "Siege Planning": {"description": "plan a siege on a fixed base"},
    }
    assert pipeline._keyword_fallback("defend against waves", details) == "Multi-Front Defense"


def test_keyword_fallback_no_overlap_returns_none():
    details = {"Siege Planning": {"description": "plan a siege"}}
    assert pipeline._keyword_fallback("xyzzy qwerty", details) is None
