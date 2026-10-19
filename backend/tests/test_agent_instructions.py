"""Leitura local das instruções, sem chamadas de IA ou mudanças no prompt real."""

from types import SimpleNamespace

import pytest

from app.agents import game_agent
from app.core.errors import AIConfigurationError


def test_instructions_path_is_independent_of_working_directory(monkeypatch, tmp_path):
    expected = game_agent.INSTRUCTIONS_PATH.read_text(encoding="utf-8").strip()
    monkeypatch.chdir(tmp_path)
    assert game_agent.load_instructions() == expected


def test_invalid_utf8_is_a_configuration_error(monkeypatch, tmp_path):
    path = tmp_path / "instructions.md"
    path.write_bytes(b"\xff\xfe")
    monkeypatch.setattr(game_agent, "INSTRUCTIONS_PATH", path)
    with pytest.raises(AIConfigurationError):
        game_agent.load_instructions()


@pytest.mark.parametrize("error", [PermissionError("internal-path"), IsADirectoryError("internal-path")])
def test_read_failure_does_not_expose_internal_details(monkeypatch, error):
    def fail(*, encoding):
        assert encoding == "utf-8"
        raise error

    monkeypatch.setattr(game_agent, "INSTRUCTIONS_PATH", SimpleNamespace(read_text=fail))
    with pytest.raises(AIConfigurationError) as captured:
        game_agent.load_instructions()
    assert "internal-path" not in str(captured.value)
