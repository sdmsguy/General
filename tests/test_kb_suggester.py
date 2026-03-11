from pathlib import Path

from copilot_core import KBSuggester


def test_kb_suggest_returns_relevant_articles():
    kb = KBSuggester(Path('kb_articles.json'))
    results = kb.suggest('My outlook keeps asking password repeatedly')
    assert results
    assert 'Outlook' in results[0]['title']


def test_kb_suggest_returns_empty_for_unrelated_issue():
    kb = KBSuggester(Path('kb_articles.json'))
    results = kb.suggest('quantum flux capacitor broke in warp core')
    assert results == []
