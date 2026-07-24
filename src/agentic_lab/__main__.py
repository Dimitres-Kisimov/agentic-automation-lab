"""CLI — run a use case from the terminal, with a live trace of the agent's
tool-use loop. Mock provider by default (no key); pass --provider anthropic to
run against Claude.

    python -m agentic_lab rfq_intake
    python -m agentic_lab product_enrichment --provider anthropic
    python -m agentic_lab rfq_intake --input path/to/email.txt --quiet

Author: Dimitres Kisimov.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .llm import make_provider
from .usecases import REGISTRY


def main(argv: list[str] | None = None) -> int:
    try:  # make the trace safe on Windows' legacy cp1252 console
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(prog="agentic_lab", description=__doc__)
    ap.add_argument("usecase", choices=sorted(REGISTRY), help="which agent to run")
    ap.add_argument("--provider", default="mock", choices=["mock", "anthropic"])
    ap.add_argument("--input", help="path to an input file (else the built-in demo input)")
    ap.add_argument("--quiet", action="store_true", help="hide the step-by-step trace")
    a = ap.parse_args(argv)

    uc = REGISTRY[a.usecase]
    user_input = Path(a.input).read_text(encoding="utf-8") if a.input else uc.demo_input()

    if a.provider == "anthropic":
        agent = uc.build_agent(provider=make_provider("anthropic"))
    else:
        agent = uc.build_agent()  # each use case supplies its mock policy

    def trace(event: str, payload) -> None:
        if a.quiet:
            return
        if event == "tool_call":
            print(f"  -> {payload['name']}({_short(payload['arguments'])})")
        elif event == "tool_result":
            print(f"     = {_short(payload['result'])}")

    print(f"# {a.usecase}  (provider={a.provider})\n")
    print("INPUT:\n" + "\n".join("  " + ln for ln in user_input.strip().splitlines()) + "\n")
    print("AGENT TRACE:")
    run = agent.run(user_input, on_event=trace)
    print("\nRESULT:\n  " + run.final.replace("\n", "\n  "))
    print("\nMETRICS:", run.summary())
    return 0


def _short(obj, n: int = 90) -> str:
    s = str(obj)
    return s if len(s) <= n else s[: n - 1] + "…"


if __name__ == "__main__":
    sys.exit(main())
