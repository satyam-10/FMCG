"""
Stage 4: Corroboration. The one agent.

This is the only place the model steers its own control flow, so it is the only
place a LangGraph state machine is used. Everything else in the pipeline is
deterministic Python. The graph is invoked once per relevant deal (per-deal
invocation).

Control flow:

    assess ──(verdict)──> verified   -> END
                        └ needs_search -> search -> assess (loop)
                        └ exhausted    -> END

assess decides:
  1. If the deal already has cluster_size >= CLUSTER_SHORTCUT outlets, it is
     corroborated at ingestion. Mark verified, no search. (Cluster size is a
     truth signal, which is corroboration's job, not relevance's.)
  2. Otherwise ask the model whether the evidence confirms the deal.
     - confirmed        -> verified
     - not confirmed and searches remain -> needs_search
     - not confirmed and search budget spent -> exhausted (committed, flagged)

The hard cap MAX_SEARCHES is the stopping condition. It stops a stubborn deal
from spinning through the API budget in front of a reviewer.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END

from .llm import get_llm
from .search_tool import search
from .state import Cluster, DealState

MAX_SEARCHES = 2
CLUSTER_SHORTCUT = 3  # outlets already reporting => treat as corroborated


class Assessment(BaseModel):
    confirmed: bool = Field(description="Does the available evidence confirm this is a real, announced deal?")
    reason: str = Field(description="One sentence explaining the judgment")


ASSESS_PROMPT = """You verify whether an FMCG deal is real and well-sourced.

Deal under review:
Title: {title}
Details: {details}

Outlets reporting at ingestion: {cluster_size}
Corroborating sources found by search so far:
{corroboration}

Decide whether the evidence confirms this is a real, announced transaction.
Be conservative: if the sourcing is thin or the deal is only rumoured, do not
confirm it.
"""


def _assess_node(state: DealState) -> DealState:
    cluster: Cluster = state["cluster"]

    # Shortcut: many outlets is itself corroboration.
    if cluster.cluster_size >= CLUSTER_SHORTCUT and not state["corroborating_sources"]:
        state["verdict"] = "verified"
        state["reason"] = f"Corroborated by {cluster.cluster_size} outlets at ingestion."
        return state

    llm = get_llm().with_structured_output(Assessment)
    corr = "\n".join(state["corroborating_sources"]) or "(none yet)"
    prompt = ASSESS_PROMPT.format(
        title=cluster.lead().title,
        details=cluster.text()[:1500],
        cluster_size=cluster.cluster_size,
        corroboration=corr,
    )
    result: Assessment = llm.invoke(prompt)

    if result.confirmed:
        state["verdict"] = "verified"
        state["reason"] = result.reason
    elif state["searches_used"] >= MAX_SEARCHES:
        state["verdict"] = "exhausted"
        state["reason"] = f"Low confidence after {state['searches_used']} searches: {result.reason}"
    else:
        state["verdict"] = "needs_search"
        state["reason"] = result.reason
    return state


def _search_node(state: DealState) -> DealState:
    cluster: Cluster = state["cluster"]
    query = f"{cluster.lead().title} deal confirmed"
    results = search(query)
    state["corroborating_sources"].extend(results)
    state["searches_used"] += 1
    return state


def _route(state: DealState) -> str:
    if state["verdict"] in ("verified", "exhausted"):
        return END
    return "search"


def build_corroboration_graph():
    g = StateGraph(DealState)
    g.add_node("assess", _assess_node)
    g.add_node("search", _search_node)
    g.set_entry_point("assess")
    g.add_conditional_edges("assess", _route, {"search": "search", END: END})
    g.add_edge("search", "assess")
    return g.compile()


# Compile once; reuse across deals.
_GRAPH = build_corroboration_graph()


def corroborate(cluster: Cluster) -> Cluster:
    """Invoke the corroboration graph for a single deal."""
    final: DealState = _GRAPH.invoke(
        {
            "cluster": cluster,
            "searches_used": 0,
            "corroborating_sources": [],
            "verdict": "",
            "reason": "",
        }
    )
    cluster.verdict = final["verdict"]
    cluster.corroboration_reason = final["reason"]
    cluster.corroborating_sources = final["corroborating_sources"]
    cluster.searches_used = final["searches_used"]
    return cluster
