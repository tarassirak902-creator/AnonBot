from __future__ import annotations

import builtins

import run


def test_ensure_env_fills_all_required_values_and_preserves_extra(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("BOT_TOKEN=existing-token\nEXTRA_FLAG=keep-me\n", encoding="utf-8")
    monkeypatch.setattr(run, "ENV_FILE", env_file)

    answers = iter(["123,456", "-100123", "@casper_test_bot"])
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(answers))

    run.ensure_env()
    values = run._read_env()

    assert values["BOT_TOKEN"] == "existing-token"
    assert values["ADMIN_IDS"] == "123,456"
    assert values["LOG_CHANNEL_ID"] == "-100123"
    assert values["BOT_USERNAME"] == "casper_test_bot"
    assert values["EXTRA_FLAG"] == "keep-me"


def test_ensure_env_does_not_prompt_when_complete(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "BOT_TOKEN=t\nADMIN_IDS=1\nLOG_CHANNEL_ID=-1001\nBOT_USERNAME=botname\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(run, "ENV_FILE", env_file)
    monkeypatch.setattr(
        builtins,
        "input",
        lambda prompt="": (_ for _ in ()).throw(AssertionError("input must not be called")),
    )

    run.ensure_env()
