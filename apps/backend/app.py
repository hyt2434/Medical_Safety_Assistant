"""Start the local development API: python app.py [--port 8000]."""

import argparse
import os
import sys
from pathlib import Path

import uvicorn


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    source = root / 'src'
    sys.path[:0] = [str(root), str(source)]
    from shared.auth import settings

    parser = argparse.ArgumentParser(description="Run the local backend")
    parser.add_argument("--port", type=int, default=int(os.environ.get("BACKEND_PORT", "8000")))
    parser.add_argument("--no-reload", action="store_true", help="Disable development file watcher")
    args = parser.parse_args()
    uvicorn.run(
        "apps.backend.api.app:app",
        host="127.0.0.1",
        port=args.port,
        reload=not args.no_reload,
        reload_dirs=[str(source)] if not args.no_reload else None,
    )


if __name__ == "__main__":
    main()
