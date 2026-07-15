# FMCG Deal Intelligence

An agentic pipeline that turns public FMCG news into a short newsletter of recent M&A and investment deals. It ingests news, removes duplicates, filters for FMCG deals, verifies each deal with a LangGraph agent, and generates a structured newsletter.

**Live demo:** https://825vtdbmthns99kdrdjegl.streamlit.app/

## Features

- News ingestion from Google News RSS, filterable by category and region.
- Near-duplicate detection with TF-IDF and cosine similarity.
- Two-pass relevance filter: a keyword gate followed by an LLM classifier.
- A LangGraph agent that corroborates each deal and decides when to search for more evidence.
- Newsletter output to Excel and Markdown, plus a raw-data CSV.
- Streamlit UI with a cached demo run, live execution, and an in-app agent decision trace.
- Optional LangSmith tracing.

## Architecture

```
ingest  ->  dedupe  ->  relevance  ->  corroboration  ->  newsletter
```

The linear stages run in plain Python. Corroboration is a LangGraph state machine invoked once per deal, the only stage where the model controls its own flow. See `architecture.png`.

## Installation

```bash
git clone <your-repo-url>
cd fmcg-deal-newsletter
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS or Linux
pip install -r requirements.txt
```

## Configuration

Copy `.env.example` to `.env` and set:

```
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=your-key-here
# OPENAI_BASE_URL=...          # optional, OpenAI-compatible proxy
# ANTHROPIC_API_KEY=...        # if using a Claude model
# TAVILY_API_KEY=...           # optional, enables corroboration search
# LANGCHAIN_TRACING_V2=true    # optional, LangSmith
# LANGCHAIN_API_KEY=...
# LANGCHAIN_PROJECT=fmcg-deal-newsletter
```

## Usage

```bash
streamlit run app.py
```

The app opens on a cached run. Pick a category and region in the sidebar, then click Run live to execute the pipeline. Outputs appear in two tabs, Newsletter and Agent trace, with download buttons for the Excel newsletter and the raw-data CSV.

## Project structure

```
fmcg-deal-newsletter/
├── app.py                  Streamlit front end
├── architecture.png        pipeline diagram
├── requirements.txt
├── pipeline/
│   ├── state.py            shared data records
│   ├── ingest.py           RSS ingestion and query building
│   ├── dedupe.py           TF-IDF cosine clustering
│   ├── relevance.py        keyword gate and LLM classifier
│   ├── corroboration.py    LangGraph agent loop
│   ├── generate.py         newsletter assembly
│   └── runner.py           pipeline orchestration
├── data/cached_run.json    demo cache
└── output/                 generated files
```

## Tech stack

Python, LangGraph, LangChain, scikit-learn, feedparser, Tavily, openpyxl, Streamlit.

## Notes

- Without a Tavily key, corroboration falls back to cluster size alone.
- The pipeline reflects whatever the public feeds return at run time, so output varies by run.
- Keep `.env` out of version control. It is listed in `.gitignore`.
