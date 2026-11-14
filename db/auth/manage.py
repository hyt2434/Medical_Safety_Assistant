"""Apply additive identity migrations and optionally seed development accounts."""
import argparse
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps/backend/src"))
from auth.db import initialize, migrate

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["migrate", "seed"])
    args = parser.parse_args()
    if args.command == "migrate":
        migrate()
    else:
        os.environ["AUTH_SEED_DEMO"] = "1"
        initialize()
    print("Identity " + args.command + " completed; existing accounts and grants retained.")
