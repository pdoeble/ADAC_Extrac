from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Frame, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from .export import build_summary, ensure_output_dirs, export_dataset
from .extract_curve import (
    extract_curve_paths,
    extract_curve_points,
    extract_svg_snapshots,
    get_curve_signature,
)
from .extract_table import discover_vehicle_rows
from .models import CurvePath, CurvePoint, ExtractionLogRecord, Vehicle
from .utils import (
    normalize_vehicle_columns,
    safe_filename,
    slugify_base,
    slugify_vehicle_id,
    split_vehicle_name,
    utc_now_iso,
)


MAIN_ARTICLE_URL = (
    "https://www.adac.de/rund-ums-fahrzeug/elektromobilitaet/laden/"
    "schnellladen-langstrecke-ladekurven-2026/"
)

DEFAULT_INFOGRAM_URL = (
    "https://www.adac.de/infogram/a194a8ff-52a8-41cb-bd33-e553c66f04f8/"
    "?parent_url=https%3A%2F%2Fwww.adac.de%2Frund-ums-fahrzeug%2Felektromobilitaet%2F"
    "laden%2Fschnellladen-langstrecke-ladekurven-2026%2F&src=embed#async_embed"
)


@dataclass
class ExtractOptions:
    url: str
    out: Path
    headless: bool = True
    delay_ms: int = 500
    limit: int | None = None
    save_html: bool = False
    save_svg: bool = False
    debug: bool = False


class ExtractionLogger:
    def __init__(self) -> None:
        self.records: list[ExtractionLogRecord] = []

    def log(
        self,
        level: str,
        message: str,
        vehicle_id: str | None = None,
        display_name: str | None = None,
    ) -> None:
        self.records.append(
            ExtractionLogRecord(
                timestamp_utc=utc_now_iso(),
                level=level.upper(),
                vehicle_id=vehicle_id,
                display_name=display_name,
                message=message,
            )
        )


def _wait_for_load(page: Page) -> None:
    page.wait_for_load_state("domcontentloaded", timeout=90_000)
    try:
        page.wait_for_load_state("networkidle", timeout=30_000)
    except PlaywrightTimeoutError:
        pass
    page.wait_for_timeout(1500)


def _try_accept_cookie_banner(page: Page) -> None:
    selectors = [
        'button:has-text("Alle akzeptieren")',
        'button:has-text("Akzeptieren")',
        'button:has-text("Zustimmen")',
        'button:has-text("Accept all")',
        '[data-testid*="accept"]',
        '#onetrust-accept-btn-handler',
    ]
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if locator.count() and locator.is_visible(timeout=1000):
                locator.click(timeout=3000)
                page.wait_for_timeout(500)
                return
        except PlaywrightError:
            continue


def _select_infogram_frame(page: Page, source_url: str) -> tuple[Frame, str]:
    if "/infogram/" in source_url:
        return page.main_frame, page.url

    iframe = page.locator('iframe[src*="/infogram/"]').first
    iframe.wait_for(state="attached", timeout=45_000)
    src = iframe.get_attribute("src") or source_url
    frame = iframe.element_handle().content_frame()
    if frame is None:
        raise RuntimeError("Infogram iframe was found, but Playwright could not access its frame.")
    return frame, src


def _wait_for_infogram_ready(frame: Frame) -> None:
    selectors = [
        "svg",
        "table",
        "circle.igc-data-point",
        'circle[class*="data-point"]',
        "path.igc-graph-line-path",
        'path[class*="graph-line-path"]',
        "g.igc-graph-line",
    ]
    last_error: Exception | None = None
    for selector in selectors:
        try:
            frame.locator(selector).first.wait_for(state="attached", timeout=20_000)
            return
        except Exception as exc:  # Playwright has multiple timeout/error subclasses.
            last_error = exc
    if last_error:
        raise RuntimeError("Infogram DOM did not expose expected SVG/table selectors.") from last_error


