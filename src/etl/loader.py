from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from src.etl.normaliser import normalize_ticker, normalize_year


logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"

CORE_FILES = {
    "companies": "companies.xlsx",
    "profitandloss": "profitandloss.xlsx",
    "balancesheet": "balancesheet.xlsx",
    "cashflow": "cashflow.xlsx",
    "analysis": "analysis.xlsx",
    "documents": "documents.xlsx",
    "prosandcons": "prosandcons.xlsx",
}

ANNUAL_DATASETS = {
    "profitandloss",
    "balancesheet",
    "cashflow",
}


def load_excel(path: Path) -> pd.DataFrame:
    """Load one core Excel dataset using row 1 as the header."""

    if not path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {path}"
        )

    df = pd.read_excel(
        path,
        header=1,
    )

    df = df.dropna(
        how="all"
    ).copy()

    df.columns = [
        str(column).strip()
        for column in df.columns
    ]

    return df


def normalise_dataframe(
    dataframe: pd.DataFrame,
    dataset_name: str,
) -> pd.DataFrame:
    """Apply common field normalisation rules."""

    df = dataframe.copy()

    # Company master ticker
    if (
        dataset_name == "companies"
        and "id" in df.columns
    ):
        df["id"] = df["id"].apply(
            normalize_ticker
        )

    # Child table ticker
    if "company_id" in df.columns:

        df["company_id"] = df[
            "company_id"
        ].apply(
            normalize_ticker
        )

        # Verified source typo:
        # cashflow.xlsx uses AGTL for
        # Adani Total Gas Ltd.
        # Correct NSE ticker is ATGL.
        if dataset_name == "cashflow":

            typo_mask = (
                df["company_id"] == "AGTL"
            )

            corrected = int(
                typo_mask.sum()
            )

            if corrected > 0:

                logger.warning(
                    "Source correction | cashflow | "
                    "AGTL -> ATGL | %d rows",
                    corrected,
                )

                df.loc[
                    typo_mask,
                    "company_id",
                ] = "ATGL"

    # Financial year
    if "year" in df.columns:

        df["year"] = df[
            "year"
        ].apply(
            normalize_year
        )

    # Documents has capital-Y Year
    if (
        dataset_name == "documents"
        and "Year" in df.columns
    ):

        df["Year"] = pd.to_numeric(
            df["Year"],
            errors="raise",
        ).astype(int)

    # Clean company names
    if (
        dataset_name == "companies"
        and "company_name" in df.columns
    ):

        df["company_name"] = (
            df["company_name"]
            .astype(str)
            .str.replace(
                r"\s+",
                " ",
                regex=True,
            )
            .str.strip()
        )

    return df


def deduplicate_dataset(
    dataframe: pd.DataFrame,
    dataset_name: str,
) -> pd.DataFrame:
    """Remove duplicate company/year rows, keeping last occurrence."""

    df = dataframe.copy()

    if dataset_name not in ANNUAL_DATASETS:
        return df

    if not {
        "company_id",
        "year",
    }.issubset(df.columns):
        return df

    before = len(df)

    df = df.drop_duplicates(
        subset=[
            "company_id",
            "year",
        ],
        keep="last",
    ).copy()

    removed = (
        before - len(df)
    )

    if removed > 0:

        logger.warning(
            "DQ-02 | %-15s removed %d duplicate rows",
            dataset_name,
            removed,
        )

    return df


def remove_orphan_rows(
    dataframe: pd.DataFrame,
    dataset_name: str,
    valid_company_ids: set[str],
) -> pd.DataFrame:
    """Reject company IDs not present in companies master."""

    if "company_id" not in dataframe.columns:
        return dataframe

    df = dataframe.copy()

    orphan_mask = ~df[
        "company_id"
    ].isin(
        valid_company_ids
    )

    rejected = int(
        orphan_mask.sum()
    )

    if rejected > 0:

        orphan_ids = sorted(
            df.loc[
                orphan_mask,
                "company_id",
            ]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

        logger.warning(
            "DQ-03 | %-15s rejected %d orphan rows | %s",
            dataset_name,
            rejected,
            ", ".join(orphan_ids),
        )

    return df.loc[
        ~orphan_mask
    ].copy()


def load_core_dataset(
    dataset_name: str,
) -> pd.DataFrame:
    """Load and normalise one core dataset."""

    if dataset_name not in CORE_FILES:

        raise ValueError(
            f"Unknown core dataset: {dataset_name}"
        )

    path = (
        RAW_DIR
        / CORE_FILES[dataset_name]
    )

    dataframe = load_excel(
        path
    )

    return normalise_dataframe(
        dataframe,
        dataset_name,
    )


def load_all_core_datasets(
    clean: bool = True,
) -> dict[str, pd.DataFrame]:
    """Load all seven core datasets."""

    datasets: dict[
        str,
        pd.DataFrame,
    ] = {}

    # Load companies first
    companies = load_core_dataset(
        "companies"
    )

    datasets[
        "companies"
    ] = companies

    valid_company_ids = set(
        companies[
            "id"
        ]
        .dropna()
        .astype(str)
    )

    logger.info(
        "Loaded %-15s rows=%d columns=%d",
        "companies",
        len(companies),
        len(companies.columns),
    )

    # Load remaining datasets
    for dataset_name in CORE_FILES:

        if dataset_name == "companies":
            continue

        dataframe = load_core_dataset(
            dataset_name
        )

        rows_in = len(
            dataframe
        )

        if clean:

            dataframe = deduplicate_dataset(
                dataframe,
                dataset_name,
            )

            dataframe = remove_orphan_rows(
                dataframe,
                dataset_name,
                valid_company_ids,
            )

        datasets[
            dataset_name
        ] = dataframe

        logger.info(
            "Loaded %-15s rows_in=%d rows_out=%d columns=%d",
            dataset_name,
            rows_in,
            len(dataframe),
            len(dataframe.columns),
        )

    return datasets


# Compatibility alias
normalize_dataframe = normalise_dataframe


if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(message)s",
    )

    datasets = load_all_core_datasets(
        clean=True
    )

    print("\n=== CORE DATASETS ===")

    for name, dataframe in datasets.items():

        print(
            f"{name:15s} {len(dataframe):5d} rows"
        )
