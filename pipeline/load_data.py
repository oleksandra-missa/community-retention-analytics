"""Download the Simple English Wikipedia history dump and load it into DuckDB.

The dump is loaded unchanged into the table `raw_events`: one row per event (an edit,
a new page, a new account, ...), all 78 columns. Cleaning happens in later steps,
so every cleaning decision stays visible and can be undone.

Usage:
    python pipeline/load_data.py
"""

import bz2
import csv
import shutil
import urllib.request
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
DB_PATH = PROJECT_ROOT / "data" / "wiki.duckdb"
COLUMNS_FILE = Path(__file__).resolve().parent / "columns.csv"

SNAPSHOT = "2026-10"
WIKI = "simplewiki"
FILE_NAME = f"{SNAPSHOT}.{WIKI}.all-time.tsv.bz2"
DUMP_URL = f"https://dumps.wikimedia.org/other/mediawiki_history/{SNAPSHOT}/{WIKI}/{FILE_NAME}"


def download_dump() -> Path:
    """Download the compressed dump (about 1 GB), unless it's already there."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    dump_path = RAW_DIR / FILE_NAME
    if dump_path.exists():
        print(f"Dump already downloaded: {dump_path.relative_to(PROJECT_ROOT)}")
        return dump_path

    print(f"Downloading {DUMP_URL} (about 1 GB) ...")
    # Download to a temporary name first, so an interrupted download is never mistaken for a complete one.
    partial_path = dump_path.with_suffix(".part")
    urllib.request.urlretrieve(DUMP_URL, partial_path)
    partial_path.rename(dump_path)
    return dump_path


def decompress(dump_path: Path) -> Path:
    """Unpack the .bz2 file into a plain TSV file that DuckDB can read.

    DuckDB can't read .bz2 files directly, so we unpack once. The TSV is large (around 10 GB)
    and is deleted after loading.
    """
    tsv_path = dump_path.with_suffix("")  # removes ".bz2"
    print(f"Decompressing to {tsv_path.name} (this takes several minutes) ...")
    with bz2.open(dump_path, "rb") as source, open(tsv_path, "wb") as target:
        shutil.copyfileobj(source, target, length=16 * 1024 * 1024)
    return tsv_path


def duckdb_type(column: str, source_type: str) -> str:
    """Translate a type from the official documentation into a DuckDB type."""
    if source_type == "boolean":
        return "BOOLEAN"
    if source_type == "bigint":
        return "BIGINT"
    if source_type == "int":
        return "INTEGER"
    # Timestamps are documented as strings, but storing them as TIMESTAMP lets us do date math in SQL.
    if column.endswith("_timestamp"):
        return "TIMESTAMP"
    # Text, and lists such as user groups or edit tags (kept as text here and split during cleaning).
    return "VARCHAR"


def read_columns() -> dict[str, str]:
    """The dump has no header row; the column names and order come from the official docs."""
    with open(COLUMNS_FILE, newline="") as f:
        return {row["column"]: duckdb_type(row["column"], row["source_type"]) for row in csv.DictReader(f)}


def load_into_duckdb(tsv_path: Path) -> None:
    """Replace the raw_events table with the contents of the TSV file."""
    with duckdb.connect(str(DB_PATH)) as con:
        print("Loading into DuckDB ...")
        con.execute(
            """
            CREATE OR REPLACE TABLE raw_events AS
            SELECT * FROM read_csv(
                ?,
                delim = '\t',
                header = false,
                quote = '',   -- the dump doesn't quote values; quotes inside comments are ordinary text
                escape = '',
                columns = ?
            )
            """,
            [str(tsv_path), read_columns()],
        )
        print(f"\nLoaded into {DB_PATH.relative_to(PROJECT_ROOT)}, table raw_events")
        print_summary(con)


def print_summary(con: duckdb.DuckDBPyConnection) -> None:
    """Print a first look at the data, for checking the load."""
    print(con.sql("SELECT COUNT(*) AS total_rows, MIN(event_timestamp) AS first_event, "
                  "MAX(event_timestamp) AS last_event FROM raw_events"))
    print(con.sql(
        """
        SELECT event_entity, event_type, COUNT(*) AS events
        FROM raw_events
        GROUP BY ALL
        ORDER BY events DESC
        """
    ))


if __name__ == "__main__":
    tsv = decompress(download_dump())
    try:
        load_into_duckdb(tsv)
    finally:
        tsv.unlink()  # the compressed dump stays; the large unpacked copy isn't needed any more
