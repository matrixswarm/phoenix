# Authored by Daniel F MacDonald and ChatGPT-5 aka The Generals
"""
Module: Agent Root Selector

This module provides utilities to handle the discovery and verification of agent source files within a normalized project structure.
It supports multiple programming languages and is designed to work with agent directories such as `/agents` or `/agents/<lang>_core/`.

The module includes methods to resolve the base agent directory, locate specific agent source files, and validate all necessary
agent sources within a directive tree.

---

Classes:
    - AgentRootSelector: Provides static methods for resolving and validating agent source paths.

Constants:
    - LANG_EXT_MAP: A dictionary mapping programming languages to their standard file extensions.

---

class AgentRootSelector:
"""

from pathlib import Path

LANG_EXT_MAP = {
    "python": "py",
    "go": "go",
    "bash": "sh",
    "rust": "rs",
    "javascript": "js",
    "cpp": "cpp",
    "c": "c"
}


class AgentRootSelector:
    """
    Handles agent source discovery across multiple language cores.
    Automatically normalizes /agents, /agents/<lang>_core/, or project-root paths.
    """

    @staticmethod
    def resolve_agents_root(base_dir: str) -> Path:
        """
        Normalize and validate the agents root directory from any input.
        Accepts:
            - Project root containing /agents/
            - /agents/ itself
            - /agents/<lang>_core/
        Returns:
            Path to the /agents directory.
        """
        base = Path(base_dir).resolve()
        if not base.exists():
            raise FileNotFoundError(f"[CLOWN-CAR] Invalid base directory: {base_dir}")

        # Directly inside <lang>_core?
        if base.name.endswith("_core"):
            return base.parent

        # Inside /agents?
        if base.name.lower() == "agents":
            return base

        # Project root? (has /agents/)
        if (base / "agents").exists():
            return base / "agents"

        # Already inside /agents/<lang>_core/
        if "agents" in [p.name.lower() for p in base.parents]:
            for parent in base.parents:
                if parent.name.lower() == "agents":
                    return parent

        raise FileNotFoundError(f"[CLOWN-CAR] Could not resolve agents root from: {base_dir}")

    @staticmethod
    def find_agent_source(agent_name: str, base_dir: str, lang: str = "python") -> str:
        """
        Locate a specific agent source file (e.g., matrix_core/gatekeeper/gatekeeper.py)
        under /agents.
        """
        agents_root = AgentRootSelector.resolve_agents_root(base_dir)
        ext = LANG_EXT_MAP.get(lang.lower(), "py")

        for file in agents_root.rglob(f"{agent_name}.{ext}"):
            if file.is_file():
                return str(file.resolve())

        print(f"[CLOWN-CAR][WARN] Not found: {agent_name} ({lang}) under {agents_root}")
        return ""

    @staticmethod
    def verify_all_sources(directive_root: dict, base_dir: str) -> list[str]:
        """
        Recursively verify all agents within a directive tree have valid sources.
        Returns a list of missing agent names.
        """
        missing = []

        def recurse(node):
            if not isinstance(node, dict):
                return
            name = node.get("name")
            lang = node.get("lang", "python")
            if name:
                src_path = AgentRootSelector.find_agent_source(name, base_dir, lang)
                if not src_path:
                    missing.append(name)
            for child in node.get("children", []):
                recurse(child)

        recurse(directive_root)
        return missing
