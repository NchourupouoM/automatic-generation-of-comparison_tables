from app.core.utils import clamp_pagination


def test_defaults_when_none():
    assert clamp_pagination(None, None, default=50, maximum=200) == (50, 0)


def test_caps_at_maximum():
    limit, _ = clamp_pagination(10_000, 0, default=50, maximum=200)
    assert limit == 200


def test_floors_limit_at_one():
    limit, _ = clamp_pagination(0, 0, default=50, maximum=200)
    assert limit == 50  # 0 is falsy -> falls back to default


def test_negative_offset_becomes_zero():
    _, offset = clamp_pagination(10, -5, default=50, maximum=200)
    assert offset == 0


def test_valid_values_pass_through():
    assert clamp_pagination(25, 75, default=50, maximum=200) == (25, 75)
