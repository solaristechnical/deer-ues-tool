import os
import sqlite3
import argparse
from pathlib import Path

# ============================================================================
# USER INPUTS
# ============================================================================
parser = argparse.ArgumentParser(
    description="Validate the generated simdata.sqlite database."
)

parser.add_argument(
    "folder_path",
    type=Path,
    help="Folder containing simdata.sqlite",
)

parser.add_argument(
    "expected_permutations",
    type=int,
    help="Expected number of simulation permutations",
)

args = parser.parse_args()

FOLDER_PATH = args.folder_path.resolve()
EXPECTED_PERMUTATIONS = args.expected_permutations

if not FOLDER_PATH.exists():
    raise SystemExit(
        f"Folder does not exist: {FOLDER_PATH}"
    )

SQLITE_FILENAME = "simdata.sqlite"

# ============================================================================
# EXPECTED TABLE CONFIGURATION
# ============================================================================

# Number of rows expected per permutation in each table (based on result3.py)
TABLE_REQUIREMENTS = {
    "sim_data": 30,
    "sim_deerpeak": 3,
    "sim_hourly": 14,
    "sim_metadata": 1,
}

# ============================================================================
# MAIN
# ============================================================================

sqlite_path = FOLDER_PATH / SQLITE_FILENAME

print(f"\nStep 1: Looking for {SQLITE_FILENAME}...")

if not os.path.isfile(sqlite_path):
    print(f"ERROR: File not found:\n  {sqlite_path}")
    raise SystemExit(1)

print(f"SUCCESS: Found SQLite file:\n  {sqlite_path}")

print("\nStep 2: Opening database...")

try:
    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()
    print("SUCCESS: Database opened.")
except Exception as e:
    print(f"ERROR: Could not open database: {e}")
    raise SystemExit(1)

print("\nStep 3: Checking required tables...")

cursor.execute("""
SELECT name
FROM sqlite_master
WHERE type='table'
""")

existing_tables = {row[0] for row in cursor.fetchall()}

all_tables_found = True

for table_name in TABLE_REQUIREMENTS:
    if table_name in existing_tables:
        print(f"  FOUND: {table_name}")
    else:
        print(f"  MISSING: {table_name}")
        all_tables_found = False

if not all_tables_found:
    print("\nERROR: One or more required tables are missing.")
    conn.close()
    raise SystemExit(1)

print("\nSUCCESS: All required tables found.")

print("\nStep 4: Validating row counts...")

for table_name, rows_per_permutation in TABLE_REQUIREMENTS.items():

    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    actual_rows = cursor.fetchone()[0]

    expected_rows = EXPECTED_PERMUTATIONS * rows_per_permutation

    if actual_rows % rows_per_permutation != 0:
        print(
            f"STATUS: FAIL - {table_name} has {actual_rows:,} rows, "
            f"which is not divisible by {rows_per_permutation}"
        )
        raise SystemExit(1)

    derived_permutations = actual_rows // rows_per_permutation

    print("\n" + "-" * 50)
    print(f"Table: {table_name}")
    print(f"Expected row count        : {expected_rows:,}")
    print(f"Rows found                : {actual_rows:,}")
    print(f"Rows per permutation      : {rows_per_permutation}")
    print(f"Expected permutations     : {EXPECTED_PERMUTATIONS}")
    print(f"Permutations found        : {derived_permutations:,}")

    if actual_rows == expected_rows:
        print("STATUS: PASS")

    else:
        print("STATUS: FAIL")
        print(f"  Expected {expected_rows:,} rows")
        print(f"  Found    {actual_rows:,} rows")
        raise SystemExit(1)

print("\nSUCCESS: All table row counts match expected values.")

conn.close()
print("\nDatabase connection closed.")