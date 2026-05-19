from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from playwright.sync_api import Frame

from .models import CurvePath, CurvePoint
from .utils import clean_text, parse_aria_label, parse_number, slugify_base


CURVE_SIGNATURE_JS = r"""
() => {
  const labels = Array.from(
    document.querySelectorAll('circle.igc-data-point, circle[class*="data-point"]')
  ).slice(0, 20).map((c) => c.getAttribute("aria-label") || "");
  const paths = Array.from(
    document.querySelectorAll('path.igc-graph-line-path, path[class*="graph-line-path"]')
  ).map((p) => p.getAttribute("d") || "");
  return labels.join("|") + "::" + paths.join("|");
}
"""


EXTRACT_POINTS_JS = r"""
() => {
  function parseNumber(s) {
    if (s == null) return null;
    const n = Number(String(s).replace(",", "."));
    return Number.isFinite(n) ? n : null;
  }

  const rows = [];
  const circles = Array.from(
    document.querySelectorAll('circle.igc-data-point, circle[class*="data-point"]')
  );

  for (const [i, c] of circles.entries()) {
    const aria = c.getAttribute("aria-label") || "";
    const cx = parseNumber(c.getAttribute("cx"));
    const cy = parseNumber(c.getAttribute("cy"));
    let svgX = null;
    let svgY = null;

    try {
      if (cx != null && cy != null && c.getCTM()) {
        const p = new DOMPoint(cx, cy).matrixTransform(c.getCTM());
        svgX = p.x;
        svgY = p.y;
      }
    } catch (e) {}

    const parentSeries =
      c.closest("g[aria-label]")?.getAttribute("aria-label") ||
      c.closest("g.igc-graph-line")?.getAttribute("aria-label") ||
      "";

    rows.push({
      point_index: i,
      aria_label: aria,
      parent_series: parentSeries,
      svg_cx: cx,
      svg_cy: cy,
      svg_x_transformed: svgX,
      svg_y_transformed: svgY
    });
  }

  return rows;
}
"""


EXTRACT_PATHS_JS = r"""
() => {
  const paths = Array.from(
    document.querySelectorAll('path.igc-graph-line-path, path[class*="graph-line-path"]')
  );

  return paths.map((p, i) => ({
    path_index: i,
    aria_label:
      p.closest("g[aria-label]")?.getAttribute("aria-label") ||
      p.getAttribute("aria-label") ||
      "",
    d: p.getAttribute("d"),
    stroke: p.style.stroke || p.getAttribute("stroke") || "",
    class_name: p.getAttribute("class") || ""
  }));
}
"""


EXTRACT_SVGS_JS = r"""
() => Array.from(document.querySelectorAll("svg")).map((svg, i) => ({
  index: i,
  outer_html: svg.outerHTML
}))
"""


def get_curve_signature(frame: Frame) -> str:
    signature = frame.evaluate(CURVE_SIGNATURE_JS)
    return str(signature or "")


def extract_raw_points(frame: Frame) -> list[dict[str, Any]]:
    rows = frame.evaluate(EXTRACT_POINTS_JS)
    return rows if isinstance(rows, list) else []


def _point_series_slug(row: dict[str, Any]) -> str:
    parent_series = clean_text(row.get("parent_series"))
    if parent_series:
        return slugify_base(parent_series)

    aria_label = clean_text(row.get("aria_label"))
    if ":" in aria_label:
        return slugify_base(aria_label.split(":", 1)[0])
    return ""


def _canonical_match_slug(value: str) -> str:
    slug = slugify_base(value)
    slug = re.sub(r"([a-z])(\d)", r"\1_\2", slug)
    slug = re.sub(r"(\d)([a-z])", r"\1_\2", slug)
    slug = slug.replace("genisis", "genesis")
    slug = slug.replace("elekctric", "electric")
    slug = slug.replace("_mr", "_maximum_range")
    slug = re.sub(r"_\d+(?:_\d+)?_kwh\b", "", slug)
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug


def _series_matches_display(series_slug: str, display_name: str) -> bool:
    display_slug = _canonical_match_slug(display_name)
    series_slug = _canonical_match_slug(series_slug)
    if not display_slug or not series_slug:
        return False
    if display_slug == series_slug:
        return True

    shorter, longer = sorted([display_slug, series_slug], key=len)
    if longer.startswith(shorter + "_") and len(shorter) / len(longer) >= 0.55:
        return True

    ratio = SequenceMatcher(None, display_slug, series_slug).ratio()
    if ratio >= 0.82:
        return True

    display_tokens = set(display_slug.split("_"))
    series_tokens = set(series_slug.split("_"))
    ignorable = {"awd", "rwd", "gs", "gt", "techno", "premium", "range"}
    display_core = display_tokens - ignorable
    series_core = series_tokens - ignorable
    if display_core and series_core:
        overlap = len(display_core & series_core) / min(len(display_core), len(series_core))
        if overlap >= 0.75 and ratio >= 0.70:
            return True

    return False


