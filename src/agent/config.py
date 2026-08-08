"""Configuration loaded from environment variables.

All knobs live here so main.py stays clean and the rest of the
codebase never touches os.environ directly.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


# Load .env on import — harmless if the file is absent.
load_dotenv()


@dataclass
class Config:
    # --- Anthropic API ---
    api_key: str = ""
    model: str = "claude-sonnet-4-6"

    # --- Agent runtime ---
    max_turns: int = 40
    permission_mode: str = "bypassPermissions"

    # --- Workspace ---
    workspace_root: Path = Path("workspace")

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            model=os.getenv("AGENT_MODEL", "claude-sonnet-4-6"),
            max_turns=int(os.getenv("AGENT_MAX_TURNS", "40")),
            workspace_root=Path(os.getenv("WORKSPACE_ROOT", "workspace")),
        )

    def apply_to_env(self) -> None:
        """Set the env vars the Claude Agent SDK expects for direct API access."""
        if self.api_key:
            os.environ["ANTHROPIC_API_KEY"] = self.api_key
        # Ensure Bedrock is disabled
        os.environ.pop("CLAUDE_CODE_USE_BEDROCK", None)
        os.environ.pop("AWS_REGION", None)
