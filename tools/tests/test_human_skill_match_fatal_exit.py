import pytest

import run_vs_ai_human_skill as match_entry
from sc2.protocol import ProtocolResponseTimeoutError


def test_match_entry_converts_transport_fatal_to_nonzero_exit(monkeypatch, tmp_path):
    class FatalGameStarter:
        def __init__(self, _definitions):
            pass

        def play(self):
            raise ProtocolResponseTimeoutError("injected observation timeout")

    monkeypatch.setattr(match_entry, "GameStarter", FatalGameStarter)
    monkeypatch.setattr(match_entry, "BotDefinitions", lambda _path: object())
    monkeypatch.setattr(match_entry.os, "chdir", lambda _path: None)

    with pytest.raises(SystemExit) as raised:
        match_entry.main(
            [
                "--force-human-skill",
                "PvP_O01",
                "--output-base-dir",
                str(tmp_path),
                "--skip-version-update",
            ]
        )

    assert raised.value.code == match_entry.MATCH_FATAL_EXIT_CODE
