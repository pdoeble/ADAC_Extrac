from adac_ev_curves.utils import parse_aria_label


def test_parse_x_y_label() -> None:
    soc_percent, charging_power_kw = parse_aria_label(
        "MINI Aceman SE Favoured Trim: X: 99.9, Y: 46"
    )
    assert soc_percent == 99.9
    assert charging_power_kw == 46.0


def test_parse_simple_x_y_label() -> None:
    assert parse_aria_label("X: 10, Y: 152") == (10.0, 152.0)
    assert parse_aria_label("X: 10.5, Y: 152.3") == (10.5, 152.3)
    assert parse_aria_label("X: 10,5, Y: 152,3") == (10.5, 152.3)


def test_parse_current_adac_percent_label() -> None:
    assert parse_aria_label("MINI Aceman SE Favoured Trim: 10%: 99,0") == (10.0, 99.0)
    assert parse_aria_label("Mercedes-Benz CLA Coupe 250+ EQ Progressive: 10: 296,2") == (
        10.0,
        296.2,
    )


def test_parse_invalid_label() -> None:
    assert parse_aria_label("kein gültiges label") == (None, None)

