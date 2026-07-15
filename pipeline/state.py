"""
Shared data structures.

The design principle: one record is attached to each item at ingestion and
carried the whole way down the funnel. By the time an item reaches the
newsletter, its record holds everything needed to explain why it made the cut
and everything the raw-data CSV must contain. Bookkeeping is done once; the raw
data, the provenance trail, and the newsletter fields all fall out of it.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional, TypedDict


@dataclass
class Article:
    """A single ingested news item."""

    title: str
    url: str
    source: str
    published: str
    summary: str = ""

    def text(self) -> str:
        return f"{self.title}. {self.summary}"


@dataclass
class Cluster:
    """
    A candidate deal. One cluster equals one real-world event, assembled from
    one or more near-duplicate articles during dedup.
    """

    articles: list[Article]

    # dedup
    cluster_size: int = 0  # number of outlets reporting; a trust signal for corroboration

    # relevance (Pass 2 verdict)
    is_fmcg: Optional[bool] = None
    is_deal: Optional[bool] = None
    deal_type: Optional[str] = None
    relevance_confidence: Optional[float] = None
    relevance_reason: Optional[str] = None

    # corroboration
    verdict: Optional[str] = None  # "verified" | "exhausted"
    corroboration_reason: Optional[str] = None
    corroborating_sources: list[str] = field(default_factory=list)
    searches_used: int = 0

    def lead(self) -> Article:
        return self.articles[0]

    def text(self) -> str:
        return " ".join(a.text() for a in self.articles)

    def to_row(self) -> dict:
        """Flatten to a single CSV row. This is the carried-down record."""
        lead = self.lead()
        return {
            "title": lead.title,
            "url": lead.url,
            "source": lead.source,
            "published": lead.published,
            "cluster_size": self.cluster_size,
            "is_fmcg": self.is_fmcg,
            "is_deal": self.is_deal,
            "deal_type": self.deal_type,
            "relevance_confidence": self.relevance_confidence,
            "relevance_reason": self.relevance_reason,
            "verdict": self.verdict,
            "corroboration_reason": self.corroboration_reason,
            "corroborating_sources": " | ".join(self.corroborating_sources),
            "searches_used": self.searches_used,
        }


class DealState(TypedDict):
    """
    State for the per-deal corroboration graph. The graph is invoked once per
    relevant deal. This graph IS the agent: everything else in the pipeline is
    deterministic Python.
    """

    cluster: Cluster
    searches_used: int
    corroborating_sources: list[str]
    verdict: str  # "" while pending, then "verified" | "exhausted" | "needs_search"
    reason: str
