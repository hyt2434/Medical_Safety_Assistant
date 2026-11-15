"""Start the local development API: python app.py [--port 8000]."""

import argparse
import os
import sys
from pathlib import Path

import uvicorn


def main() -> None:
    source = Path(__file__).resolve().parent / "src"
    sys.path.insert(0, str(source))
    import settings  # Load backend .env before reading the default port.

    parser = argparse.ArgumentParser(description="Run the local backend")
    parser.add_argument("--port", type=int, default=int(os.environ.get("BACKEND_PORT", "8000")))
    parser.add_argument("--no-reload", action="store_true", help="Disable development file watcher")
    args = parser.parse_args()
    uvicorn.run(
        "api.app:app",
        host="127.0.0.1",
        port=args.port,
        reload=not args.no_reload,
        reload_dirs=[str(source)] if not args.no_reload else None,
    )


if __name__ == "__main__":
    main()
