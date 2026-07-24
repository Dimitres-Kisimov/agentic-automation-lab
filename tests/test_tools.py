"""Unit tests for the business tools — the layer both the full-code agent and the
n8n workflow call, so these guard the shared behaviour."""
from agentic_lab import tools


def test_parse_email_both_line_styles():
    email = ("From: buyer@x.de\nSubject: order\n\n"
             "10 x M8 bolts\nsilicone sealant - 5\nBest regards")
    out = tools.parse_email(email)
    assert out["customer"] == "buyer@x.de"
    assert {"description": "M8 bolts", "qty": 10} in out["items"]
    assert {"description": "silicone sealant", "qty": 5} in out["items"]
    assert out["n_items"] == 2


def test_lookup_sku_confident_match():
    r = tools.lookup_sku("M8x40 hex bolts zinc")
    assert r["matched"] is True
    assert r["sku"] == "FAS-0008-40"
    assert r["unit_price_eur"] > 0


def test_lookup_sku_below_floor_is_flagged():
    r = tools.lookup_sku("titanium coated left-handed drill bit 3mm")
    assert r["matched"] is False
    assert r["match_score"] < tools.MATCH_FLOOR


def test_check_stock_in_and_backorder():
    ok = tools.check_stock("FAS-0008-40", 10)
    assert ok["in_stock"] is True and ok["backorder"] == 0
    short = tools.check_stock("PWR-IMP-18", 10_000)
    assert short["in_stock"] is False and short["backorder"] > 0
    assert short["lead_time_days"] > 0


def test_draft_quote_totals():
    q = tools.draft_quote("ACME", [
        {"sku": "FAS-0008-40", "description": "bolt", "qty": 10, "unit_price_eur": 0.89},
        {"sku": "PPE-GLV-CR-L", "description": "gloves", "qty": 20, "unit_price_eur": 3.10},
    ])
    assert q["total_eur"] == round(10 * 0.89 + 20 * 3.10, 2)
    assert q["quote_id"].startswith("Q-")
    assert "TOTAL" in q["quote_text"]


def test_classify_category():
    assert tools.classify_category("M8 hex bolt zinc")["category"] == "fasteners"
    assert tools.classify_category("cordless impact driver")["category"] == "power tools"
    assert tools.classify_category("cut-resistant gloves")["category"] == "ppe"
    assert tools.classify_category("mystery widget")["category"] == "uncategorized"


def test_normalize_fields_units_and_price():
    out = tools.normalize_fields({"name": "  m8   bolt ", "uom": "pieces",
                                  "brand": "wuerth", "unit_price_eur": "0,89 EUR"})["normalized"]
    assert out["name"] == "m8 bolt"
    assert out["uom"] == "PCS"
    assert out["brand"] == "Wuerth"
    assert out["unit_price_eur"] == 0.89


def test_validate_record():
    good = tools.validate_record({"name": "x", "category": "fasteners", "uom": "PCS",
                                  "unit_price_eur": 1.0, "brand": "Würth"})
    assert good["valid"] is True
    bad = tools.validate_record({"name": "x", "category": "uncategorized", "uom": "PCS",
                                 "unit_price_eur": 0, "brand": "Würth"})
    assert bad["valid"] is False
    assert "unit_price_eur must be > 0" in bad["issues"]
