"""tools.py — the concrete tools the agent can call.

These are deterministic, testable functions (no LLM inside a tool — the model
decides WHICH tool and with what arguments; the tool just does the work). The
identical set is exposed to the n8n workflow as a "Call Full-Code Tool" HTTP
endpoint (see tool_server.py), so the low-code and full-code builds share one
tool implementation — the fairest possible A/B for the benchmark.

Two use-case families:
  RFQ intake      : parse_email, lookup_sku, check_stock, draft_quote
  Product enrich  : normalize_fields, classify_category, validate_record

Author: Dimitres Kisimov.
"""
from __future__ import annotations

import re
from typing import Any

from . import catalog

# --------------------------------------------------------------------------- #
# RFQ / order-email intake tools
# --------------------------------------------------------------------------- #
_QTY_LINE = re.compile(
    r"^\s*(?:[-*•]\s*)?"                 # optional bullet
    r"(?:(?P<q1>\d+)\s*(?:x|pcs|pieces|stk|stück|units)?\s+(?P<d1>.+?)"   # "10 x M8 bolts"
    r"|(?P<d2>.+?)\s*[-–:]\s*(?:qty\s*)?(?P<q2>\d+)\s*(?:pcs|units|stk)?)"  # "M8 bolts - 10"
    r"\s*$",
    re.IGNORECASE,
)


def parse_email(raw_email: str) -> dict[str, Any]:
    """Extract the customer and the requested line items from a raw RFQ email.
    Handles 'From:'/'Subject:' headers and both '10 x item' and 'item - 10'
    line styles."""
    customer, subject = None, None
    items: list[dict[str, Any]] = []
    for line in raw_email.splitlines():
        low = line.lower()
        if low.startswith("from:") and customer is None:
            customer = line.split(":", 1)[1].strip()
            continue
        if low.startswith("subject:") and subject is None:
            subject = line.split(":", 1)[1].strip()
            continue
        m = _QTY_LINE.match(line)
        if m:
            qty = m.group("q1") or m.group("q2")
            desc = (m.group("d1") or m.group("d2") or "").strip(" .")
            if qty and desc and not desc.lower().startswith(("hi", "hello", "dear", "regards", "best")):
                items.append({"description": desc, "qty": int(qty)})
    return {"customer": customer or "unknown", "subject": subject,
            "items": items, "n_items": len(items)}


# Below this token-overlap score a "best match" is too weak to trust — the item
# is flagged for human review rather than silently quoted against a wrong SKU.
MATCH_FLOOR = 0.18


def lookup_sku(description: str) -> dict[str, Any]:
    """Resolve a free-text line to the best catalog SKU, or flag it for review
    when no candidate clears the confidence floor."""
    prod, score = catalog.best_match(description)
    if not prod or score < MATCH_FLOOR:
        return {"matched": False, "query": description, "match_score": score,
                "reason": "no confident catalog match"}
    return {"matched": True, "query": description, "match_score": score, **prod.as_dict()}


def check_stock(sku: str, qty: int = 1) -> dict[str, Any]:
    """Availability + lead time for a SKU at a requested quantity."""
    prod = catalog.by_sku(sku)
    if not prod:
        return {"error": f"unknown sku {sku!r}"}
    ok = prod.stock_qty >= qty
    return {
        "sku": sku, "requested": qty, "in_stock": ok,
        "available_now": min(qty, prod.stock_qty),
        "backorder": max(0, qty - prod.stock_qty),
        "lead_time_days": 0 if ok else prod.lead_time_days,
    }


def draft_quote(customer: str, line_items: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a customer quote from resolved line items
    (each: {sku, description, qty, unit_price_eur})."""
    lines, total = [], 0.0
    for li in line_items:
        qty = int(li.get("qty", 1))
        price = float(li.get("unit_price_eur", 0.0))
        line_total = round(qty * price, 2)
        total += line_total
        lines.append({
            "sku": li.get("sku"), "description": li.get("description"),
            "qty": qty, "unit_price_eur": price, "line_total_eur": line_total,
        })
    total = round(total, 2)
    body = [f"Quote for {customer}", "-" * 40]
    for ln in lines:
        body.append(f"{ln['qty']:>4} x {ln['sku'] or '?':<10} {ln['description'][:28]:<28} "
                    f"{ln['line_total_eur']:>10.2f} EUR")
    body += ["-" * 40, f"{'TOTAL':>44}: {total:>10.2f} EUR",
             "Prices excl. VAT. Valid 30 days."]
    return {"quote_id": f"Q-{abs(hash(customer + str(total))) % 100000:05d}",
            "customer": customer, "line_items": lines, "total_eur": total,
            "quote_text": "\n".join(body)}


# --------------------------------------------------------------------------- #
# Product-data enrichment tools
# --------------------------------------------------------------------------- #
_CATEGORY_HINTS = {
    "fasteners": ["bolt", "screw", "nut", "washer", "anchor", "rivet", "thread"],
    "power tools": ["drill", "driver", "grinder", "saw", "impact", "cordless"],
    "abrasives": ["disc", "grinding", "flap", "sanding", "cutting wheel"],
    "chemicals": ["adhesive", "sealant", "lubricant", "cleaner", "spray", "silicone"],
    "ppe": ["glove", "goggle", "helmet", "mask", "ear", "safety"],
    "hand tools": ["wrench", "plier", "hammer", "screwdriver", "spanner", "cutter"],
}
_REQUIRED = ("name", "category", "uom", "unit_price_eur", "brand")


def classify_category(description: str) -> dict[str, Any]:
    """Assign a catalog category from a free-text description via keyword hints."""
    low = (description or "").lower()
    for cat, kws in _CATEGORY_HINTS.items():
        if any(k in low for k in kws):
            return {"category": cat, "confidence": "high",
                    "matched_keyword": next(k for k in kws if k in low)}
    return {"category": "uncategorized", "confidence": "low"}


def normalize_fields(record: dict[str, Any]) -> dict[str, Any]:
    """Standardize a raw product record: trim, title-case name, upper UOM,
    coerce price to float, normalize brand casing."""
    out = dict(record)
    if "name" in out and isinstance(out["name"], str):
        out["name"] = " ".join(out["name"].split()).strip()
    if "uom" in out and isinstance(out["uom"], str):
        u = out["uom"].strip().upper()
        out["uom"] = {"PIECES": "PCS", "PIECE": "PCS", "PC": "PCS",
                      "STK": "PCS", "STUECK": "PCS"}.get(u, u)
    if "brand" in out and isinstance(out["brand"], str):
        out["brand"] = out["brand"].strip().title()
    if "unit_price_eur" in out:
        try:
            out["unit_price_eur"] = round(float(str(out["unit_price_eur"]).replace(",", ".")
                                                .replace("EUR", "").replace("€", "").strip()), 2)
        except (ValueError, TypeError):
            out["unit_price_eur"] = None
    return {"normalized": out}


def validate_record(record: dict[str, Any]) -> dict[str, Any]:
    """Check a record against required fields + basic sanity rules."""
    missing = [f for f in _REQUIRED if not record.get(f)]
    issues: list[str] = []
    price = record.get("unit_price_eur")
    if isinstance(price, (int, float)) and price <= 0:
        issues.append("unit_price_eur must be > 0")
    if record.get("category") == "uncategorized":
        issues.append("category could not be determined")
    return {"valid": not missing and not issues,
            "missing_fields": missing, "issues": issues}
