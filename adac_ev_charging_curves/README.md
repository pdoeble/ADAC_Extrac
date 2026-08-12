---
canonical_status: unknown
normative_status: binding
lifecycle_state: unknown
currency_assessment: not_assessed
audit_role: core
scope: project
review_disposition: review
provenance_origin: local_project_authoring
document_kind: technical_or_research_note
derivation: direct_authoring
---
# ADAC / Infogram EV Charging Curves

http://127.0.0.1:8050

Quelle:

- Hauptartikel: https://www.adac.de/rund-ums-fahrzeug/elektromobilitaet/laden/schnellladen-langstrecke-ladekurven-2026/
- Direktes Infogram-Embed: https://www.adac.de/infogram/a194a8ff-52a8-41cb-bd33-e553c66f04f8/?parent_url=https%3A%2F%2Fwww.adac.de%2Frund-ums-fahrzeug%2Felektromobilitaet%2Fladen%2Fschnellladen-langstrecke-ladekurven-2026%2F&src=embed#async_embed

Dieses Projekt extrahiert die Fahrzeugtabelle und die gerenderten SVG-Ladekurven aus dem ADAC/Infogram-Embed:

<https://www.adac.de/infogram/a194a8ff-52a8-41cb-bd33-e553c66f04f8/?parent_url=https%3A%2F%2Fwww.adac.de%2Frund-ums-fahrzeug%2Felektromobilitaet%2Fladen%2Fschnellladen-langstrecke-ladekurven-2026%2F&src=embed#async_embed>

Die Primärdatenquelle für Kurvenpunkte sind `circle.igc-data-point`-Elemente im gerenderten SVG. Das `aria-label` wird zuerst geparst; der SVG-`path d` wird zusätzlich als Audit-Information gespeichert und nicht als Primärdatenquelle behandelt.

## Installation

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
```

Für lokale Entwicklung:

```bash
python -m pip install -e .
```

## Conda-Environment

Alternativ kann ein reproduzierbares Conda-Environment aus der YAML gebaut werden:

```bash
conda env create -f environment.yml
conda activate adac-ev-curves
python -m pip install -e .
python -m playwright install chromium
```

Wenn das Environment schon existiert:

```bash
conda env update -f environment.yml --prune
conda activate adac-ev-curves
python -m pip install -e .
python -m playwright install chromium
```

## Ausführung

Empfohlener erster Probelauf:

```bash
python -m adac_ev_curves.cli extract ^
  --url "https://www.adac.de/infogram/a194a8ff-52a8-41cb-bd33-e553c66f04f8/?parent_url=https%3A%2F%2Fwww.adac.de%2Frund-ums-fahrzeug%2Felektromobilitaet%2Fladen%2Fschnellladen-langstrecke-ladekurven-2026%2F&src=embed#async_embed" ^
  --out output ^
  --headless false ^
  --limit 3 ^
  --debug
