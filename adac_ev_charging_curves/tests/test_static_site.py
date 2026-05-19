import json

from adac_ev_curves.static_site import build_static_site


def test_build_static_site(tmp_path) -> None:
    data_dir = tmp_path / "data"
    site_dir = tmp_path / "site"
    data_dir.mkdir()

    (data_dir / "vehicles.csv").write_text(
        "\n".join(
            [
                "vehicle_id,row_index,display_name,manufacturer,model,variant,source_url,extraction_timestamp_utc,raw_row_text,table_values_json,rank,range_until_stop_km,range_added_20min_km,range_total_one_stop_km,battery_capacity_kwh,consumption_kwh_per_100km,max_charging_power_kw",
                'car_a,0,Car A,Brand A,,,,,,{},1,300,120,420,,,',
            ]
        ),
        encoding="utf-8",
    )
    (data_dir / "charging_curve_points.csv").write_text(
        "\n".join(
            [
                "vehicle_id,display_name,point_index,soc_percent,charging_power_kw,svg_cx,svg_cy,svg_x_transformed,svg_y_transformed,aria_label,source_type,extraction_timestamp_utc",
                "car_a,Car A,0,10,100,,,,,,svg_aria,",
                "car_a,Car A,1,20,200,,,,,,svg_aria,",
            ]
        ),
        encoding="utf-8",
    )
    (data_dir / "source_metadata.json").write_text('{"source_name":"test"}', encoding="utf-8")

    summary = build_static_site(data_dir, site_dir)

    assert summary["vehicles"] == 1
    assert (site_dir / "index.html").exists()
    assert (site_dir / ".nojekyll").exists()
    payload = json.loads((site_dir / "assets" / "data.json").read_text(encoding="utf-8"))
    assert payload["vehicleIds"] == ["car_a"]
    assert payload["ui"]["defaultPercentiles"].startswith("Worst")
    assert payload["ui"]["defaultPlotMode"] == "percentiles"
    assert payload["ui"]["defaultYAxis"] == "charging_power_relative_percent"
    assert payload["ui"]["defaultPercentileLegendMode"] == "colorbar"
    assert payload["ui"]["defaultPercentileDash"] == "solid"
    assert payload["ui"]["defaultTitle"] == "100 EV Models / Charging Power"
    assert {"label": "Inside bottom left", "value": "inside_bottom_left"} in payload["ui"]["legendPositionOptions"]
