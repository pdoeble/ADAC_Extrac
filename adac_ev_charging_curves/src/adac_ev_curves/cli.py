from __future__ import annotations

import argparse
import json
from pathlib import Path

from .browser import DEFAULT_INFOGRAM_URL, ExtractOptions, run_extraction
from .utils import parse_bool


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="adac-ev-curves")
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract = subparsers.add_parser("extract", help="Extract ADAC/Infogram charging curves.")
    extract.add_argument("--url", default=DEFAULT_INFOGRAM_URL, help="Infogram URL or ADAC main article URL.")
    extract.add_argument("--out", default="output", help="Output directory.")
    extract.add_argument("--headless", default="true", help="true/false")
    extract.add_argument("--delay-ms", type=int, default=500, help="Wait time after model click.")
    extract.add_argument("--limit", type=int, default=None, help="Only extract the first N models.")
    extract.add_argument("--save-html", action="store_true", help="Save per-vehicle HTML snapshots.")
    extract.add_argument("--save-svg", action="store_true", help="Save per-vehicle SVG snapshots.")
    extract.add_argument("--debug", action="store_true", help="Enable verbose extraction logging.")

    gui = subparsers.add_parser("gui", help="Start the interactive Plotly/Dash comparison GUI.")
    gui.add_argument("--data", default="output", help="Directory with extracted CSV files.")
    gui.add_argument("--host", default="127.0.0.1", help="Dash host.")
    gui.add_argument("--port", type=int, default=8050, help="Dash port.")
    gui.add_argument("--debug", action="store_true", help="Enable Dash debug mode.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "extract":
        options = ExtractOptions(
            url=args.url,
            out=Path(args.out),
            headless=parse_bool(args.headless),
            delay_ms=args.delay_ms,
            limit=args.limit,
            save_html=args.save_html or args.debug,
            save_svg=args.save_svg or args.debug,
            debug=args.debug,
        )
        summary = run_extraction(options)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    if args.command == "gui":
        from .gui import create_app

        app = create_app(args.data)
        print(json.dumps({"url": f"http://{args.host}:{args.port}", "data": str(Path(args.data).resolve())}, indent=2))
        app.run(host=args.host, port=args.port, debug=args.debug)
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