```

Headless-Lauf für alle Modelle:

```bash
python -m adac_ev_curves.cli extract --out output --headless true
```

Optionen:

- `--url`: Infogram-URL oder ADAC-Hauptartikel-URL
- `--out`: Ausgabeverzeichnis
- `--headless`: `true` oder `false`
- `--delay-ms`: Wartezeit nach Modellklick, Standard `500`
- `--limit`: optional nur die ersten N Modelle extrahieren
- `--save-html`: HTML-Snapshots in `raw/` speichern
- `--save-svg`: SVG-Snapshots in `raw/` speichern
- `--debug`: speichert HTML- und SVG-Snapshots und schreibt ausführliche Logs

## Ausgabe

Nach einem erfolgreichen Lauf liegen im Ausgabeverzeichnis:

- `vehicles.csv`
- `charging_curve_points.csv`
- `charging_curve_paths.csv`
- `source_metadata.json`
- `extraction_log.csv`
- `raw/`

`vehicles.csv` enthält generische Tabellenwerte als `table_values_json` plus normalisierte Spalten, soweit aus den Tabellenüberschriften ableitbar. `charging_curve_points.csv` enthält pro Fahrzeug sortierte Wertepaare aus `soc_percent` und `charging_power_kw` sowie SVG-Koordinaten und das Original-`aria-label`.

## Extraktionslogik

1. Playwright lädt die direkte Infogram-URL oder den ADAC-Hauptartikel.
2. Bei Hauptartikel-URLs wird das Infogram-`iframe` gesucht und als aktiver Frame verwendet.
3. Die interaktive Tabelle wird bevorzugt als echtes HTML-`table` gelesen.
4. Pro Zeile wird der sichtbare Fahrzeugname, der Tabellenrohtext und ein Satz Header/Wert-Paare gespeichert.
5. Für Infogram sitzt die Kurvenumschaltung in der zweiten, optisch leeren Tabellenspalte als Link mit `aria-label="Switch chart tab"`. Dieser Link wird pro Fahrzeug geklickt.
6. Danach werden SVG-Kurvenpunkte aus `circle.igc-data-point` gelesen. Unterstützte `aria-label`-Formate sind unter anderem:
   - `Modellname: X: 99.9, Y: 46`
   - `Modellname: 10%: 104,7`
   - `Modellname: 10: 296,2`
7. Zusätzliche Pfade aus `path.igc-graph-line-path` werden für Audit-Zwecke gespeichert.

## Tests

```bash
python -m pytest
```

Die Tests prüfen das Parsing der `aria-label`s, eindeutige Fahrzeug-IDs und die CSV-Pflichtspalten.

## Interaktive GUI

Nach einer Extraktion kann eine lokale Plotly/Dash-Oberfläche gestartet werden:

```bash
python -m adac_ev_curves.gui --data output --host 127.0.0.1 --port 8050
```

Alternativ über die gemeinsame CLI:

```bash
python -m adac_ev_curves.cli gui --data output
```

Die Oberfläche enthält:

- selectable vehicle table with ADAC metadata and checkboxes
- buttons for `Select all` and `Select none`
- source link to the ADAC article above the controls
- plot mode switch between individual `Vehicles` and aggregated `Percentiles`
- editable percentile list; default is `Worst`, every 5% step from `5% Percentile` to `95% Percentile`, and `Top`
- separate control for which percentile lines receive legend entries, e.g. only `Worst, 25, 50, 75, Top`
- percentile labels use publication-friendly names such as `30% Percentile`
- percentile display as individual lines or as an interpolated false-color field between the `Worst` and `Top` percentile curves
- percentile legend can be shown as selected legend entries, as a continuous colorbar, or hidden
- configurable legend position, including inside-bottom-left placement, and centered bold figure title
- percentile curves are computed over the selected vehicles on shared x-axis support points with linear interpolation
- configurable x and y axes, including SOC, absolute charging power in kW, and relative charging power as percent of each vehicle's maximum; axis units are written in square brackets
- line colors by vehicle, manufacturer, or continuous quantities such as observed maximum power and range values
- one legend entry per manufacturer when `Brand / manufacturer (discrete)` is selected
- grouped settings panels for analysis, percentiles, line/legend styling, and figure/export controls
- methodology note below the figure with a short ADAC excerpt and paraphrased test context
- publication-oriented defaults: percentile mode, relative charging power, colorbar legend, Times New Roman, 500 x 400 px, 16 px labels, white background, subtle grid, black axis lines, and centered bold title
- display options for font family, line shape, percentile dash style, line width, marker size, opacity, figure width/height, font sizes, and cyclic line styles
- for continuous color scales, individual line legend entries are hidden; only the colorbar remains visible
- SVG export through the `Export SVG` button
- additional SVG export through the Plotly modebar

## Statische GitHub-Pages-Seite

Die Dash-GUI benötigt einen laufenden Python-Server und kann deshalb nicht direkt auf GitHub Pages betrieben werden. Für GitHub Pages gibt es zusätzlich einen statischen Build, der dieselben extrahierten CSV-Daten in eine eigenständige Plotly/JavaScript-Seite schreibt:

```bash
python -m adac_ev_curves.cli site --data output --out site
```

Der Build erzeugt:

- `site/index.html`
- `site/assets/data.json`
- `site/.nojekyll`

Die Datei `site/index.html` kann lokal über einen einfachen statischen Server getestet werden:

```bash
python -m http.server 8080 --directory site
```

Danach im Browser öffnen:

```text
http://127.0.0.1:8080
```

Für GitHub Pages ist ein Workflow unter `.github/workflows/pages.yml` enthalten. Beim Push auf `main` installiert der Workflow das Paket, baut die statische Seite aus `adac_ev_charging_curves/output` und deployed das Ergebnis als GitHub-Pages-Artefakt.

Einmalige GitHub-Einstellung:

1. Repository auf GitHub öffnen.
2. `Settings` -> `Pages` öffnen.
3. Unter `Build and deployment` bei `Source` den Eintrag `GitHub Actions` auswählen.
4. Änderungen auf `main` pushen.
5. Im Tab `Actions` den Workflow `Deploy GitHub Pages` prüfen.

Die spätere URL hat typischerweise dieses Schema:

```text
https://<github-user-or-org>.github.io/<repository-name>/
```

Falls eine Custom Domain genutzt wird, muss sie zusätzlich in den GitHub-Pages-Einstellungen konfiguriert werden.

## Methodische Hinweise

Die extrahierten Werte sind gerenderte/aufbereitete Website-Daten. Für wissenschaftliche Nutzung sollten Quelle, URL, Extraktionszeitpunkt, Parser-Version und der Hinweis dokumentiert werden, dass die SVG-Pfade nur Audit-Daten sind.
