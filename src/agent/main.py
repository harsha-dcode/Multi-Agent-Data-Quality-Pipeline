"""Entry point: drive the agent loop end-to-end.

Usage:
    python -m agent.main --brief "Why did Q4 revenue drop?" --csv data.csv
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from agent.config import Config
from agent.tools import allowed_tool_names, build_mcp_server
from agent.workspace import Workspace


def load_system_prompt() -> str:
    here = Path(__file__).resolve().parent
    return (here / "prompts" / "system.md").read_text(encoding="utf-8")


def build_user_message(brief: str) -> str:
    return (
        f"# Analysis Brief\n{brief}\n\n"
        f"# Available data\n"
        f"A file `input.csv` has been staged in the landing zone of the workspace.\n\n"
        f"# Your job\n"
        f"Run the full pipeline: extract_csv -> profile_data -> clean_data -> "
        f"write_report -> finalize. At each stage, reason about what you see and "
        f"decide what to do next. Justify your cleaning decisions in the final report."
    )


async def run(brief: str, csv_path: Path, config: Config) -> int:
    config.apply_to_env()

    ws = Workspace(root=config.workspace_root)
    ws.reset()
    staged = ws.stage_input(csv_path)
    print(f"[setup] staged {csv_path} -> {staged}")
    print(f"[setup] model: {config.model}")

    server = build_mcp_server(ws)

    options = ClaudeAgentOptions(
        model=config.model,
        system_prompt=load_system_prompt(),
        mcp_servers={"data_agent": server},
        allowed_tools=allowed_tool_names(),
        permission_mode=config.permission_mode,
        max_turns=config.max_turns,
        cwd=str(ws.root.resolve()),
    )

    print("\n" + "=" * 70)
    print(f"BRIEF: {brief}")
    print("=" * 70 + "\n")

    async with ClaudeSDKClient(options=options) as client:
        await client.query(build_user_message(brief))
        async for message in client.receive_response():
            _print_message(message)

    print(f"\n[done] outputs in: {ws.final.resolve()}")
    return 0


def _print_message(message) -> None:
    """Stream a readable trace of the agent loop to stdout."""
    if isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, TextBlock):
                print(f"\n[agent] {block.text}")
            elif isinstance(block, ToolUseBlock):
                preview = _preview(block.input)
                print(f"  -> {block.name}({preview})")
    elif isinstance(message, UserMessage):
        for block in message.content if isinstance(message.content, list) else []:
            if isinstance(block, ToolResultBlock):
                print(f"  <- tool result ({len(str(block.content))} chars)")
    elif isinstance(message, ResultMessage):
        cost = message.total_cost_usd or 0.0
        dur = message.duration_ms or 0
        print(f"\n[result] turns={message.num_turns}  duration={dur}ms  cost=${cost:.4f}")
    elif isinstance(message, SystemMessage):
        pass


def _preview(d: dict, limit: int = 120) -> str:
    s = ", ".join(f"{k}=...{type(v).__name__}" if isinstance(v, (list, dict)) else f"{k}={v!r}"
                  for k, v in d.items())
    return s if len(s) <= limit else s[: limit - 3] + "..."


def main() -> int:
    parser = argparse.ArgumentParser(description="AI Data Analysis Agent — Phase 1 PoC")
    parser.add_argument("--brief", required=True, help="Analysis brief / business question.")
    parser.add_argument("--csv", required=True, type=Path, help="Path to input CSV.")
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"[error] CSV not found: {args.csv}", file=sys.stderr)
        return 1

    config = Config.from_env()
    return asyncio.run(run(args.brief, args.csv, config))


if __name__ == "__main__":
    sys.exit(main())
