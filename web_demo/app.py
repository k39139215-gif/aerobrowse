"""
⚡ AeroBrowse Interactive Web Playground
========================================
Test live semantic pruning, token savings, and Set-of-Marks indexing on any URL.
Deployable directly to Hugging Face Spaces or Streamlit Cloud.
"""

import sys
import os
import streamlit as st
import pandas as pd

# Add parent directory to path so aerobrowse can be imported directly
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from aerobrowse import AeroBrowser

st.set_page_config(
    page_title="AeroBrowse Playground",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-title {
        font-size: 2.4rem;
        font-weight: 800;
        background: -webkit-linear-gradient(45deg, #00ffcc, #0077ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0px;
    }
    .metric-card {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-title">⚡ AeroBrowse Playground</h1>', unsafe_allow_html=True)
st.caption("Hybrid retrieval with measured token counts; see README for supported platforms and limitations")

# Sidebar Controls
st.sidebar.header("⚙️ Engine Configuration")
force_fidelity = st.sidebar.checkbox(
    "Force Fidelity Mode (CDP/Blink)",
    value=False,
    help="Forces full Chromium headless engine execution instead of bounded HTTP Turbo mode. Useful for dynamic SPAs."
)

st.sidebar.markdown("---")
st.sidebar.subheader("🌟 Quick Presets")
presets = {
    "Quotes to Scrape": "https://quotes.toscrape.com",
    "Books to Scrape (Catalog)": "https://books.toscrape.com",
    "Python.org (Docs & Portal)": "https://www.python.org",
    "Hacker News": "https://news.ycombinator.com",
    "Wikipedia (AI Article)": "https://en.wikipedia.org/wiki/Artificial_intelligence"
}

selected_preset = st.sidebar.selectbox("Choose a sample URL:", list(presets.keys()))
default_url = presets[selected_preset]

# Main Input Bar
url_input = st.text_input("Enter any web URL to prune & index:", value=default_url)

col_run, col_space = st.columns([1, 4])
with col_run:
    run_btn = st.button("🚀 Run AeroBrowse", type="primary", use_container_width=True)

if run_btn or url_input:
    with st.spinner(f"Browsing {url_input} via AeroBrowse..."):
        try:
            with AeroBrowser() as browser:
                result = browser.fetch(url_input, force_fidelity=force_fidelity)
            if not result.get("success"):
                st.error(result.get("error", {}).get("code", "REQUEST_FAILED"))
                st.stop()

            # Actual tokenizer counts.
            raw_tokens = max(1, result["original_tokens"])
            pruned_tokens = max(1, result["extracted_tokens"])
            tokens_saved = max(0, raw_tokens - pruned_tokens)
            
            # GPT-4o input cost: $2.50 per 1M tokens ($0.0000025 per token)
            cost_unpruned = (raw_tokens / 1_000_000) * 2.50
            cost_pruned = (pruned_tokens / 1_000_000) * 2.50
            dollars_saved = cost_unpruned - cost_pruned

            # Metrics Row
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.metric("Raw HTML Characters", f"{result['original_chars']:,}", f"~{raw_tokens:,} tokens")
            with m2:
                st.metric("Pruned Markdown Characters", f"{result['pruned_chars']:,}", f"~{pruned_tokens:,} tokens")
            with m3:
                st.metric("Token Bill Reduction", f"{result['reduction_pct']}%", f"-{tokens_saved:,} tokens", delta_color="normal")
            with m4:
                st.metric("GPT-4o Cost Saved / Fetch", f"${dollars_saved:.4f}", f"From ${cost_unpruned:.4f} down to ${cost_pruned:.4f}")

            st.markdown(f"**📌 Page Title**: `{result['title']}`")

            # Tabs for outputs
            tab_md, tab_actions, tab_raw = st.tabs([
                "📄 Pruned Markdown Preview",
                f"🎯 Set-of-Marks Actions ({len(result['actions'])})",
                "🔍 Raw Text & Debug Info"
            ])

            with tab_md:
                st.markdown(result["markdown"])

            with tab_actions:
                if result["actions"]:
                    df = pd.DataFrame(result["actions"])
                    st.dataframe(
                        df,
                        column_config={
                            "id": "Action ID",
                            "tag": "HTML Tag",
                            "label": "Action Text / Label",
                            "href": "Target Link (href)",
                            "input_type": "Input Type"
                        },
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("No interactive elements found on this page.")

            with tab_raw:
                st.subheader("Raw Pruned Markdown")
                st.code(result["markdown"], language="markdown")

        except Exception as e:
            st.error("Browser request failed; see the structured error and server diagnostics")

st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #888;">
    AeroBrowse is Open Source under MIT License • <a href="https://github.com/k39139215-gif/aerobrowse" target="_blank">Star on GitHub ⭐</a> • <a href="https://pypi.org/project/aerobrowse" target="_blank">View on PyPI 📦</a>
</div>
""", unsafe_allow_html=True)
