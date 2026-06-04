from discord_bot import config


def test_int_env(monkeypatch):
    monkeypatch.setenv("FOO_INT", "42")
    assert config._int_env("FOO_INT") == 42
    monkeypatch.setenv("FOO_INT", "abc")
    assert config._int_env("FOO_INT", 7) == 7
    monkeypatch.delenv("FOO_INT", raising=False)
    assert config._int_env("FOO_INT", 5) == 5


def test_validate_ok():
    # .env у проєкті містить валідний токен
    assert config.validate() == []
