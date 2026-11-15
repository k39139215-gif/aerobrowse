import pytest
from aerobrowse.pruner import SemanticPruner
from aerobrowse.turbo import TurboEngine
from aerobrowse.engine import AeroBrowser


def test_semantic_pruner():
    raw_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Page</title>
        <script>console.log("tracking analytics script");</script>
        <style>.ad-banner { display: block; }</style>
    </head>
    <body>
        <header>
            <nav>
                <a href="/home">Home</a>
                <a href="/pricing">Pricing</a>
            </nav>
        </header>
        <main>
            <h1>Welcome to AeroBrowse</h1>
            <p>The featherweight browser engine for AI agents.</p>
            <input type="text" placeholder="Search documentation..." name="q" id="search-box">
            <button id="submit-btn">Search Now</button>
        </main>
        <footer>
            <p>Copyright 2026</p>
        </footer>
    </body>
    </html>
    """

    pruner = SemanticPruner()
    res = pruner.prune(raw_html)

    assert res["title"] == "Test Page"
    assert "tracking analytics script" not in res["markdown"]
    assert "AeroBrowse" in res["markdown"]
    assert len(res["actions"]) >= 4  # Home, Pricing, Input, Button
    assert res["reduction_pct"] > 0

    # Verify action tags
    action_labels = [a["label"] for a in res["actions"]]
    assert "Home" in action_labels
    assert "Pricing" in action_labels


def test_turbo_engine_local():
    # Test turbo engine with httpbin / example or fast domain
    engine = TurboEngine()
    res = engine.fetch("https://httpbin.org/html")
    assert res["success"] is True
    assert res["engine"] == "turbo"
    assert len(res["markdown"]) > 0
    assert res["reduction_pct"] > 0


def test_aerobrowser_unified():
    browser = AeroBrowser()
    res = browser.fetch("https://example.com")
    assert res["success"] is True
    assert "Example Domain" in res["title"]
    assert res["reduction_pct"] > 0
    browser.close()
