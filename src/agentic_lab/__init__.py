"""agentic_lab — a full-code agentic automation toolkit, built to be benchmarked
head-to-head against the same use cases implemented low-code in n8n.

Public surface:
    from agentic_lab.usecases import rfq_intake, product_enrichment
    agent = rfq_intake.build_agent()          # mock provider by default
    run = agent.run(rfq_intake.demo_input())
    print(run.final, run.summary())

Author: Dimitres Kisimov. Proprietary — all rights reserved (see LICENSE).
"""
from .agent import Agent, AgentRun, ToolRegistry
from .llm import make_provider

__version__ = "0.1.0"
__all__ = ["Agent", "AgentRun", "ToolRegistry", "make_provider"]
