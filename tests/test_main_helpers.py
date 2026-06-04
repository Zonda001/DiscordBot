import os

from discord_bot import main as m


def test_pid_alive():
    assert m._pid_alive(os.getpid()) is True
    assert m._pid_alive(2_000_000_000) is False


def test_acquire_lock(tmp_path, monkeypatch):
    lock = tmp_path / "bot.lock"
    monkeypatch.setattr(m, "LOCK_FILE", lock)
    # не реєструвати atexit, щоб не чіпати реальний лок робочого бота
    monkeypatch.setattr("atexit.register", lambda f: None)

    m._acquire_lock()
    assert lock.exists()
    assert lock.read_text().strip() == str(os.getpid())

    # повторний виклик тим самим PID не падає
    m._acquire_lock()
    assert lock.exists()
