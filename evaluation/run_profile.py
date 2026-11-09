"""Run a Python script with an env profile, without editing the app .env or parent shell."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', required=True, type=Path)
    parser.add_argument('script', type=Path)
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    from dotenv import dotenv_values
    environment = dict(os.environ)
    # Avoid inherited candidate settings leaking into a different model profile.
    for name in ('LLM_TEMPERATURE','LLM_TOP_P','LLM_ENABLE_THINKING'):
        environment.pop(name, None)
    for name, value in dotenv_values(args.profile).items():
        if value is not None:
            environment[name] = value
    if not args.profile.is_file() or not args.script.is_file():
        parser.error('profile and script must be readable files')
    result = subprocess.run([sys.executable, str(args.script), *args.arguments], env=environment)
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
