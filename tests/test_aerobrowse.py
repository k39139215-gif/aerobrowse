from aerobrowse.engine import AeroBrowser
from aerobrowse.pruner import SemanticPruner
from aerobrowse.turbo import TurboEngine


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


def test_semantic_pruner_fidelity_and_nested_cards():
    """Verify that complex nested DOMs (like quote boxes, product cards, truncated titles) retain 100% data."""
    card_html = """
    <div class="container">
        <div class="quote">
            <span class="text">“Imagination is more important than knowledge.”</span>
            <span>by <small class="author">Albert Einstein</small></span>
        </div>
        <ol>
            <li>
                <article class="product">
                    <h3><a href="/book1" title="The Great Gatsby Full Title">The Great...</a></h3>
                    <p class="price">£29.99</p>
                    <p class="instock">In stock</p>
                </article>
            </li>
        </ol>
    </div>
    """
    pruner = SemanticPruner()
    res = pruner.prune(card_html)

    # 1. Spans and small tags must not be skipped
    assert "Albert Einstein" in res["markdown"]
    assert "Imagination is more important than knowledge" in res["markdown"]

    # 2. Truncated titles with title attribute must be resolved to full title
    assert "The Great Gatsby Full Title" in res["markdown"]
    assert "£29.99" in res["markdown"]
    assert "In stock" in res["markdown"]

    # 3. Action map check
    action_labels = [a["label"] for a in res["actions"]]
    assert "The Great Gatsby Full Title" in action_labels


def test_turbo_engine_local(site):
    from aerobrowse.security import NetworkPolicy

    engine = TurboEngine(policy=NetworkPolicy(allow_networks=("127.0.0.1/32",)))
    res = engine.fetch(site)
    assert res["success"] is True
    assert res["engine"] == "turbo"
    assert len(res["markdown"]) > 0
    assert res["reduction_pct"] > 0


def test_aerobrowser_unified(site):
    from aerobrowse.security import NetworkPolicy

    browser = AeroBrowser(policy=NetworkPolicy(allow_networks=("127.0.0.1/32",)))
    res = browser.fetch(site)
    assert res["success"] is True
    assert "Private service secret" in res["markdown"]
    assert res["reduction_pct"] > 0
    browser.close()
