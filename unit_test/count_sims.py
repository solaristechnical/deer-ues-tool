#!/usr/bin/env python3

import sqlite3
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 2:
        print(
            "Usage: python count_sims.py <folder_containing_simdata>"
        )
        raise SystemExit(1)

    folder_path = Path(sys.argv[1])
    sqlite_path = folder_path / "simdata.sqlite"

    if not sqlite_path.exists():
        print(f"ERROR: Database not found: {sqlite_path}")
        raise SystemExit(1)

    with sqlite3.connect(sqlite_path) as conn:
        cursor = conn.execute(
            "SELECT COUNT(*) FROM sim_metadata"
        )
        row_count = cursor.fetchone()[0]

    print()
    print("========================================")
    print(f"Database : {sqlite_path}")
    print(f"Rows in sim_metadata : {row_count:,}")
    print("========================================")
    print()


if __name__ == "__main__":
    main()