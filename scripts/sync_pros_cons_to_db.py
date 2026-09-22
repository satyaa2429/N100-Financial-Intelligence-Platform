from pathlib import Path
from itertools import zip_longest
import shutil
import sqlite3
import pandas as pd


ROOT = Path.cwd()

DB = ROOT / "data" / "nifty100.db"
CSV = ROOT / "output" / "pros_cons_generated.csv"
BACKUP = ROOT / "data" / "nifty100_before_full_pros_cons_sync.db"


print("=== PROS / CONS DATABASE SYNC ===")
print("Database:", DB)
print("Source CSV:", CSV)


# ------------------------------------------------------------
# Validate files
# ------------------------------------------------------------

if not DB.exists():
    raise FileNotFoundError(
        f"Database not found: {DB}"
    )

if not CSV.exists():
    raise FileNotFoundError(
        f"CSV not found: {CSV}"
    )


# ------------------------------------------------------------
# Backup database
# ------------------------------------------------------------

shutil.copy2(
    DB,
    BACKUP,
)

print("Backup created:", BACKUP)


# ------------------------------------------------------------
# Read final generated Pros / Cons
# ------------------------------------------------------------

df = pd.read_csv(CSV)

required_columns = {
    "company_id",
    "type",
    "text",
}

missing_columns = required_columns - set(df.columns)

if missing_columns:
    raise RuntimeError(
        f"CSV missing required columns: {missing_columns}"
    )


df["company_id"] = (
    df["company_id"]
    .astype(str)
    .str.strip()
    .str.upper()
)

df["type"] = (
    df["type"]
    .astype(str)
    .str.strip()
    .str.lower()
)

df["text"] = (
    df["text"]
    .fillna("")
    .astype(str)
    .str.strip()
)

# Keep only real Pros and Cons
df = df[
    df["type"].isin(["pro", "con"])
    & (df["text"] != "")
].copy()


print()
print("CSV rows:", len(df))
print("CSV companies:", df["company_id"].nunique())
print(
    "Pros:",
    (df["type"] == "pro").sum()
)
print(
    "Cons:",
    (df["type"] == "con").sum()
)


# ------------------------------------------------------------
# Update SQLite
# ------------------------------------------------------------

with sqlite3.connect(DB) as con:

    table_columns = [
        row[1]
        for row in con.execute(
            "PRAGMA table_info(prosandcons)"
        ).fetchall()
    ]

    print()
    print(
        "Database prosandcons columns:",
        table_columns,
    )

    required_db_columns = {
        "company_id",
        "pros",
        "cons",
    }

    if not required_db_columns.issubset(
        set(table_columns)
    ):
        raise RuntimeError(
            "Unexpected prosandcons table structure: "
            + str(table_columns)
        )

    # Remove old incomplete data
    con.execute(
        "DELETE FROM prosandcons"
    )

    inserted = 0

    for company_id, company_df in df.groupby(
        "company_id"
    ):

        pros = (
            company_df.loc[
                company_df["type"] == "pro",
                "text",
            ]
            .tolist()
        )

        cons = (
            company_df.loc[
                company_df["type"] == "con",
                "text",
            ]
            .tolist()
        )

        for pro, con_item in zip_longest(
            pros,
            cons,
            fillvalue=None,
        ):

            con.execute(
                """
                INSERT INTO prosandcons
                    (company_id, pros, cons)
                VALUES (?, ?, ?)
                """,
                (
                    company_id,
                    pro,
                    con_item,
                ),
            )

            inserted += 1

    con.commit()


# ------------------------------------------------------------
# Final verification
# ------------------------------------------------------------

with sqlite3.connect(DB) as con:

    total_rows = con.execute(
        """
        SELECT COUNT(*)
        FROM prosandcons
        """
    ).fetchone()[0]

    company_count = con.execute(
        """
        SELECT COUNT(DISTINCT company_id)
        FROM prosandcons
        """
    ).fetchone()[0]

    incomplete = con.execute(
        """
        SELECT
            company_id
        FROM prosandcons
        GROUP BY company_id
        HAVING
            SUM(
                CASE
                    WHEN pros IS NOT NULL
                     AND TRIM(pros) <> ''
                    THEN 1
                    ELSE 0
                END
            ) = 0
        OR
            SUM(
                CASE
                    WHEN cons IS NOT NULL
                     AND TRIM(cons) <> ''
                    THEN 1
                    ELSE 0
                END
            ) = 0
        ORDER BY company_id
        """
    ).fetchall()


print()
print("=== SYNC COMPLETE ===")
print("Inserted rows:", inserted)
print("Database rows:", total_rows)
print("Companies:", company_count)
print("Incomplete companies:", len(incomplete))

if incomplete:
    print(
        "Incomplete:",
        [x[0] for x in incomplete]
    )
else:
    print(
        "SUCCESS: All 92 companies have "
        "at least one Pro and one Con."
    )
