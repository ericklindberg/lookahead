"""Create fictional demo tables. Does not configure, register or schedule anything."""
import argparse
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--now',help='Aware ISO instant; defaults to the current UTC time.')
    args = parser.parse_args()
    now = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        parser.error('--now must be timezone-aware')
    args.output.mkdir(parents=True,exist_ok=True)
    tables = {'agenda.md':'| id | at | title | readiness_key |\n| --- | --- | --- | --- |\n'
              f'| orbital-demo | {(now+timedelta(minutes=12)).isoformat()} | Orbital demo | deck |\n',
              'readiness.md':'| key | status | detail |\n| --- | --- | --- |\n| deck | not_ready | Deck unfinished |\n'}
    for name,content in tables.items():
        path = args.output/name
        # Refuse existing files, including symlinks; generation never overwrites user data.
        with path.open('x',encoding='utf-8') as handle:
            handle.write(content)
        os.utime(path,(now.timestamp(),now.timestamp()))


if __name__ == '__main__':
    main()
