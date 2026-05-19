from __future__ import annotations

from dataclasses import dataclass, field


NORMALIZED_VEHICLE_COLUMNS = [
    "rank",
    "range_until_stop_km",
    "range_added_20min_km",
    "range_total_one_stop_km",
    "battery_capacity_kwh",
    "consumption_kwh_per_100km",
    "max_charging_power_kw",
]


@dataclass
class Vehicle:
    vehicle_id: str
    row_index: int
    manufacturer: str | None
    model: str | None
    variant: str | None
    display_name: str
    table_values: dict[str, str]
    source_url: str
    extraction_timestamp_utc: str
    raw_row_text: str = ""
    rank: str | None = None
    range_until_stop_km: str | None = None
    range_added_20min_km: str | None = None
    range_total_one_stop_km: str | None = None
    battery_capacity_kwh: str | None = None
    consumption_kwh_per_100km: str | None = None
    max_charging_power_kw: str | None = None


@dataclass
class CurvePoint:
    vehicle_id: str
    display_name: str
    point_index: int
    soc_percent: float | None
    charging_power_kw: float | None
    svg_cx: float | None
    svg_cy: float | None
    svg_x_transformed: float | None
    svg_y_transformed: float | None
    aria_label: str | None
    source_type: str
    extraction_timestamp_utc: str


@dataclass
class CurvePath:
    vehicle_id: str
    display_name: str
    path_index: int
    aria_label: str | None
    d: str | None
    stroke: str | None
    class_name: str | None
    extraction_timestamp_utc: str


@dataclass
class ExtractionLogRecord:
    timestamp_utc: str
    level: str
    vehicle_id: str | None
    display_name: str | None
    message: str


@dataclass
class ExtractionResult:
    vehicles: list[Vehicle] = field(default_factory=list)
    points: list[CurvePoint] = field(default_factory=list)
    paths: list[CurvePath] = field(default_factory=list)
    logs: list[ExtractionLogRecord] = field(default_factory=list)
    summary: dict[str, object] = field(default_factory=dict)

