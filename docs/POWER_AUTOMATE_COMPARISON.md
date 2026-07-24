# Power Automate / Copilot Studio — the documented-only third column

The Würth role names both **n8n and/or Power Automate**. n8n is in this repo as
runnable code; Power Automate is covered here in writing. That split is not a
shortcut — it *is* one of the findings.

## Where Microsoft's agentic story lives (2025)

Agents live mainly in **Copilot Studio**, with **Power Automate flows** acting as
tools/actions the agents invoke. Current capabilities:

- **Autonomous agents** that trigger on events and run multi-step tool sequences.
- A unified **Tools** surface connecting Outlook, SharePoint, SAP, Snowflake,
  custom connectors and Power Automate flows.
- **Agent flows**, **agent-to-agent (A2A)** protocol, and a **computer-use**
  preview that drives apps/websites in a hosted browser.
- **Copilot-credit** analytics for per-run/per-tool cost and ROI.

So the RFQ-intake and enrichment agents in this repo are entirely buildable in
Copilot Studio + Power Automate.

## Why it isn't committed as code

| | n8n | Power Automate / Copilot Studio |
|---|---|---|
| Portable artifact | single JSON, secret-free, in Git | tenant-bound solution `.zip` (Dataverse) |
| Runs from `git clone`? | yes (+ Docker) | no — needs a licensed M365/Power Platform tenant |
| Cost to run the demo | self-host = infra only | premium/per-user or per-flow licensing + Copilot credits |
| Credentials in the export | referenced by name, re-bound on import | tenant-scoped, governed by DLP policies |
| Git diff quality | noisy but reviewable JSON | barely diffable solution package |

A committed Power Automate build would not run for anyone cloning the repo, would
require a paid tenant, and wouldn't diff meaningfully — so it is represented as
this document plus the scorecard column, which is the honest and useful choice.

## What it's genuinely better at

Not a dunk on Power Automate — it wins the **governance & observability** column
(5/5): native Microsoft 365 identity, enterprise DLP, and analytics that a
self-hosted stack has to assemble. If the requirement is "must run inside our
M365 tenant under existing DLP with no new infrastructure," Power Automate /
Copilot Studio is the right answer, and this project would recommend it — which
is the entire point of building a *decision guide* rather than picking a winner.

## The takeaway for the role

The portability/lock-in axis isn't abstract: you can `git clone` this repo and
run the n8n build tonight; you could not do that with a Power Automate export.
That is the trade-off the job asks an intern to reason about, made concrete.