def _wait_for_curve_change(frame: Frame, previous_signature: str, delay_ms: int) -> bool:
    frame.page.wait_for_timeout(delay_ms)
    try:
        frame.wait_for_function(
            """previous => {
              const labels = Array.from(
                document.querySelectorAll('circle.igc-data-point, circle[class*="data-point"]')
              ).slice(0, 20).map((c) => c.getAttribute("aria-label") || "");
              const paths = Array.from(
                document.querySelectorAll('path.igc-graph-line-path, path[class*="graph-line-path"]')
              ).map((p) => p.getAttribute("d") || "");
              return labels.join("|") + "::" + paths.join("|") !== previous;
            }""",
            arg=previous_signature,
            timeout=max(2000, delay_ms * 4),
        )
        return True
    except PlaywrightTimeoutError:
        return False


def _find_current_row(frame: Frame, vehicle: Vehicle, fallback_row: dict[str, Any]) -> dict[str, Any]:
    """Rediscover row markers because Infogram can mutate parts of the table after chart switches."""
    try:
        rows = discover_vehicle_rows(frame)
    except Exception:
        return fallback_row

    display_slug = slugify_base(vehicle.display_name)
    for row in rows:
        if slugify_base(str(row.get("display_name") or "")) == display_slug:
            return row
    for row in rows:
        if int(row.get("row_index") or -1) == vehicle.row_index:
            return row
    return fallback_row


def _click_vehicle_row(frame: Frame, row: dict[str, Any], vehicle: Vehicle) -> None:
    selector = str(row.get("click_selector") or row.get("row_selector"))
    locator = frame.locator(selector).first
    locator.scroll_into_view_if_needed(timeout=15_000)
    frame.page.wait_for_timeout(150)
    locator.click(timeout=15_000, force=True)


def _save_snapshots(
    frame: Frame,
    out_dir: Path,
    vehicle_id: str,
    save_html: bool,
    save_svg: bool,
) -> None:
    raw_dir = out_dir / "raw"
    if save_html:
        (raw_dir / f"{safe_filename(vehicle_id)}.html").write_text(frame.content(), encoding="utf-8")
    if save_svg:
        for svg in extract_svg_snapshots(frame):
            index = int(svg.get("index") or 0)
            outer_html = str(svg.get("outer_html") or "")
            if outer_html:
                (raw_dir / f"{safe_filename(vehicle_id)}_svg_{index:02d}.svg").write_text(
                    outer_html, encoding="utf-8"
                )


def _vehicle_from_row(
    row: dict[str, Any],
    source_url: str,
    extraction_timestamp_utc: str,
    used_ids: set[str],
) -> Vehicle:
    display_name = str(row.get("display_name") or "").strip()
    table_values = row.get("table_values") if isinstance(row.get("table_values"), dict) else {}
    normalized = normalize_vehicle_columns({str(k): str(v) for k, v in table_values.items()}, int(row["row_index"]))
    manufacturer, model, variant = split_vehicle_name(display_name)
    return Vehicle(
        vehicle_id=slugify_vehicle_id(display_name, used_ids),
        row_index=int(row["row_index"]),
        manufacturer=manufacturer,
        model=model,
        variant=variant,
        display_name=display_name,
        table_values={str(k): str(v) for k, v in table_values.items()},
        source_url=source_url,
        extraction_timestamp_utc=extraction_timestamp_utc,
        raw_row_text=str(row.get("raw_row_text") or ""),
        **normalized,
    )


def _metadata(url: str, infogram_url: str, extraction_timestamp_utc: str) -> dict[str, object]:
    return {
        "source_name": "ADAC / Infogram",
        "main_article_url": MAIN_ARTICLE_URL,
        "infogram_url": infogram_url if "/infogram/" in infogram_url else url,
        "extraction_timestamp_utc": extraction_timestamp_utc,
        "method": "Playwright DOM extraction of Infogram SVG points",
        "primary_curve_source": "circle.igc-data-point aria-label",
        "fallback_curve_source": "SVG coordinate calibration when aria-labels are not parseable",
        "notes": [
            "The SVG path is stored for audit purposes only.",
            "The primary numerical data are taken from point aria-labels if available.",
            "The data may be website-rendered/processed data, not necessarily original ADAC raw measurement data.",
        ],
    }


