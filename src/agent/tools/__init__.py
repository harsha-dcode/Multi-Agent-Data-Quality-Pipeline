"""Build the in-process MCP server with all data-agent tools.

create_sdk_mcp_server runs an MCP server inside the Python process —
no separate process, no socket, just function calls. The agent sees
tools as `mcp__data_agent__<tool_name>`.
"""
from __future__ import annotations

from claude_agent_sdk import create_sdk_mcp_server

from agent.workspace import Workspace
from agent.tools.extract_csv import make_extract_csv_tool
from agent.tools.profile import make_profile_tool
from agent.tools.clean import make_clean_tool
from agent.tools.correct_dates import make_correct_dates_tool
from agent.tools.impute import make_impute_tool
from agent.tools.report import make_report_tool
from agent.tools.finalize import make_finalize_tool


SERVER_NAME = "data_agent"


def build_mcp_server(ws: Workspace):
    return create_sdk_mcp_server(
        name=SERVER_NAME,
        version="0.1.0",
        tools=[
            make_extract_csv_tool(ws.landing),
            make_profile_tool(ws.landing, ws.profiled),
            make_clean_tool(ws.landing, ws.cleaned),
            make_correct_dates_tool(ws.cleaned),
            make_impute_tool(ws.cleaned),
            make_report_tool(ws.final),
            make_finalize_tool(ws.cleaned, ws.final),
        ],
    )


def allowed_tool_names() -> list[str]:
    """The fully-qualified tool names allowed_tools needs."""
    return [
        f"mcp__{SERVER_NAME}__extract_csv",
        f"mcp__{SERVER_NAME}__profile_data",
        f"mcp__{SERVER_NAME}__clean_data",
        f"mcp__{SERVER_NAME}__correct_dates",
        f"mcp__{SERVER_NAME}__impute_data",
        f"mcp__{SERVER_NAME}__write_report",
        f"mcp__{SERVER_NAME}__finalize",
    ]
