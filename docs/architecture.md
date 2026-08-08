# Architecture Deep-Dive

## The Hybrid Intelligence Pattern

The core architectural principle of this project:

> **Claude handles judgment. Python handles execution.**

This is not a code-generation approach where Claude writes Python that then runs. Instead:

1. Claude **reads** structured tool outputs (JSON profiles, log strings)
2. Claude **decides** what operations to apply based on the data and the brief
3. Python **executes** those operations deterministically
4. Claude **reads** the results and decides next steps

This pattern has several advantages:
- **Reproducibility**: given the same profile + brief, Claude's decisions are consistent
- **Debuggability**: every decision maps to a tool call you can inspect
- **Trustworthiness**: Claude cannot invent statistics — every number came from a tool
- **Extensibility**: adding a new cleaning operation is just adding a handler in `_apply_op()`

## MCP Server Architecture

The 7 tool functions are exposed to Claude via an **in-process MCP server**:

```python
server = create_sdk_mcp_server(
    name="data_agent",
    version="0.1.0",
    tools=[make_extract_csv_tool(ws.landing), ...]
)
```

"In-process" means there's no separate MCP server process, no TCP socket, no subprocess. The tools run in the same Python process as the agent loop. This makes the setup simple (no Docker, no port management) while still conforming to the MCP protocol that Claude Agent SDK expects.

Claude sees the tools as `mcp__data_agent__extract_csv`, `mcp__data_agent__profile_data`, etc.

## Tool Factory Pattern

Each tool is created via a factory function that captures workspace paths via closure:

```python
def make_extract_csv_tool(landing_dir: Path):
    @tool("extract_csv", description, schema)
    async def extract_csv(args): ...
    return extract_csv
```

This means the tool function itself has no global state — the paths it reads from and writes to are bound at construction time. The same tool code can be used with different workspace layouts.

## Workspace as Pipeline State

The workspace folders serve as the pipeline's state:

```
00_landing/    → extract_csv writes here; profile_data reads from here
10_profiled/   → profile_data writes profile.json here
20_cleaned/    → clean_data / correct_dates / impute_data write/read cleaned.parquet here
99_final/      → write_report / finalize write here
```

Each `clean_data` call reads from `cleaned.parquet` if it exists, otherwise from `extracted.parquet`. This means pass 1 and pass 2 of cleaning both work correctly without any special handling.

## Agent Loop

The agent loop is driven by the Claude Agent SDK:

```python
async with ClaudeSDKClient(options=options) as client:
    await client.query(build_user_message(brief))
    async for message in client.receive_response():
        _print_message(message)
```

The SDK handles:
- Sending the initial message with the system prompt
- Routing tool calls to the MCP server
- Collecting tool results and feeding them back to Claude
- Enforcing the `max_turns` limit
- Reporting cost and duration in the `ResultMessage`

## Sub-Agent Ecosystem

The `pipeline-orchestrator.md` agent (Claude Code sub-agent) is a higher-level orchestrator that:
1. Guides users through all 9 stages interactively (with pauses at decision points)
2. Calls the SDK pipeline for stages 4-7 (clean, validate, audit, pre-viz)
3. Hands off to `analytics-expert` for stage 9

The separation exists because:
- The SDK pipeline runs headlessly (no user interaction mid-run)
- The orchestrator adds human-in-the-loop decision points
- Analytics is a different skill set from cleaning

## Anthropic API Integration

The project uses Claude directly via the Anthropic API. This requires:

1. **API key**: `ANTHROPIC_API_KEY` set in your `.env` file
2. **Model**: `claude-sonnet-4-6` (bare model ID, no cloud-provider prefix)

The config applies the API key before constructing the SDK client:

```python
def apply_to_env(self) -> None:
    if self.api_key:
        os.environ["ANTHROPIC_API_KEY"] = self.api_key
```

Get your API key at `console.anthropic.com`.
