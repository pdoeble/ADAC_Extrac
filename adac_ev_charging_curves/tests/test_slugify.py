from adac_ev_curves.utils import slugify_vehicle_id


def test_slugify_vehicle_id() -> None:
    assert slugify_vehicle_id("MINI Aceman SE Favoured Trim") == "mini_aceman_se_favoured_trim"


def test_slugify_vehicle_id_uniqueness() -> None:
    existing: set[str] = set()
    assert slugify_vehicle_id("MINI Aceman SE Favoured Trim", existing) == "mini_aceman_se_favoured_trim"
    assert slugify_vehicle_id("MINI Aceman SE Favoured Trim", existing) == "mini_aceman_se_favoured_trim_2"

