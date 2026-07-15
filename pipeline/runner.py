"""
The runner. Wires the funnel end to end:

    ingest -> dedupe -> relevance_filter -> [corroboration per deal] -> generate

The linear stages run in plain Python. The corroboration graph is invoked once
per relevant deal. Every cluster's carried-down record is written to
output/raw_data.csv, verified or not, so the raw data shows the whole journey.
"""

from __future__ import annotations

import csv
import json
import os

from .ingest import ingest
from .dedupe import dedupe
from .relevance import relevance_filter
from .corroboration import corroborate
from .generate import generate
from .state import Cluster


def _write_raw_csv(clusters: list[Cluster], out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "raw_data.csv")
    rows = [c.to_row() for c in clusters]
    fields = list(rows[0].keys()) if rows else []
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return path


def run(
    out_dir: str = "output",
    progress=None,
    categories: list[str] | None = None,
    regions: list[str] | None = None,
) -> dict:
    def log(msg):
        if progress:
            progress(msg)

    cat_label = ", ".join(categories or ["All FMCG"])
    reg_label = ", ".join(regions or ["Global"])
    log(f"Ingesting from Google News RSS ({cat_label} | {reg_label})...")
    articles = ingest(categories=categories, regions=regions)
    log(f"Ingested {len(articles)} articles.")

    log("Deduplicating...")
    clusters = dedupe(articles)
    log(f"{len(clusters)} candidate deals after dedup.")

    log("Scoring relevance (two-pass)...")
    relevant = relevance_filter(clusters)
    log(f"{len(relevant)} clusters passed the FMCG-and-deal filter.")

    log("Corroborating (agent loop, per deal)...")
    verified: list[Cluster] = []
    for c in relevant:
        corroborate(c)
        verified.append(c)
    log(f"{sum(1 for c in verified if c.verdict == 'verified')} deals verified.")

    # Raw data covers every cluster, showing the full journey.
    for c in clusters:
        if c not in relevant:
            c.verdict = c.verdict or "dropped_at_relevance"
    raw_path = _write_raw_csv(clusters, out_dir)

    log("Writing newsletter...")
    out = generate(verified, out_dir)
    out["raw_csv"] = raw_path
    out["rows"] = [c.to_row() for c in clusters]  # per-deal trace records
    out["counts"] = {
        "ingested": len(articles),
        "clusters": len(clusters),
        "relevant": len(relevant),
        "verified": sum(1 for c in verified if c.verdict == "verified"),
    }
    return out


def save_cache(result: dict, path: str = "data/cached_run.json") -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {
        "markdown": result.get("markdown", ""),
        "counts": result.get("counts", {}),
        "rows": result.get("rows", []),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def load_cache(path: str = "data/cached_run.json") -> dict | None:
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)