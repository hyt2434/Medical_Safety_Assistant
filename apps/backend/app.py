"""Start the local development API: python app.py [--port 8000]."""

import argparse
import sys
from pathlib import Path

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local backend")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    source = Path(__file__).resolve().parent / "src"
    sys.path.insert(0, str(source))
    uvicorn.run(
        "api.app:app",
        host="127.0.0.1",
        port=args.port,
        reload=True,
        reload_dirs=[str(source)],
    )


if __name__ == "__main__":
    main()
