
from dotenv import load_dotenv
load_dotenv()

import os

import streamlit as st

from pipeline.runner import run, load_cache, save_cache


def langsmith_link():
    """Return a LangSmith project URL when tracing is configured, else None."""
    tracing = os.getenv("LANGCHAIN_TRACING_V2", "").lower() == "true"
    if not (tracing and os.getenv("LANGCHAIN_API_KEY")):
        return None
    project = os.getenv("LANGCHAIN_PROJECT", "default")
    return f"https://smith.langchain.com/o/-/projects/p/{project}"

st.set_page_config(page_title="FMCG Deal Newsletter", layout="wide")
st.title("FMCG Deal Intelligence")
st.caption("M&A and investment activity in fast-moving consumer goods.")


def render_trace(rows):
    """Show the agent's per-deal decisions: relevance judgment and corroboration."""
    if not rows:
        return
    st.subheader("Agent decision trace")
    st.caption(
        "Every candidate deal and the decisions made on it: the relevance "
        "judgment, then the corroboration verdict and how many searches the "
        "agent ran before committing."
    )

    ls_url = langsmith_link()
    if ls_url:
        st.markdown(
            f"Full LLM traces (inputs, outputs, latency, token counts) are in "
            f"[LangSmith]({ls_url})."
        )

    # Compact table of all candidates.
    table = [
        {
            "Title": r.get("title", "")[:70],
            "Outlets": r.get("cluster_size", ""),
            "FMCG": r.get("is_fmcg", ""),
            "Deal": r.get("is_deal", ""),
            "Relevance": r.get("relevance_confidence", ""),
            "Verdict": r.get("verdict", ""),
            "Searches": r.get("searches_used", ""),
        }
        for r in rows
    ]
    st.dataframe(table, use_container_width=True, hide_index=True)

    # Per-deal reasoning for deals that reached the corroboration agent.
    agent_rows = [r for r in rows if r.get("verdict") in ("verified", "exhausted", "needs_search")]
    if agent_rows:
        st.markdown("**Corroboration reasoning**")
        for r in agent_rows:
            label = f"[{r.get('verdict', '')}] {r.get('title', '')[:80]}"
            with st.expander(label):
                st.write(f"Deal type: {r.get('deal_type', 'n/a')}")
                st.write(f"Relevance reason: {r.get('relevance_reason', 'n/a')}")
                st.write(f"Corroboration reason: {r.get('corroboration_reason', 'n/a')}")
                st.write(f"Searches run: {r.get('searches_used', 0)}")
                srcs = r.get("corroborating_sources", "")
                if srcs:
                    st.write(f"Corroborating sources: {srcs}")

with st.sidebar:
    st.header("Filters")

    categories = st.multiselect(
        "Category",
        ["All FMCG", "Food and Beverage", "Personal Care", "Household", "Dairy", "D2C / Startup"],
        default=["All FMCG"],
    )

    regions = st.multiselect(
        "Region",
        ["Global", "India", "US", "Europe", "Southeast Asia"],
        default=["Global"],
    )

    st.divider()
    live = st.button("Run live", type="primary")

    st.divider()
    st.subheader("Pipeline")
    st.write(
        "1. Ingest (Google News RSS)\n"
        "2. Dedup (TF-IDF cosine)\n"
        "3. Relevance (keyword gate, then LLM)\n"
        "4. Corroboration (LangGraph agent loop)\n"
        "5. Generate (newsletter)"
    )

if live:
    if not categories:
        st.warning("Select at least one category.")
        st.stop()
    if not regions:
        st.warning("Select at least one region.")
        st.stop()

    log_area = st.empty()
    logs = []

    def progress(msg):
        logs.append(msg)
        log_area.code("\n".join(logs))

    with st.spinner("Running pipeline..."):
        result = run(progress=progress, categories=categories, regions=regions)

    save_cache(result)

    # Clear the verbose live log and tuck it into a collapsed expander so the
    # newsletter and trace tabs sit near the top of the page.
    log_area.empty()
    with st.expander("Run log", expanded=False):
        st.code("\n".join(logs))

    counts = result["counts"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ingested", counts["ingested"])
    c2.metric("Clusters", counts["clusters"])
    c3.metric("Relevant", counts["relevant"])
    c4.metric("Verified", counts["verified"])

    col1, col2 = st.columns(2)
    with open(result["xlsx_path"], "rb") as f:
        col1.download_button("Download newsletter.xlsx", f, file_name="newsletter.xlsx")
    with open(result["raw_csv"], "rb") as f:
        col2.download_button("Download raw_data.csv", f, file_name="raw_data.csv")

    tab_news, tab_trace = st.tabs(["Newsletter", "Agent trace"])
    with tab_news:
        st.markdown(result["markdown"])
    with tab_trace:
        render_trace(result.get("rows", []))

else:
    cache = load_cache()
    if cache:
        counts = cache.get("counts", {})
        if counts:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Ingested", counts.get("ingested", "-"))
            c2.metric("Clusters", counts.get("clusters", "-"))
            c3.metric("Relevant", counts.get("relevant", "-"))
            c4.metric("Verified", counts.get("verified", "-"))
        rows = cache.get("rows", [])
        if rows:
            tab_news, tab_trace = st.tabs(["Newsletter", "Agent trace"])
            with tab_news:
                st.markdown(cache.get("markdown", "_No cached newsletter._"))
            with tab_trace:
                render_trace(rows)
        else:
            st.markdown(cache.get("markdown", "_No cached newsletter._"))
    else:
        st.info("No cached run found. Select filters and press Run live to generate one.")
