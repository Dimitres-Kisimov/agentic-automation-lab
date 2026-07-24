# Business case — RFQ / order-email intake agent

*A one-page case for putting the flagship RFQ agent in front of an inside-sales
team. The scenario and the company are invented for illustration; the agent
behaviour and the runtime numbers it cites are the ones this repo actually
measures. Cost figures are estimates, and I've labelled them as such.*

## Situation

**Nordwerk Industrievertrieb GmbH** (fictional) is a mid-size industrial
distributor near Heilbronn — fasteners, power tools, abrasives, PPE — with a
catalogue of a few thousand SKUs. Its twelve-person inside-sales desk lives in
the inbox: customers email unstructured RFQs and repeat orders ("please quote 10x
M8x40 hex bolts zinc, 4x cordless impact driver 18V …"), and a rep reads each one,
matches every line to a SKU in the ERP, checks stock and price, and types back a
quote. Volume runs at roughly **2,000 RFQ/order emails a week**.

## Problem (quantified)

Every quote is hand-built. The arithmetic, with assumptions stated:

| Assumption | Value |
|---|---|
| RFQ/order emails per week | 2,000 |
| Manual handling per email (read → match SKUs → check stock/price → draft) | ~10 min |
| Working weeks per year | 52 |
| Fully-loaded inside-sales labour cost (salary + overhead) | €45 / hour |

- **Time:** 2,000 × 10 min = **333 hours/week** ≈ **17,300 hours/year** spent
  turning emails into quotes by hand.
- **Cost:** 17,300 h × €45/h ≈ **€780,000/year** of inside-sales time consumed by
  manual quoting.
- **Errors:** hand-keying SKUs and prices carries a transcription error rate I'll
  assume at ~3% of quoted lines. On pricing, an error is money — under- or
  over-quoting, then rework and goodwill to fix it.
- **Turnaround / SLA:** quotes come back in hours or next-day when the desk is
  busy; every hour of delay is a chance for the customer to buy elsewhere.

## Solution

The repo's flagship agent automates the draft. It is a from-scratch LLM tool-use
loop that, given one RFQ email, **decides its own steps**: parse the email,
resolve **each** line item to a catalogue SKU, check stock for each, and draft a
priced quote. Off-catalogue items ("titanium-coated left-handed drill bit") are
**flagged for human review, never guessed** — so the desk still owns pricing, but
starts from a finished draft instead of a blank inbox. The tool logic is tested
Python; the same functions can sit behind an n8n operator front-door that logs
every run (the hybrid this repo's [decision guide](DECISION_GUIDE.md) recommends).

## Impact / ROI

Tied to the repo's measured behaviour: on a real 5-line email the agent runs
**12 tool calls across 13 steps** and returns a drafted quote
(`benchmarks/results/metrics.json`). With a live model that is a
**seconds-long** draft; the ~10-minute manual step becomes a **review-and-send**.

Conservatively — assuming a rep still reviews and approves **every** draft in
~2 minutes rather than trusting straight-through automation:

- **Time cut per quote:** ~10 min → ~2 min = **80% reduction**.
- **Hours saved:** ≈ **13,900 hours/year**.
- **Cost saved:** ≈ **€625,000/year** at €45/h (estimate).
- **Errors:** deterministic SKU lookup removes transcription errors on matched
  lines; off-catalogue lines are surfaced, not silently mis-quoted.
- **Turnaround:** drafting drops from minutes to seconds, so the desk clears the
  queue faster and quotes go out sooner.

**Payback.** Treating a one-off build-and-integration effort at an estimated
~€100,000 (engineering + ERP/email wiring), the ~€625k/year saving pays it back
in **under two months**. Even halve the saving for a cautious pilot and payback is
still inside a quarter.

## Stakeholders & use case

- **Inside-sales reps** — primary users; review and send agent-drafted quotes.
- **Sales-ops / team lead** — owns the operator front-door and watches run logs.
- **IT / engineering** — owns the tested tool layer and the model integration.
- **Finance** — cares about the pricing-error reduction and the labour saving.

Daily workflow:

1. An RFQ/order email lands in the shared inbox.
2. The agent parses it and resolves each line to a SKU, checking stock and price.
3. Off-catalogue or ambiguous lines are flagged for the rep.
4. The agent drafts a priced quote; the rep reviews (~2 min) and sends.
5. Every run is logged for audit and for measuring live cost and latency.

## Deliverable

Leadership receives **`deliverables/executive_onepager.pdf`** — a circulable
one-page summary of the situation, the quantified problem, the solution, and the
ROI above — backed by this business case, the
[decision guide](DECISION_GUIDE.md), and the measured
[scorecard](../benchmarks/results/scorecard.md).
