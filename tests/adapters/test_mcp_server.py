from coderagmanager.adapters.mcp.server import serve


class _FakeMCPServer:
    def run(self, transport: str) -> None:
        pass


def test_serve_prints_ready_message_to_stderr_not_stdout(capsys):
    serve(
        "proyecto-test",
        _build_server=lambda pid, registry_path=None: _FakeMCPServer(),
    )
    captured = capsys.readouterr()
    assert "proyecto-test" in captured.err
    assert captured.out == ""
