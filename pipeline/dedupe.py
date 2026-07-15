"""
Stage 2: Dedup.

The same deal is reported by many outlets. Collapse near-duplicates into one
cluster per event. TF-IDF plus cosine similarity, with a fixed threshold, is
deterministic and needs no API call. The threshold (0.35) is a tunable knob;
raise it to split more aggressively, lower it to merge more. It was set from
sample data: same-deal article pairs scored around 0.42 on title plus summary,
while distinct deals sharing only an acquirer name stayed at or below 0.13, so
0.35 sits in the gap with margin on both sides.

Two passes:
  Pass A: exact match on normalised title (kills verbatim reprints).
  Pass B: near-duplicate merge via TF-IDF cosine over title + summary.

Cluster size (number of outlets in a cluster) is recorded and carried down. It
is a trust signal used later by corroboration, never by relevance.
"""

from __future__ import annotations

import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .state import Article, Cluster

THRESHOLD = 0.35


def _norm(title: str) -> str:
    t = title.lower()
    # Google News appends " - Source"; strip it for exact matching.
    t = re.sub(r"\s+-\s+[^-]+$", "", t)
    t = re.sub(r"[^a-z0-9 ]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def _connected_components(n: int, edges: list[tuple[int, int]]) -> list[list[int]]:
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        parent[find(a)] = find(b)

    for a, b in edges:
        union(a, b)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def dedupe(articles: list[Article], threshold: float = THRESHOLD) -> list[Cluster]:
    if not articles:
        return []

    # Pass A: fold exact title matches first.
    by_title: dict[str, list[Article]] = {}
    for a in articles:
        by_title.setdefault(_norm(a.title), []).append(a)
    reps = [group[0] for group in by_title.values()]
    members = list(by_title.values())

    if len(reps) == 1:
        return [Cluster(articles=members[0], cluster_size=len(members[0]))]

    # Pass B: near-duplicate merge over representatives.
    corpus = [f"{a.title} {a.summary}" for a in reps]
    tfidf = TfidfVectorizer(stop_words="english", max_features=5000).fit_transform(corpus)
    sim = cosine_similarity(tfidf)

    edges = [
        (i, j)
        for i in range(len(reps))
        for j in range(i + 1, len(reps))
        if sim[i, j] >= threshold
    ]

    clusters: list[Cluster] = []
    for comp in _connected_components(len(reps), edges):
        merged: list[Article] = []
        for idx in comp:
            merged.extend(members[idx])
        clusters.append(Cluster(articles=merged, cluster_size=len(merged)))

    # Largest clusters first: the most-reported deals lead the funnel.
    clusters.sort(key=lambda c: c.cluster_size, reverse=True)
    return clusters
