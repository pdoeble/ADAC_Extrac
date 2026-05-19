from __future__ import annotations

from typing import Any

from playwright.sync_api import Frame


DISCOVER_ROWS_JS = r"""
() => {
  function clean(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function visible(el) {
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return rect.width > 1 && rect.height > 1 && style.display !== "none" && style.visibility !== "hidden";
  }

  function uniqueKey(base, target) {
    let key = clean(base) || "column";
    if (key.toLowerCase() === "sort") key = "column";
    let candidate = key;
    let suffix = 2;
    while (Object.prototype.hasOwnProperty.call(target, candidate)) {
      candidate = `${key}_${suffix}`;
      suffix += 1;
    }
    return candidate;
  }

  function textOf(el) {
    return clean(el.innerText || el.textContent || "");
  }

  function rowClickTarget(row) {
    return (
      row.querySelector('td:first-child a[data-href]') ||
      row.querySelector('a[data-href]') ||
      row.querySelector('td:first-child a[role="link"][tabindex]') ||
      row.querySelector('a[aria-label*="Switch chart tab" i]') ||
      row.querySelector('a[aria-label*="Switch" i]') ||
      row.querySelector('button[aria-label*="Switch" i]') ||
      row.querySelector('a[role="link"][tabindex]') ||
      row.querySelector('button') ||
      row.querySelector('[tabindex]')
    );
  }

  function displayNameFromCells(cells) {
    for (const cell of cells) {
      const value = textOf(cell);
      if (!value) continue;
      if (/switch chart tab/i.test(value)) continue;
      if (!/[A-Za-zÄÖÜäöü]/.test(value)) continue;
      if (/^sort$/i.test(value)) continue;
      return value;
    }
    return "";
  }

  const results = [];
  let marker = 0;

  const tables = Array.from(document.querySelectorAll("table")).filter(visible);
  for (const table of tables) {
    const headerCells = Array.from(table.querySelectorAll("thead th, thead td"));
    const headers = headerCells.map(textOf);
    const bodyRows = Array.from(table.querySelectorAll("tbody tr"));
    const rows = bodyRows.length ? bodyRows : Array.from(table.querySelectorAll("tr"));

    for (const row of rows) {
      if (!visible(row)) continue;
      const cells = Array.from(row.querySelectorAll(":scope > th, :scope > td"));
      if (cells.length < 2) continue;
      const cellTexts = cells.map(textOf);
      const displayName = displayNameFromCells(cells);
      if (!displayName) continue;
      if (displayName.toLowerCase() === "sort") continue;

      const tableValues = {};
      for (let i = 0; i < cells.length; i += 1) {
        let header = headers[i] || "";
        if (i === 0 && (!header || /^sort$/i.test(header))) header = "vehicle";
        if (i === 1 && (!header || /^sort$/i.test(header))) header = "chart_switch";
        if (!header || /^sort$/i.test(header)) header = `column_${i + 1}`;
        tableValues[uniqueKey(header, tableValues)] = cellTexts[i] || "";
      }

      const rowId = `adac-row-${marker}`;
      row.setAttribute("data-adac-extractor-row-id", rowId);
      const clickTarget = rowClickTarget(row) || row;
      const clickId = `adac-click-${marker}`;
      clickTarget.setAttribute("data-adac-extractor-click-id", clickId);

      results.push({
        row_index: results.length,
        display_name: displayName,
        raw_row_text: cellTexts.filter(Boolean).join(" "),
        table_values: tableValues,
        row_selector: `[data-adac-extractor-row-id="${rowId}"]`,
        click_selector: `[data-adac-extractor-click-id="${clickId}"]`,
        candidate_source: "table",
      });
      marker += 1;
    }
  }

  if (results.length) {
    return results;
  }

  const genericSelectors = [
    "tr",
    '[role="row"]',
    '[data-lookup*="contents"]',
    '[data-lookup*="table"]',
    "button",
    "[tabindex]",
    "[onclick]"
  ];

  const seen = new Set();
  for (const selector of genericSelectors) {
    for (const el of Array.from(document.querySelectorAll(selector))) {
      if (!visible(el)) continue;
      const text = textOf(el);
      const normalized = text.toLowerCase();
      if (!text || text.length < 3 || text.length > 500) continue;
      if (!/[A-Za-zÄÖÜäöü]/.test(text)) continue;
      if (/^(sort|switch chart tab|interact)$/i.test(text)) continue;
      if (seen.has(normalized)) continue;
      seen.add(normalized);

      const rowId = `adac-row-${marker}`;
      el.setAttribute("data-adac-extractor-row-id", rowId);
      const clickId = `adac-click-${marker}`;
      el.setAttribute("data-adac-extractor-click-id", clickId);

      results.push({
        row_index: results.length,
        display_name: text,
        raw_row_text: text,
        table_values: { raw_row_text: text },
        row_selector: `[data-adac-extractor-row-id="${rowId}"]`,
        click_selector: `[data-adac-extractor-click-id="${clickId}"]`,
        candidate_source: selector,
      });
      marker += 1;
    }
  }

  return results;
}
"""


def discover_vehicle_rows(frame: Frame) -> list[dict[str, Any]]:
    rows = frame.evaluate(DISCOVER_ROWS_JS)
    if not isinstance(rows, list):
        return []
    return rows
