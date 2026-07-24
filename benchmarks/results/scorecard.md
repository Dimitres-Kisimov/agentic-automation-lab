# Low-code vs Full-code — scorecard

Scores 1–5 (higher = better). Judgement ratings from the rubric in `docs/EVALUATION_FRAMEWORK.md`; the runtime numbers in `metrics.json` are measured.

| Dimension | n8n (low-code) | Python (full-code) | Power Automate (doc-only) |
|---|:--:|:--:|:--:|
| Time-to-first-demo | 5 | 3 | 4 |
| Maintainability at scale | 2 | 5 | 2 |
| Testability & CI | 2 | 5 | 1 |
| Cost / TCO (self-host) | 4 | 4 | 2 |
| Latency control | 3 | 5 | 3 |
| Governance & observability | 4 | 3 | 5 |
| Extensibility | 3 | 5 | 2 |
| Portability / no lock-in | 4 | 5 | 1 |
| Versioning (Git diff quality) | 3 | 5 | 1 |
| **Average** | **3.33** | **4.44** | **2.33** |

### Why each score

- **Time-to-first-demo** — Visual wiring is fastest to a working agent; full-code pays boilerplate up front.
- **Maintainability at scale** — Literature flags weak fault-tolerance / tight platform coupling for low-code.
- **Testability & CI** — Full-code has native pytest + GitHub Actions; low-code unit testing is unusual.
- **Cost / TCO (self-host)** — Self-hosted n8n avoids seat fees; PA adds premium licensing + Copilot credits.
- **Latency control** — Full-code can cache/short-circuit calls; platforms add orchestration hops.
- **Governance & observability** — n8n ships run logs; PA has enterprise DLP/analytics; full-code is DIY.
- **Extensibility** — Code nodes help, but full-code is unbounded; PA is most constrained.
- **Portability / no lock-in** — Open-source n8n JSON runs from a clone; PA flows are tenant-bound.
- **Versioning (Git diff quality)** — Python diffs cleanly; workflow JSON diffs are noisy; PA solutions barely diff.
