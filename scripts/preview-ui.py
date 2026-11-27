"""Start UI and API using apps/backend/.env, or an explicit isolated Auth preview.

Run with the project's Python environment. Core settings can be supplied via
environment variables or apps/backend/.env; this script never provisions Core.
"""
import argparse
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=5173)
    parser.add_argument('--api-port', type=int, default=8000)
    parser.add_argument('--isolated-auth', action='store_true', help='Use a separate SQLite preview and disable Core')
    args = parser.parse_args()
    for port in (args.port, args.api_port):
        with socket.socket() as probe:
            try:
                probe.bind(('127.0.0.1', port))
            except OSError:
                parser.error(f'Port {port} is occupied. Stop the previous preview or select another port.')
    npm = shutil.which('npm.cmd' if os.name == 'nt' else 'npm')
    if not npm or not (ROOT / 'apps/frontend/node_modules').is_dir():
        parser.error('Install frontend dependencies first: cd apps/frontend && npm ci')
    origin = f'http://127.0.0.1:{args.port}'
    env = {**os.environ, 'AUTH_ALLOWED_ORIGINS': origin, 'FRONTEND_PORT': str(args.port),
           'API_PROXY_URL': f'http://127.0.0.1:{args.api_port}'}
    if args.isolated_auth:
        env.update(AUTH_DATABASE_URL='', AUTH_DB_PATH=str(ROOT / 'artifacts/auth/ui-preview.sqlite'),
                   AUTH_ENV='development', AUTH_SEED_DEMO='1', AUTH_COOKIE_SECURE='0', CORE_DB_DSN='')
    commands = [([sys.executable, 'apps/backend/app.py', '--port', str(args.api_port), '--no-reload'], ROOT),
                ([npm, 'run', 'dev', '--', '--strictPort'], ROOT / 'apps/frontend')]
    children = []
    try:
        for command, cwd in commands:
            children.append(subprocess.Popen(command, cwd=cwd, env=env))
        mode = 'isolated SQLite preview (Core disabled)' if args.isolated_auth else 'apps/backend/.env configuration'
        print(f'UI: {origin}\nDatabase: {mode}\nCtrl+C stops this preview.', flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(0.5)
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        for child in children:
            if child.poll() is None:
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(child.pid), '/T', '/F'], capture_output=True)
                else:
                    child.terminate()
        for child in children:
            child.wait()


if __name__ == '__main__':
    raise SystemExit(main())