def extract_curve_points(
    frame: Frame,
    vehicle_id: str,
    display_name: str,
    extraction_timestamp_utc: str,
) -> tuple[list[CurvePoint], list[str]]:
    warnings: list[str] = []
    raw_points = extract_raw_points(frame)

    normalized_display = _canonical_match_slug(display_name)
    matching = [
        row
        for row in raw_points
        if normalized_display and _series_matches_display(_point_series_slug(row), display_name)
    ]
    if matching:
        matched_series = sorted({_point_series_slug(row) for row in matching if _point_series_slug(row)})
        if matched_series and not any(_canonical_match_slug(s) == normalized_display for s in matched_series):
            warnings.append(
                "SVG series label differs from table display_name; accepted as fuzzy match: "
                f"{', '.join(matched_series[:5])}"
            )
        raw_points = matching
    elif raw_points:
        current_series = sorted({_point_series_slug(row) for row in raw_points if _point_series_slug(row)})
        warnings.append(
            "No SVG point series matched the selected vehicle; refusing to reuse the current curve. "
            f"Current series slug(s): {', '.join(current_series[:5])}"
        )
        return [], warnings

    points: list[CurvePoint] = []
    seen: set[tuple[float | None, float | None, float | None, float | None, str | None]] = set()
    duplicate_count = 0

    for row in raw_points:
        aria_label = row.get("aria_label")
        soc_percent, charging_power_kw = parse_aria_label(aria_label)
        source_type = "svg_aria" if soc_percent is not None and charging_power_kw is not None else "failed"

        if aria_label and source_type == "failed":
            warnings.append(f"Could not parse aria-label: {aria_label}")
        if soc_percent is not None and not 0 <= soc_percent <= 100:
            warnings.append(f"soc_percent outside plausible range: {soc_percent}")
        if charging_power_kw is not None and not 0 <= charging_power_kw <= 500:
            warnings.append(f"charging_power_kw outside plausible range: {charging_power_kw}")

        key = (
            soc_percent,
            charging_power_kw,
            parse_number(row.get("svg_cx")),
            parse_number(row.get("svg_cy")),
            aria_label,
        )
        if key in seen:
            duplicate_count += 1
            continue
        seen.add(key)

        points.append(
            CurvePoint(
                vehicle_id=vehicle_id,
                display_name=display_name,
                point_index=int(row.get("point_index") or 0),
                soc_percent=soc_percent,
                charging_power_kw=charging_power_kw,
                svg_cx=parse_number(row.get("svg_cx")),
                svg_cy=parse_number(row.get("svg_cy")),
                svg_x_transformed=parse_number(row.get("svg_x_transformed")),
                svg_y_transformed=parse_number(row.get("svg_y_transformed")),
                aria_label=aria_label,
                source_type=source_type,
                extraction_timestamp_utc=extraction_timestamp_utc,
            )
        )

    if duplicate_count:
        warnings.append(f"Removed {duplicate_count} duplicate curve point(s).")

    points.sort(
        key=lambda p: (
            p.soc_percent is None,
            p.soc_percent if p.soc_percent is not None else p.point_index,
            p.point_index,
        )
    )
    for index, point in enumerate(points):
        point.point_index = index

    return points, warnings


def extract_curve_paths(
    frame: Frame,
    vehicle_id: str,
    display_name: str,
    extraction_timestamp_utc: str,
) -> list[CurvePath]:
    rows = frame.evaluate(EXTRACT_PATHS_JS)
    if not isinstance(rows, list):
        return []
    return [
        CurvePath(
            vehicle_id=vehicle_id,
            display_name=display_name,
            path_index=int(row.get("path_index") or i),
            aria_label=row.get("aria_label"),
            d=row.get("d"),
            stroke=row.get("stroke"),
            class_name=row.get("class_name"),
            extraction_timestamp_utc=extraction_timestamp_utc,
        )
        for i, row in enumerate(rows)
    ]


def extract_svg_snapshots(frame: Frame) -> list[dict[str, Any]]:
    rows = frame.evaluate(EXTRACT_SVGS_JS)
    return rows if isinstance(rows, list) else []
