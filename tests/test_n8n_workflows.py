"""Structural validation of the n8n workflow JSON — asserts the low-code build is
wired the way the docs claim (an AI Agent fed a chat model + tool nodes). This is
the kind of automated check that low-code platforms usually lack, and is part of
the point the project makes."""
import json
from pathlib import Path

import pytest

N8N = Path(__file__).resolve().parents[1] / "n8n"
WORKFLOWS = sorted(N8N.glob("*.json"))
AGENT_TYPE = "@n8n/n8n-nodes-langchain.agent"
MODEL_PREFIX = "@n8n/n8n-nodes-langchain.lmChat"
TOOL_PREFIX = "@n8n/n8n-nodes-langchain.tool"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_workflow_is_valid_agent_graph(path):
    wf = json.loads(path.read_text(encoding="utf-8"))
    assert wf["nodes"] and "connections" in wf
    types = [n["type"] for n in wf["nodes"]]

    # exactly one agent, one chat model, at least two tools
    assert types.count(AGENT_TYPE) == 1, "need exactly one AI Agent node"
    assert any(t.startswith(MODEL_PREFIX) for t in types), "need a chat model sub-node"
    assert sum(t.startswith(TOOL_PREFIX) for t in types) >= 2, "need >= 2 tool nodes"

    agent_name = next(n["name"] for n in wf["nodes"] if n["type"] == AGENT_TYPE)

    # the model must feed the agent via an ai_languageModel connection
    conns = wf["connections"]
    model_name = next(n["name"] for n in wf["nodes"] if n["type"].startswith(MODEL_PREFIX))
    assert "ai_languageModel" in conns[model_name]
    assert conns[model_name]["ai_languageModel"][0][0]["node"] == agent_name

    # every tool node must feed the agent via an ai_tool connection
    for n in wf["nodes"]:
        if n["type"].startswith(TOOL_PREFIX):
            assert n["name"] in conns and "ai_tool" in conns[n["name"]], \
                f"{n['name']} is not wired as a tool"
            assert conns[n["name"]]["ai_tool"][0][0]["node"] == agent_name

    # exported JSON must not carry secrets (portability / safety claim)
    assert "REBIND_ON_IMPORT" in path.read_text(encoding="utf-8") or \
        all("apiKey" not in json.dumps(n.get("parameters", {})) for n in wf["nodes"])


def test_tools_match_the_python_tool_server():
    """Every HTTP tool the workflows call must exist in the shared tool server."""
    from agentic_lab.tool_server import _TOOLS
    for path in WORKFLOWS:
        wf = json.loads(path.read_text(encoding="utf-8"))
        for n in wf["nodes"]:
            url = n.get("parameters", {}).get("url", "")
            if url:
                endpoint = url.rstrip("/").rsplit("/", 1)[-1]
                assert endpoint in _TOOLS, f"{path.name}: /{endpoint} not in tool server"
