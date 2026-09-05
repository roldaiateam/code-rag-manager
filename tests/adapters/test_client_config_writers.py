import json
import os
import tomllib

from coderagmanager.adapters.mcp.client_configs.writers import (
    ClaudeConfigWriter,
    CodexConfigWriter,
    CopilotConfigWriter,
    resolve_crm_executable,
)


def test_claude_writer_creates_mcp_json(tmp_path):
    path = ClaudeConfigWriter(str(tmp_path)).install("backend")
    config = json.loads((tmp_path / ".mcp.json").read_text())
    entry = config["mcpServers"]["crm-backend"]
    assert entry["type"] == "stdio"
    assert entry["command"] == resolve_crm_executable()
    assert entry["args"] == ["mcp", "serve", "--project", "backend"]
    assert path.endswith(".mcp.json")


def test_claude_writer_merges_without_clobbering(tmp_path):
    (tmp_path / ".mcp.json").write_text(json.dumps({
        "mcpServers": {"otro": {"type": "stdio", "command": "otro-cmd", "args": []}}
    }))
    ClaudeConfigWriter(str(tmp_path)).install("backend")
    config = json.loads((tmp_path / ".mcp.json").read_text())
    assert "otro" in config["mcpServers"]
    assert "crm-backend" in config["mcpServers"]


def test_codex_writer_creates_valid_toml(tmp_path):
    CodexConfigWriter(str(tmp_path)).install("backend")
    with open(tmp_path / ".codex" / "config.toml", "rb") as fh:
        config = tomllib.load(fh)
    entry = config["mcp_servers"]["crm-backend"]
    assert entry["command"] == resolve_crm_executable()
    assert entry["args"] == ["mcp", "serve", "--project", "backend"]
    assert entry["startup_timeout_sec"] == 10


def test_codex_writer_preserves_existing_servers(tmp_path):
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".codex" / "config.toml").write_text(
        '[mcp_servers.otro]\ncommand = "otro-cmd"\nargs = []\n'
    )
    CodexConfigWriter(str(tmp_path)).install("backend")
    with open(tmp_path / ".codex" / "config.toml", "rb") as fh:
        config = tomllib.load(fh)
    assert "otro" in config["mcp_servers"]
    assert "crm-backend" in config["mcp_servers"]


def test_copilot_writer_uses_custom_home(tmp_path):
    CopilotConfigWriter(str(tmp_path)).install("backend")
    config = json.loads((tmp_path / "mcp-config.json").read_text())
    entry = config["mcpServers"]["crm-backend"]
    assert entry["type"] == "local"
    assert entry["tools"] == ["*"]


def _make_executable(path):
    path.write_text("#!/bin/sh\n")
    os.chmod(path, 0o755)
    return path


def test_resolve_crm_executable_finds_it_in_scripts_dir(tmp_path):
    _make_executable(tmp_path / "crm")
    assert resolve_crm_executable(scripts_dir=str(tmp_path)) == str(tmp_path / "crm")


def test_resolve_crm_executable_falls_back_to_path(tmp_path, monkeypatch):
    empty_scripts_dir = tmp_path / "scripts"
    empty_scripts_dir.mkdir()
    path_dir = tmp_path / "on-path"
    path_dir.mkdir()
    _make_executable(path_dir / "crm")
    monkeypatch.setenv("PATH", str(path_dir))
    result = resolve_crm_executable(scripts_dir=str(empty_scripts_dir))
    assert result == str(path_dir / "crm")


def test_resolve_crm_executable_falls_back_to_bare_string(tmp_path, monkeypatch):
    empty_scripts_dir = tmp_path / "scripts"
    empty_scripts_dir.mkdir()
    monkeypatch.setenv("PATH", "")
    assert resolve_crm_executable(scripts_dir=str(empty_scripts_dir)) == "crm"
