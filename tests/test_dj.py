"""Тести DJ-логіки (vote-skip): чисті функції member_is_dj / votes_needed."""
from types import SimpleNamespace

from discord_bot.cogs.music import member_is_dj, votes_needed


def _member(*, role_ids=(), admin=False):
    return SimpleNamespace(
        roles=[SimpleNamespace(id=rid) for rid in role_ids],
        guild_permissions=SimpleNamespace(administrator=admin),
    )


def test_no_dj_role_everyone_allowed():
    # DJ-роль не задана -> керують усі
    assert member_is_dj(_member(), None) is True
    assert member_is_dj(_member(), 0) is True


def test_member_with_dj_role():
    assert member_is_dj(_member(role_ids=[111]), 111) is True
    assert member_is_dj(_member(role_ids=[222]), 111) is False


def test_admin_bypasses_dj_role():
    # адмін без DJ-ролі все одно проходить
    assert member_is_dj(_member(admin=True), 111) is True


def test_plain_member_blocked_when_dj_set():
    assert member_is_dj(_member(role_ids=[222]), 111) is False
    assert member_is_dj(_member(), 111) is False


def test_votes_needed_majority():
    assert votes_needed(1) == 1   # сам у каналі — миттєво
    assert votes_needed(2) == 1
    assert votes_needed(3) == 2
    assert votes_needed(4) == 2
    assert votes_needed(5) == 3
    assert votes_needed(0) == 1   # захист від ділення/порожнечі