def run_extraction(options: ExtractOptions) -> dict[str, object]:
    ensure_output_dirs(options.out)
    logger = ExtractionLogger()
    extraction_timestamp_utc = utc_now_iso()
    vehicles: list[Vehicle] = []
    points: list[CurvePoint] = []
    paths: list[CurvePath] = []
    infogram_url = options.url

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=options.headless)
        page = browser.new_page(viewport={"width": 1600, "height": 2000}, locale="de-DE")
        try:
            page.goto(options.url, wait_until="domcontentloaded", timeout=90_000)
            _wait_for_load(page)
            _try_accept_cookie_banner(page)
            frame, infogram_url = _select_infogram_frame(page, options.url)
            _wait_for_infogram_ready(frame)
            page.wait_for_timeout(1500)

            row_candidates = discover_vehicle_rows(frame)
            if options.limit is not None:
                row_candidates = row_candidates[: options.limit]

            used_ids: set[str] = set()
            for row in row_candidates:
                vehicle = _vehicle_from_row(row, infogram_url, extraction_timestamp_utc, used_ids)
                vehicles.append(vehicle)
                logger.log(
                    "INFO",
                    f"Model recognized from {row.get('candidate_source', 'unknown')}.",
                    vehicle.vehicle_id,
                    vehicle.display_name,
                )

            for row, vehicle in zip(row_candidates, vehicles, strict=False):
                try:
                    vehicle_points: list[CurvePoint] = []
                    point_warnings: list[str] = []
                    changed = False
                    for attempt in range(2):
                        current_row = _find_current_row(frame, vehicle, row)
                        previous_signature = get_curve_signature(frame)
                        _click_vehicle_row(frame, current_row, vehicle)
                        logger.log(
                            "INFO",
                            f"Model clicked (attempt {attempt + 1}).",
                            vehicle.vehicle_id,
                            vehicle.display_name,
                        )
                        changed = _wait_for_curve_change(frame, previous_signature, options.delay_ms)
                        vehicle_points, point_warnings = extract_curve_points(
                            frame,
                            vehicle.vehicle_id,
                            vehicle.display_name,
                            extraction_timestamp_utc,
                        )
                        if vehicle_points:
                            break
                        if attempt == 0:
                            page.wait_for_timeout(max(750, options.delay_ms))

                    if not changed and not vehicle_points:
                        logger.log(
                            "WARNING",
                            "Curve signature did not change after click and no matching curve points were found.",
                            vehicle.vehicle_id,
                            vehicle.display_name,
                        )

                    vehicle_paths = extract_curve_paths(
                        frame,
                        vehicle.vehicle_id,
                        vehicle.display_name,
                        extraction_timestamp_utc,
                    )
                    points.extend(vehicle_points)
                    paths.extend(vehicle_paths)

                    logger.log(
                        "INFO",
                        f"Extracted {len(vehicle_points)} point(s).",
                        vehicle.vehicle_id,
                        vehicle.display_name,
                    )
                    logger.log(
                        "INFO",
                        f"Extracted {len(vehicle_paths)} path(s).",
                        vehicle.vehicle_id,
                        vehicle.display_name,
                    )
                    if not vehicle_points:
                        logger.log("WARNING", "No curve points extracted.", vehicle.vehicle_id, vehicle.display_name)
                    for warning in point_warnings:
                        logger.log("WARNING", warning, vehicle.vehicle_id, vehicle.display_name)

                    _save_snapshots(frame, options.out, vehicle.vehicle_id, options.save_html, options.save_svg)

                except Exception as exc:
                    logger.log(
                        "ERROR",
                        f"Vehicle extraction failed: {exc}",
                        vehicle.vehicle_id,
                        vehicle.display_name,
                    )
                    continue
        finally:
            browser.close()

    summary = build_summary(vehicles, points)
    metadata = _metadata(options.url, infogram_url, extraction_timestamp_utc)
    metadata["summary"] = summary
    export_dataset(options.out, vehicles, points, paths, logger.records, metadata)
    return summary
