"""
Stage 3: Relevance.

Two filters, both required: is it FMCG, and is it a deal. Two passes:

  Pass 1 (keyword gate, free, deterministic): a cluster survives only with a
    deal signal AND an FMCG signal. This is a cost and volume gate, not the
    real judgment. Keyword matching is brittle and is never shipped alone; its
    job is to send ten clusters to the LLM instead of a hundred.

  Pass 2 (structured LLM classification, the real judgment): each survivor gets
    one structured call. FMCG-status and deal-status are judged independently so
    the logic is legible and tunable. The reason field is the transparent
    reasoning the brief asks for and lands in the CSV.

Relevance decides topic fit only. It never touches corroboration, which decides
truth. The two trust signals stay separate.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from .state import Cluster

CONFIDENCE_THRESHOLD = 0.6

DEAL_SIGNALS = [
    "acquire", "acquisition", "buys", "buyout", "merger", "merges", "merge",
    "stake", "majority stake", "minority stake", "raises", "raised",
    "funding round", "series a", "series b", "series c", "invests",
    "investment", "divest", "sells unit", "sells its", "takeover", "deal",
]

FMCG_CATEGORY_SIGNALS = [
    "fmcg", "consumer goods", "packaged food", "packaged goods", "beverage",
    "beverages", "personal care", "household", "cosmetics", "dairy", "snack",
    "snacks", "confectionery", "grocery", "cpg", "consumer staples",
]

FMCG_COMPANY_SEED = [
    "unilever", "nestle", "nestlé", "procter", "p&g", "pepsico", "coca-cola",
    "colgate", "kraft", "heinz", "mondelez", "danone", "reckitt", "kellogg",
    "general mills", "itc", "hindustan unilever", "hul", "britannia", "dabur",
    "marico", "godrej", "nestle india", "l'oreal", "loreal", "kimberly-clark",
    "johnson & johnson", "estee lauder", "diageo", "ab inbev", "heineken",
]


def _has_signal(text: str, signals: list[str]) -> bool:
    t = text.lower()
    return any(s in t for s in signals)


def keyword_gate(cluster: Cluster) -> bool:
    text = cluster.text().lower()
    deal = _has_signal(text, DEAL_SIGNALS)
    fmcg = _has_signal(text, FMCG_CATEGORY_SIGNALS) or _has_signal(text, FMCG_COMPANY_SEED)
    return deal and fmcg


class RelevanceVerdict(BaseModel):
    is_fmcg: bool = Field(description="Does the article concern a fast-moving consumer goods company or category?")
    is_deal: bool = Field(description="Does the article report an M&A, stake, or investment transaction?")
    deal_type: str = Field(description="One of: acquisition, merger, stake, funding, divestiture, none")
    confidence: float = Field(description="0.0 to 1.0 confidence in the two booleans above")
    reason: str = Field(description="One sentence grounding the verdict in specifics from the text")


CLASSIFY_PROMPT = """You classify news articles for an FMCG deal newsletter.

Definitions (use these exactly):
- FMCG (fast-moving consumer goods): companies selling food, beverages, personal
  care, household products, cosmetics, dairy, snacks, or packaged consumer goods.
  Software, fintech, industrials, and services are NOT FMCG.
- Deal: an announced transaction or ownership change. Acquisitions, mergers,
  stake purchases or sales, funding rounds, and divestitures count. Earnings
  reports, product launches, and leadership changes do NOT count, even for an
  FMCG company.

Judge FMCG-status and deal-status independently. An article passes only if both
are true.

Article:
Title: {title}
Summary: {summary}
"""


def classify(cluster: Cluster) -> RelevanceVerdict:
    from .llm import get_llm

    llm = get_llm().with_structured_output(RelevanceVerdict)
    lead = cluster.lead()
    prompt = CLASSIFY_PROMPT.format(title=lead.title, summary=cluster.text()[:1500])
    return llm.invoke(prompt)


def relevance_filter(clusters: list[Cluster]) -> list[Cluster]:
    survivors: list[Cluster] = []
    for c in clusters:
        if not keyword_gate(c):
            continue  # dropped before it costs a token
        verdict = classify(c)
        c.is_fmcg = verdict.is_fmcg
        c.is_deal = verdict.is_deal
        c.deal_type = verdict.deal_type
        c.relevance_confidence = verdict.confidence
        c.relevance_reason = verdict.reason
        if verdict.is_fmcg and verdict.is_deal and verdict.confidence >= CONFIDENCE_THRESHOLD:
            survivors.append(c)
    return survivors
