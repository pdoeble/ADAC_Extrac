import csv

from adac_ev_curves.export import PATH_COLUMNS, POINT_COLUMNS, VEHICLE_COLUMNS, export_dataset
from adac_ev_curves.models import CurvePath, CurvePoint, ExtractionLogRecord, Vehicle


def read_header(path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        return next(csv.reader(handle))


def test_export_schema_contains_required_columns(tmp_path) -> None:
    vehicle = Vehicle(
        vehicle_id="mini_aceman_se_favoured_trim",
        row_index=0,
        manufacturer="MINI",
        model="Aceman SE Favoured Trim",
        variant=None,
        display_name="MINI Aceman SE Favoured Trim",
        table_values={"vehicle": "MINI Aceman SE Favoured Trim"},
        source_url="https://example.test",
        extraction_timestamp_utc="2026-01-01T00:00:00Z",
        raw_row_text="MINI Aceman SE Favoured Trim 517 332 185",
    )
    point = CurvePoint(
        vehicle_id=vehicle.vehicle_id,
        display_name=vehicle.display_name,
        point_index=0,
        soc_percent=99.9,
        charging_power_kw=46.0,
        svg_cx=1.0,
        svg_cy=2.0,
        svg_x_transformed=1.0,
        svg_y_transformed=2.0,
        aria_label="MINI Aceman SE Favoured Trim: X: 99.9, Y: 46",
        source_type="svg_aria",
        extraction_timestamp_utc="2026-01-01T00:00:00Z",
    )
    path = CurvePath(
        vehicle_id=vehicle.vehicle_id,
        display_name=vehicle.display_name,
        path_index=0,
        aria_label=vehicle.display_name,
        d="M0 0L1 1",
        stroke="#000",
        class_name="igc-graph-line-path",
        extraction_timestamp_utc="2026-01-01T00:00:00Z",
    )
    log = ExtractionLogRecord(
        timestamp_utc="2026-01-01T00:00:00Z",
        level="INFO",
        vehicle_id=vehicle.vehicle_id,
        display_name=vehicle.display_name,
        message="ok",
    )

    export_dataset(tmp_path, [vehicle], [point], [path], [log], {"source_name": "test"})

    assert set(VEHICLE_COLUMNS).issubset(read_header(tmp_path / "vehicles.csv"))
    assert set(POINT_COLUMNS).issubset(read_header(tmp_path / "charging_curve_points.csv"))
    assert set(PATH_COLUMNS).issubset(read_header(tmp_path / "charging_curve_paths.csv"))

