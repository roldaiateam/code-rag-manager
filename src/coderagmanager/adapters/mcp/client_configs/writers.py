"""Generadores de configuración MCP por cliente.

Cada writer sabe leer el fichero existente (si lo hay), fusionar la entrada
`crm-<project_id>` sin pisar otros servidores ya configurados, y escribirlo
de vuelta en su formato. Añadir un cliente futuro = un writer nuevo.
"""

from __future__ import annotations

import json
import os
import tomllib


def server_entry_name(project_id: str) -> str:
    return f"crm-{project_id}"


def server_command(project_id: str) -> tuple[str, list[str]]:
    return "crm", ["mcp", "serve", "--project", project_id]


class ClaudeConfigWriter:
    """Claude Code: `.mcp.json` en la raíz del repo (ámbito project, versionable)."""

    def __init__(self, project_root: str):
        self._path = os.path.join(project_root, ".mcp.json")

    def install(self, project_id: str) -> str:
        config = {}
        if os.path.exists(self._path):
            with open(self._path, encoding="utf-8") as fh:
                config = json.load(fh)
        command, args = server_command(project_id)
        config.setdefault("mcpServers", {})[server_entry_name(project_id)] = {
            "type": "stdio",
            "command": command,
            "args": args,
        }
        with open(self._path, "w", encoding="utf-8") as fh:
            json.dump(config, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        return self._path


class CodexConfigWriter:
    """Codex CLI: `.codex/config.toml` a nivel de proyecto (proyectos de confianza)."""

    def __init__(self, project_root: str):
        self._path = os.path.join(project_root, ".codex", "config.toml")

    def install(self, project_id: str) -> str:
        config = {}
        if os.path.exists(self._path):
            with open(self._path, "rb") as fh:
                config = tomllib.load(fh)
        command, args = server_command(project_id)
        config.setdefault("mcp_servers", {})[server_entry_name(project_id)] = {
            "command": command,
            "args": args,
            "startup_timeout_sec": 10,
        }
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as fh:
            fh.write(_dump_toml(config))
        return self._path


class CopilotConfigWriter:
    """Copilot CLI: `~/.copilot/mcp-config.json` (redirigible con COPILOT_HOME)."""

    def __init__(self, copilot_home: str | None = None):
        home = copilot_home or os.environ.get(
            "COPILOT_HOME", os.path.expanduser("~/.copilot")
        )
        self._path = os.path.join(home, "mcp-config.json")

    def install(self, project_id: str) -> str:
        config = {}
        if os.path.exists(self._path):
            with open(self._path, encoding="utf-8") as fh:
                config = json.load(fh)
        command, args = server_command(project_id)
        config.setdefault("mcpServers", {})[server_entry_name(project_id)] = {
            "type": "local",
            "command": command,
            "args": args,
            "tools": ["*"],
        }
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as fh:
            json.dump(config, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        return self._path


def build_writer(client: str, project_root: str):
    if client == "claude":
        return ClaudeConfigWriter(project_root)
    if client == "codex":
        return CodexConfigWriter(project_root)
    if client == "copilot":
        return CopilotConfigWriter()
    raise ValueError(f"Cliente desconocido: '{client}' (usa claude|codex|copilot).")


def _toml_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value)  # JSON escapa igual que TOML para strings simples
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(v) for v in value) + "]"
    raise TypeError(f"Valor TOML no soportado: {value!r}")


def _dump_toml(data: dict, prefix: str = "") -> str:
    scalars, tables = [], []
    for key, value in data.items():
        if isinstance(value, dict):
            tables.append((key, value))
        else:
            scalars.append((key, value))
    out = []
    for key, value in scalars:
        out.append(f"{key} = {_toml_value(value)}")
    if scalars:
        out.append("")
    for key, value in tables:
        full_key = f"{prefix}.{key}" if prefix else key
        nested_tables = {k: v for k, v in value.items() if isinstance(v, dict)}
        own_scalars = {k: v for k, v in value.items() if not isinstance(v, dict)}
        if own_scalars or not nested_tables:
            out.append(f"[{full_key}]")
            for k, v in own_scalars.items():
                out.append(f"{k} = {_toml_value(v)}")
            out.append("")
        if nested_tables:
            out.append(_dump_toml(nested_tables, prefix=full_key))
    return "\n".join(out).strip() + "\n"
