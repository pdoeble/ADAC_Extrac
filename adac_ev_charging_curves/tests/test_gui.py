from adac_ev_curves.gui import build_figure, load_dataset, make_plot_style, parse_percentiles


def test_gui_dataset_and_figure(tmp_path) -> None:
    (tmp_path / "vehicles.csv").write_text(
        "\n".join(
            [
                "vehicle_id,row_index,display_name,manufacturer,model,variant,source_url,extraction_timestamp_utc,raw_row_text,table_values_json,rank,range_until_stop_km,range_added_20min_km,range_total_one_stop_km,battery_capacity_kwh,consumption_kwh_per_100km,max_charging_power_kw",
                'car_a,0,Car A,Brand A,,,,,,{},1,300,120,420,,,',
                'car_b,1,Car B,Brand B,,,,,,{},2,250,100,350,,,',
                'car_c,2,Car C,Brand A,,,,,,{},3,240,90,330,,,',
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "charging_curve_points.csv").write_text(
        "\n".join(
            [
                "vehicle_id,display_name,point_index,soc_percent,charging_power_kw,svg_cx,svg_cy,svg_x_transformed,svg_y_transformed,aria_label,source_type,extraction_timestamp_utc",
                "car_a,Car A,0,10,100,,,,,,svg_aria,",
                "car_a,Car A,1,20,200,,,,,,svg_aria,",
                "car_b,Car B,0,10,50,,,,,,svg_aria,",
                "car_b,Car B,1,20,150,,,,,,svg_aria,",
                "car_c,Car C,0,10,80,,,,,,svg_aria,",
                "car_c,Car C,1,20,120,,,,,,svg_aria,",
            ]
        ),
        encoding="utf-8",
    )

    dataset = load_dataset(tmp_path)
    assert dataset.vehicle_ids == ["car_a", "car_b", "car_c"]
    assert dataset.points[1]["charging_power_relative_percent"] == 100.0

    figure = build_figure(
        dataset,
        ["car_a", "car_b"],
        "soc_percent",
        "charging_power_relative_percent",
        "manufacturer",
    )
    assert len(figure.data) == 2
    assert figure.layout.yaxis.title.text == "Relative charging power [%]"
    assert figure.data[0].mode == "lines"
    assert figure.layout.font.family == "Times New Roman"
    assert figure.layout.width == 336
    assert figure.layout.height == 250

    empty = build_figure(dataset, [], "soc_percent", "charging_power_kw", "manufacturer")
    assert empty.layout.title.text is None

    styled = build_figure(
        dataset,
        ["car_a", "car_b"],
        "soc_percent",
        "charging_power_kw",
        "max_observed_charging_power_kw",
        make_plot_style(
            line_width=5,
            marker_size=0,
            plot_width=900,
            plot_height=500,
            font_size=16,
            title_font_size=24,
            line_shape="spline",
            show_title=True,
        ),
    )
    assert styled.layout.showlegend is False
    assert styled.layout.width == 900
    assert styled.layout.height == 500
    assert styled.layout.font.size == 16
    assert styled.layout.title.font.size == 24
    assert styled.layout.title.text == "ADAC/Infogram charging curves - 2 vehicle(s)"
    assert styled.data[0].showlegend is False
    assert styled.data[0].mode == "lines"
    assert styled.data[0].line.width == 5
    assert styled.data[0].line.shape == "spline"

    manufacturer_legend = build_figure(
        dataset,
        ["car_a", "car_b", "car_c"],
        "soc_percent",
        "charging_power_kw",
        "manufacturer",
    )
    assert [trace.name for trace in manufacturer_legend.data if trace.showlegend] == ["Brand A", "Brand B"]

    percentiles = build_figure(
        dataset,
        ["car_a", "car_b", "car_c"],
        "soc_percent",
        "charging_power_kw",
        "manufacturer",
        plot_mode="percentiles",
        percentile_text="worst, 50, top",
    )
    assert [trace.name for trace in percentiles.data] == ["Worst", "50% Percentile", "Top"]
    assert all(trace.showlegend for trace in percentiles.data)
    assert percentiles.layout.showlegend is True
    assert list(percentiles.data[0].y) == [50.0, 120.0]
    assert list(percentiles.data[1].y) == [80.0, 150.0]
    assert list(percentiles.data[2].y) == [100.0, 200.0]

    filtered_percentile_legend = build_figure(
        dataset,
        ["car_a", "car_b", "car_c"],
        "soc_percent",
        "charging_power_kw",
        "manufacturer",
        plot_mode="percentiles",
        percentile_text="worst, 25, 50, 75, top",
        percentile_legend_text="25, 75",
    )
    assert [trace.name for trace in filtered_percentile_legend.data if trace.showlegend] == [
        "25% Percentile",
        "75% Percentile",
    ]

    percentile_colorbar = build_figure(
        dataset,
        ["car_a", "car_b", "car_c"],
        "soc_percent",
        "charging_power_kw",
        "manufacturer",
        plot_mode="percentiles",
        percentile_text="worst, 50, top",
        percentile_legend_mode="colorbar",
    )
    assert percentile_colorbar.layout.showlegend is False
    assert percentile_colorbar.data[-1].marker.showscale is True

    percentile_heatmap = build_figure(
        dataset,
        ["car_a", "car_b", "car_c"],
        "soc_percent",
        "charging_power_kw",
        "manufacturer",
        plot_mode="percentiles",
        percentile_text="worst, 50, top",
        percentile_display="heatmap",
        percentile_legend_mode="colorbar",
    )
    assert percentile_heatmap.data[0].type == "heatmap"
    assert percentile_heatmap.data[0].showscale is True


def test_parse_percentiles() -> None:
    assert parse_percentiles("worst, 5, 50, 95, top") == [
        ("Worst", 0.0),
        ("5% Percentile", 5.0),
        ("50% Percentile", 50.0),
        ("95% Percentile", 95.0),
        ("Top", 100.0),
    ]
    assert parse_percentiles("min 0 100 max") == [("Worst", 0.0), ("Top", 100.0)]
    assert parse_percentiles("not-a-percentile")[:2] == [("Worst", 0.0), ("5% Percentile", 5.0)]
