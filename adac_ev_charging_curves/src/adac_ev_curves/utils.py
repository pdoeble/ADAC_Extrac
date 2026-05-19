from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Iterable


X_RE = re.compile(r"\bX\s*:\s*([-+]?\d+(?:[.,]\d+)?)", re.IGNORECASE)
Y_RE = re.compile(r"\bY\s*:\s*([-+]?\d+(?:[.,]\d+)?)", re.IGNORECASE)
ADAC_PERCENT_RE = re.compile(
    r"(?:^|:|\s)([-+]?\d+(?:[.,]\d+)?)\s*%?\s*:\s*([-+]?\d+(?:[.,]\d+)?)\s*$"
)

KNOWN_MANUFACTURERS = [
    "Mercedes-Benz",
    "Alfa Romeo",
    "Aston Martin",
    "Land Rover",
    "Volkswagen",
    "Polestar",
    "Porsche",
    "Hyundai",
    "Genesis",
    "Peugeot",
    "Renault",
    "Subaru",
    "Toyota",
    "Citroen",
    "Skoda",
    "Smart",
    "Audi",
    "BMW",
    "BYD",
    "Cupra",
    "Ford",
    "Honda",
    "Jaguar",
    "Kia",
    "KIA",
    "Lucid",
    "Mazda",
    "MINI",
    "NIO",
    "Opel",
    "Tesla",
    "Volvo",
    "VW",
    "XPeng",
    "MG",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_number(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = (
        text.replace("\u2212", "-")
        .replace("\xa0", " ")
        .replace("%", "")
        .replace("kW", "")
        .strip()
    )
    text = re.sub(r"\s+", "", text)
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        number = float(text)
    except ValueError:
        return None
    return number if number == number else None


def parse_aria_label(label: str | None) -> tuple[float | None, float | None]:
    """Parse Infogram point labels into (soc_percent, charging_power_kw)."""
    if not label:
        return None, None

    x_match = X_RE.search(label)
    y_match = Y_RE.search(label)
    if x_match and y_match:
        return parse_number(x_match.group(1)), parse_number(y_match.group(1))

    # Current ADAC/Infogram labels look like:
    # "Model name: 10%: 104,7" or "Model name: 10: 296,2".
    adac_match = ADAC_PERCENT_RE.search(label)
    if adac_match:
        return parse_number(adac_match.group(1)), parse_number(adac_match.group(2))

    return None, None


def slugify_base(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_text.lower()).strip("_")
    slug = re.sub(r"_+", "_", slug)
    return slug or "vehicle"


def slugify_vehicle_id(value: str, existing: set[str] | None = None) -> str:
    base = slugify_base(value)
    if existing is None:
        return base

    candidate = base
    counter = 2
    while candidate in existing:
        candidate = f"{base}_{counter}"
        counter += 1
    existing.add(candidate)
    return candidate


def safe_filename(value: str) -> str:
    return slugify_base(value)[:120]


def parse_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    text = value.strip().lower()
    if text in {"1", "true", "yes", "y", "ja", "j"}:
        return True
    if text in {"0", "false", "no", "n", "nein"}:
        return False
    raise ValueError(f"Invalid boolean value: {value!r}")


def clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_key(value: str) -> str:
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text.lower()).strip("_")
    return re.sub(r"_+", "_", text)


def first_matching_value(table_values: dict[str, str], needles: Iterable[str]) -> str | None:
    normalized_needles = [normalize_key(n) for n in needles]
    for key, value in table_values.items():
        normalized_key = normalize_key(key)
        if any(needle in normalized_key for needle in normalized_needles):
            return value or None
    return None


def normalize_vehicle_columns(table_values: dict[str, str], row_index: int) -> dict[str, str | None]:
    return {
        "rank": str(row_index + 1),
        "range_total_one_stop_km": first_matching_value(
            table_values, ["gesamt reichweite", "gesamt-reichweite", "total range"]
        ),
        "range_until_stop_km": first_matching_value(
            table_values, ["reichweite mit vollem akku", "10 restenergie", "range until"]
        ),
        "range_added_20min_km": first_matching_value(
            table_values, ["20 minuten", "20 min", "gewonnene reichweite", "range added"]
        ),
        "battery_capacity_kwh": first_matching_value(
            table_values, ["batteriekapazitat", "batteriekapazitaet", "battery capacity", "kapazitat kwh"]
        ),
        "consumption_kwh_per_100km": first_matching_value(
            table_values, ["verbrauch", "consumption"]
        ),
        "max_charging_power_kw": first_matching_value(
            table_values, ["max ladeleistung", "max charging", "ladeleistung max"]
        ),
    }


def split_vehicle_name(display_name: str) -> tuple[str | None, str | None, str | None]:
    cleaned = clean_text(display_name)
    if not cleaned:
        return None, None, None

    for manufacturer in sorted(KNOWN_MANUFACTURERS, key=len, reverse=True):
        if cleaned.lower().startswith(manufacturer.lower() + " ") or cleaned.lower() == manufacturer.lower():
            rest = cleaned[len(manufacturer) :].strip()
            canonical = "Kia" if manufacturer.upper() == "KIA" else manufacturer
            return canonical, rest or None, None

    first, _, rest = cleaned.partition(" ")
    return first or None, rest or None, None
