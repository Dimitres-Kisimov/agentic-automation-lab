"""catalog.py — a tiny in-memory product catalog over data/product_catalog.csv.

Stands in for the ERP/PIM a distributor like Würth would expose to the agent.
Pure stdlib: loads the CSV and offers SKU lookup + a deterministic token-overlap
fuzzy match (so "M8 hex bolt zinc" resolves to the right SKU without an LLM or a
vector DB — keeping the demo reproducible and dependency-free).

Author: Dimitres Kisimov.
"""
from __future__ import annotations

import csv
import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_DATA = Path(__file__).resolve().parents[2] / "data" / "product_catalog.csv"
_WORD = re.compile(r"[a-z0-9]+")


@dataclass
class Product:
    sku: str
    name: str
    description: str
    category: str
    brand: str
    uom: str
    unit_price_eur: float
    stock_qty: int
    lead_time_days: int

    def as_dict(self) -> dict:
        return {
            "sku": self.sku, "name": self.name, "category": self.category,
            "brand": self.brand, "uom": self.uom,
            "unit_price_eur": self.unit_price_eur, "stock_qty": self.stock_qty,
            "lead_time_days": self.lead_time_days,
        }


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall((text or "").lower()))


@lru_cache(maxsize=1)
def load(path: str | None = None) -> tuple[Product, ...]:
    p = Path(path) if path else _DATA
    rows: list[Product] = []
    with p.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            rows.append(Product(
                sku=r["sku"].strip(), name=r["name"].strip(),
                description=r["description"].strip(), category=r["category"].strip(),
                brand=r["brand"].strip(), uom=r["uom"].strip(),
                unit_price_eur=float(r["unit_price_eur"]),
                stock_qty=int(r["stock_qty"]), lead_time_days=int(r["lead_time_days"]),
            ))
    return tuple(rows)


def by_sku(sku: str, path: str | None = None) -> Product | None:
    sku = (sku or "").strip().upper()
    for p in load(path):
        if p.sku.upper() == sku:
            return p
    return None


def best_match(query: str, path: str | None = None) -> tuple[Product | None, float]:
    """Return (product, score in 0..1) for the closest catalog item by
    token overlap over name+description+category. Deterministic, no ML."""
    q = _tokens(query)
    if not q:
        return None, 0.0
    best, best_score = None, 0.0
    for p in load(path):
        hay = _tokens(f"{p.name} {p.description} {p.category} {p.brand}")
        if not hay:
            continue
        overlap = len(q & hay) / len(q | hay)     # Jaccard
        if overlap > best_score:
            best, best_score = p, overlap
    return best, round(best_score, 3)


def search(query: str, top_k: int = 3, path: str | None = None) -> list[dict]:
    q = _tokens(query)
    scored: list[tuple[float, Product]] = []
    for p in load(path):
        hay = _tokens(f"{p.name} {p.description} {p.category} {p.brand}")
        s = len(q & hay) / len(q | hay) if (q and hay) else 0.0
        if s > 0:
            scored.append((s, p))
    scored.sort(key=lambda t: -t[0])
    return [dict(p.as_dict(), match_score=round(s, 3)) for s, p in scored[:top_k]]


def categories(path: str | None = None) -> Iterable[str]:
    return sorted({p.category for p in load(path)})
