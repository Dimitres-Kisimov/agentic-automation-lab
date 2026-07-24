# Use cases

Two B2B-distribution automations chosen because they are genuinely *agentic*
(the model must decide, in a loop, which tools to call and how many times) and
directly relevant to an industrial distributor like Würth.

## 1. RFQ / order-email intake → quote  (flagship)

**Problem.** A distributor receives thousands of unstructured RFQ/order emails.
Each has to be read, every line item matched to a SKU, stock and price checked,
and a quote written — today, by hand.

**The agent.**

```
parse_email  →  lookup_sku (× N items)  →  check_stock (× N)  →  draft_quote  →  summary
```

Why it's agentic, not a pipeline: the number of `lookup_sku` / `check_stock`
calls depends on how many items the email contains, and off-catalog items branch
to human review. Control flow is decided at runtime.

**Proof (real run, mock provider):**

```
$ python -m agentic_lab rfq_intake
  -> parse_email(...)              customer + 5 line items
  -> lookup_sku(...) × 5           resolved to SKUs with prices
  -> check_stock(...) × 5          availability + lead time
  -> draft_quote(...)              Quote Q-15325, total 911.44 EUR
RESULT: Quote Q-15325 drafted for procurement@acme-bau.de: 5 line items, 911.44 EUR excl. VAT.
METRICS: 13 steps, 12 tool calls, answered
```

A second sample (`data/sample_emails/rfq_02.txt`) contains a deliberately
off-catalog item ("titanium coated left-handed drill bit"); the agent flags it
for manual review instead of quoting a wrong SKU.

## 2. Product-data enrichment  (secondary)

**Problem.** Supplier product records arrive messy and incomplete; the catalog
(PIM) needs clean, categorised, validated entries.

**The agent.**

```
classify_category  →  normalize_fields  →  validate_record  →  ready? / needs-review
```

**Proof (real run):**

```
$ python -m agentic_lab product_enrichment
  -> classify_category(...)   -> fasteners
  -> normalize_fields(...)    -> name trimmed, uom "pieces"→"PCS", "0,89 EUR"→0.89
  -> validate_record(...)     -> valid
RESULT: Record is catalog-ready (category: fasteners).
```

## Stretch (documented, not built): procurement / reorder triage

Detect a below-threshold SKU → verify pricing → decide draft-PO vs open-RFQ vs
escalate-to-human (human-in-the-loop). A natural next agent, and the clearest
place to demonstrate n8n's built-in approval nodes vs. a full-code approval gate.

## Data

`data/product_catalog.csv` — 24 realistic distributor SKUs across fasteners,
power tools, abrasives, chemicals, PPE and hand tools, with price, stock and
lead time. Small enough to read, rich enough to make the matching non-trivial.
