"""Apply additive identity migrations and optionally seed development accounts."""
import argparse
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from shared.auth.db import initialize, migrate

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["migrate", "seed", "provision-core"])
    parser.add_argument('--account-id', help='Existing canonical Auth UUID; server operator only')
    args = parser.parse_args()
    if args.command == "migrate":
        migrate()
    elif args.command == 'seed':
        os.environ["AUTH_SEED_DEMO"] = "1"
        initialize()
    else:
        import psycopg
        from shared.auth.core_owner import provision_core_identity
        if not args.account_id or not os.environ.get('CORE_DB_DSN'):
            parser.error('provision-core requires --account-id and CORE_DB_DSN')
        with psycopg.connect(os.environ['CORE_DB_DSN'], autocommit=True) as connection:
            provision_core_identity(args.account_id, connection)
    print("Identity " + args.command + " completed; existing accounts and grants retained.")
