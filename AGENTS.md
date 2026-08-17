# AGENTS.md

Diese Hinweise gelten fuer dieses Repository und als Vorlage fuer aehnliche Projekte, in denen Mess- oder Webdaten als interaktive Visualisierung ueber GitHub Pages veroeffentlicht werden.

## Grundsatz

- GitHub Pages ist statisches Hosting. Baue keine Loesung, die einen laufenden Python-, Dash-, Flask- oder FastAPI-Server voraussetzt.
- Wenn eine lokale Dash- oder Python-GUI existiert, muss es fuer Pages eine separate statische Ausgabe geben, typischerweise `index.html` plus `assets/data.json`.
- Der statische Build muss reproduzierbar per CLI und per GitHub Actions erzeugbar sein.
- Trenne Rohdaten, aufbereitete Daten, Build-Skripte und generierte Website-Ausgabe klar.

## Daten

- Dokumentiere fuer jedes Dataset Quelle, URL, Abruf- oder Extraktionszeitpunkt, Einheiten, Transformationen und bekannte Einschraenkungen.
- Bewahre Rohdaten oder Audit-Informationen, wenn sie fuer Reproduzierbarkeit wichtig sind. Veraendere sie nicht stillschweigend.
- Normalisiere Spaltennamen und Einheiten explizit. Achsenbeschriftungen muessen Einheiten enthalten, bevorzugt in eckigen Klammern, z. B. `Temperature [degC]`, `State of charge [%]`, `Charging power [kW]`.
- Behandle fehlende Werte, Ausreisser und Plausibilitaetsgrenzen sichtbar im Code. Nicht hart abbrechen, wenn einzelne Messreihen fehlerhaft sind, aber Warnungen oder Logs erzeugen.
- Sortiere Zeitreihen und Kurven vor dem Plotten. Entferne oder aggregiere doppelte Stuetzstellen nur mit nachvollziehbarer Methode.
- Bei interpolierten oder aggregierten Daten muss klar sein, welche Werte Originalpunkte und welche berechnet sind.

## Visualisierung

- Die erste Ansicht soll eine brauchbare Analyseansicht sein, keine Landingpage.
- Settings sollen logisch gruppiert sein, z. B. `Analysis`, `Percentiles`, `Lines & Legend`, `Figure & Export`.
- Plots muessen exportierbar sein, mindestens als SVG. Fuer Publikationen sind SVG/PDF fuer Linienplots und PNG als robuste Zusatzoption sinnvoll.
- Verwende klare Achsentitel mit Einheiten, nicht nur Variablennamen.
- Verwende eine weisse Plot- und Papierflaeche, zurueckhaltende Gridlines und schwarze Achsenlinien, sofern kein anderes Design gefordert ist.
- Bei vielen Linien: Legenden gruppieren, Colorbars fuer kontinuierliche Kodierung verwenden und redundante Legenden vermeiden.
- Farben duerfen nicht die einzige Unterscheidung sein, wenn Kurven in Graustufen unterscheidbar bleiben sollen. Linienarten oder direkte Labels sind dann zu bevorzugen.
- Marker bei dichten Linienplots standardmaessig ausblenden, wenn sie die Lesbarkeit verschlechtern.
- Kontinuierliche Farbskalen sollen eine Colorbar zeigen und individuelle Linienlegenden ausblenden, sofern sonst die Legende ueberfuellt waere.
- Titel innerhalb der Grafik nur verwenden, wenn er fuer den Export benoetigt wird. Wenn er verwendet wird, zentriert und fett setzen.

## GitHub Pages

- Lege den Pages-Build unter einem ignorierten Verzeichnis wie `site/` ab. Committe generierte Site-Dateien nur, wenn das Projekt bewusst ohne Actions deployen soll.
- Nutze einen Workflow unter `.github/workflows/`, der:
  - das Repository auscheckt,
  - Python installiert,
  - das Paket installiert,
  - die statische Site baut,
  - das Pages-Artefakt hochlaedt,
  - nach GitHub Pages deployed.
- Die Pages-Quelle in den GitHub-Einstellungen muss auf `GitHub Actions` stehen.
- Der statische Build darf nicht von lokalen absoluten Pfaden abhaengen.
- Externe CDN-Abhaengigkeiten wie Plotly sind fuer einfache Pages-Seiten akzeptabel. Wenn Offline-Reproduzierbarkeit wichtig ist, muss die JS-Datei lokal vendored und versioniert werden.
- Nach Aenderungen an der Website immer lokal bauen und mit einem statischen Server testen:

```bash
python -m adac_ev_curves.cli site --data adac_ev_charging_curves/output --out site
python -m http.server 8060 --directory site
```

## Tests und Checks

- Fuehre nach Codeaenderungen die Tests aus:

```bash
python -m pytest
```

- Bei Frontend- oder Plot-Aenderungen zusaetzlich einen Browser-Smoke-Test mit Playwright oder manuell durchfuehren:
  - Seite laedt ohne JavaScript-Fehler.
  - Plot rendert und ist nicht leer.
  - Default-Settings stimmen.
  - Export-Button funktioniert.
  - GitHub-Pages-Static und lokale GUI bleiben konsistent.
- Bei reinen Dokumentationsaenderungen reicht eine Sichtpruefung, sofern keine Build- oder UI-Logik betroffen ist.

## Quellen, Lizenzen und Zitate

- Quellenlinks sichtbar in der Anwendung platzieren, nicht nur in der README.
- Lange fremde Textpassagen nicht vollstaendig kopieren. Kurze Zitate sind erlaubt, der Rest soll paraphrasiert werden.
- Zitate als solche kennzeichnen und mit Quelle verlinken.
- Wichtige Begriffe in Methodik- oder Hinweisboxen koennen fett hervorgehoben werden, z. B. `300 kW` oder Herstellernamen.
- Wenn Daten fuer wissenschaftliche Auswertung gedacht sind, immer auf gerenderte/aufbereitete Daten, Extraktionsmethode und moegliche Abweichungen von Originalmessdaten hinweisen.

## Projektkonventionen

- Python-Code liegt in `adac_ev_charging_curves/src/adac_ev_curves/`.
- Extrahierte Standarddaten liegen in `adac_ev_charging_curves/output/`.
- Die lokale Dash-GUI wird mit `python -m adac_ev_curves.gui --data output` gestartet.
- Die gemeinsame CLI ist `python -m adac_ev_curves.cli`.
- Der statische Pages-Build ist `python -m adac_ev_curves.cli site --data output --out site`.
- Halte Dash-GUI und statische GitHub-Pages-Seite funktional gleichwertig, wenn Bedienelemente oder Defaults geaendert werden.
- Aendere keine fremden oder vom Nutzer erzeugten Dateien unnoetig. Vor groesseren Datenneuextraktionen oder Massenformatierungen kurz klaeren, ob das gewollt ist.
