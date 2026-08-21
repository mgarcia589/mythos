"""Allow running with: python -m lab.mythos_ui

Supports:
    python -m lab.mythos_ui            → native desktop window
    python -m lab.mythos_ui --web      → browser mode (http://localhost:8080)
    python -m lab.mythos_ui --port 9000  → custom port
    python -m lab.mythos_ui --no-open  → don't auto-open browser/window
"""

import sys
from pathlib import Path

# Ensure project root on path
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _check_dependencies():
    """Verify required packages are installed."""
    missing = []
    for pkg in ["nicegui", "plotly", "pandas"]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"\n  [ERROR] Missing dependencies: {', '.join(missing)}")
        print(f"  Install with: pip install {' '.join(missing)}")
        print()
        sys.exit(1)


def _print_banner():
    """Print startup ASCII banner."""
    from lab.mythos_ui import __version__

    banner = (
        f"\n"
        f"    +-------------------------------------------+\n"
        f"    |                                           |\n"
        f"    |   M Y T H O S                            |\n"
        f"    |   Compliance Review Engine  v{__version__}     |\n"
        f"    |                                           |\n"
        f"    +-------------------------------------------+\n"
    )
    print(banner)


def _parse_args():
    """Parse CLI arguments."""
    args = {
        "web": "--web" in sys.argv,
        "port": 8080,
        "no_open": "--no-open" in sys.argv,
    }

    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        if idx + 1 < len(sys.argv):
            try:
                args["port"] = int(sys.argv[idx + 1])
            except ValueError:
                print(f"  [WARN] Invalid port, using default 8080")

    if "--help" in sys.argv or "-h" in sys.argv:
        print("""
  Mythos UI — Desktop/Web Dashboard for Compliance Review

  Usage:
    python -m lab.mythos_ui [OPTIONS]

  Options:
    --web       Run in browser mode (default: native desktop window)
    --port N    Server port (default: 8080)
    --no-open   Don't auto-open the browser/window
    --help, -h  Show this help message
        """)
        sys.exit(0)

    return args


def main():
    _check_dependencies()
    _print_banner()
    args = _parse_args()

    mode = "browser" if args["web"] else "native desktop"
    print(f"  Mode: {mode}")
    print(f"  Port: {args['port']}")
    print(f"  URL:  http://localhost:{args['port']}")
    print()

    from lab.mythos_ui.main import start_with_options
    start_with_options(
        native=not args["web"],
        port=args["port"],
        show=not args["no_open"],
    )


if __name__ == "__main__":
    main()
else:
    main()
