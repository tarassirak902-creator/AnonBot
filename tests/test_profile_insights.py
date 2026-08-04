from app.services.profile_insights import (
    ProfileInsights,
    achievement_progress,
    build_achievements,
)


def test_new_user_has_only_welcome_achievement() -> None:
    achievements = build_achievements(ProfileInsights(), is_vip=False, stars_balance=0)

    unlocked, total = achievement_progress(achievements)

    assert unlocked == 1
    assert total == 9
    assert achievements[0].code == "welcome"
    assert achievements[0].unlocked is True
    assert all(not item.unlocked for item in achievements[1:])


def test_activity_unlocks_matching_achievements() -> None:
    insights = ProfileInsights(
        days_in_bot=7,
        questions_sent=1,
        questions_answered=1,
        link_visits=10,
        gifts_sent=1,
        gifts_received=5,
    )

    achievements = build_achievements(insights, is_vip=True, stars_balance=100)

    assert all(item.unlocked for item in achievements)
    assert achievement_progress(achievements) == (9, 9)


def test_unrelated_activity_does_not_unlock_achievements() -> None:
    insights = ProfileInsights(questions_received=100, answers_received=100)

    achievements = build_achievements(insights, is_vip=False, stars_balance=99)
    unlocked_codes = {item.code for item in achievements if item.unlocked}

    assert unlocked_codes == {"welcome"}
