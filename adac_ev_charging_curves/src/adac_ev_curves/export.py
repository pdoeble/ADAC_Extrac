from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from .models import (
    CurvePath,
    CurvePoint,
    ExtractionLogRecord,
    NORMALIZED_VEHICLE_COLUMNS,
    Vehicle,
)


VEHICLE_COLUMNS = [
    "vehicle_id",
    "row_index",
    "display_name",
    "manufacturer",
    "model",
    "variant",
    "source_url",
    "extraction_timestamp_utc",
    "raw_row_text",
    "table_values_json",
    *NORMALIZED_VEHICLE_COLUMNS,
]

POINT_COLUMNS = [
    "vehicle_id",
    "display_name",
    "point_index",
    "soc_percent",
    "charging_power_kw",
    "svg_cx",
    "svg_cy",
    "svg_x_transformed",
    "svg_y_transformed",
    "aria_label",
    "source_type",
    "extraction_timestamp_utc",
]

PATH_COLUMNS = [
    "vehicle_id",
    "display_name",
    "path_index",
    "aria_label",
    "d",
    "stroke",
    "class_name",
    "extraction_timestamp_utc",
]

LOG_COLUMNS = ["timestamp_utc", "level", "vehicle_id", "display_name", "message"]


def ensure_output_dirs(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "raw").mkdir(parents=True, exist_ok=True)


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: "" if row.get(key) is None else row.get(key) for key in fieldnames})


def vehicle_to_row(vehicle: Vehicle) -> dict[str, object]:
    row = asdict(vehicle)
    row["table_values_json"] = json.dumps(vehicle.table_values, ensure_ascii=False, sort_keys=True)
    return row


def export_dataset(
    out_dir: str | Path,
    vehicles: list[Vehicle],
    points: list[CurvePoint],
    paths: list[CurvePath],
    logs: list[ExtractionLogRecord],
    metadata: dict[str, object],
) -> None:
    out_path = Path(out_dir)
    ensure_output_dirs(out_path)

    write_csv(out_path / "vehicles.csv", VEHICLE_COLUMNS, (vehicle_to_row(v) for v in vehicles))
    write_csv(out_path / "charging_curve_points.csv", POINT_COLUMNS, (asdict(p) for p in points))
    write_csv(out_path / "charging_curve_paths.csv", PATH_COLUMNS, (asdict(p) for p in paths))
    write_csv(out_path / "extraction_log.csv", LOG_COLUMNS, (asdict(record) for record in logs))

    with (out_path / "source_metadata.json").open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2)


def build_summary(vehicles: list[Vehicle], points: list[CurvePoint]) -> dict[str, object]:
    vehicle_ids_with_points = {point.vehicle_id for point in points}
    soc_values = [point.soc_percent for point in points if point.soc_percent is not None]
    power_values = [point.charging_power_kw for point in points if point.charging_power_kw is not None]
    return {
        "vehicle_count": len(vehicles),
        "vehicles_with_points": len(vehicle_ids_with_points),
        "vehicles_without_points": len(vehicles) - len(vehicle_ids_with_points),
        "point_count": len(points),
        "soc_percent_min": min(soc_values) if soc_values else None,
        "soc_percent_max": max(soc_values) if soc_values else None,
        "charging_power_kw_min": min(power_values) if power_values else None,
        "charging_power_kw_max": max(power_values) if power_values else None,
    }

