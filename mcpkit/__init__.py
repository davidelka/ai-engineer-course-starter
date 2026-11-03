"""mcpkit: Acme's MCP server and client helpers (lesson 17 onward).

Built on the official MCP Python SDK, `mcp` 2.x (MCPServer is the class v1 called FastMCP).

server.py    build_acme_server(): the toolkit tools + search_docs + get_oncall_for_service as MCP tools,
             the corpus documents as acme://docs/{doc_id} resources, two prompts. `python -m mcpkit`.
bridge.py    MCPToolbox / run_mcp_agent: any MCP server's tools inside llmkit's tool loop
             (mcp_tool_to_llmkit, call_result_to_tool_result), plus elicitation callbacks.
auth.py      bearer-token check for Streamable HTTP (SDK TokenVerifier + RFC 9728 metadata).
pinning.py   tool_fingerprint / pin_tools / diff_tool_pins / scan_tool_description: against tool
             poisoning and rug pulls.
oncall.py    get_oncall_for_service() over the Engineering Service Catalog.
wire.py      RawStdio: speak JSON-RPC to a stdio server by hand, to see the protocol.
"""

from .bridge import (HttpTarget, MCPToolbox, call_result_to_tool_result, llm_tool_name, mcp_tool_to_llmkit,
                     run_mcp_agent, scripted_elicitation, terminal_elicitation)
from .oncall import get_oncall_for_service
from .pinning import diff_tool_pins, pin_tools, scan_tool_description, tool_fingerprint
from .server import acme_mcp_registry, build_acme_server

__all__ = ["HttpTarget", "MCPToolbox", "call_result_to_tool_result", "llm_tool_name", "mcp_tool_to_llmkit",
           "run_mcp_agent", "scripted_elicitation", "terminal_elicitation", "get_oncall_for_service",
           "diff_tool_pins", "pin_tools", "scan_tool_description", "tool_fingerprint", "acme_mcp_registry",
           "build_acme_server"]
