"""Data quality validator for the N100 ETL pipeline."""

import argparse
import logging
import re
from pathlib import Path

import pandas as pd
import requests

from src.etl.loader import load_all_core_datasets


logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "output"
FAILURE_FILE = OUTPUT_DIR / "validation_failures.csv"

YEAR_PATTERN = re.compile(r"^\d{4}-\d{2}$")


def add_failure(
    failures: list[dict[str, object]],
    rule_id: str,
    dataset: str,
    company_id: object,
    year: object,
    field: str,
    issue: str,
    severity: str,
) -> None:
    """Append one validation failure."""

    failures.append(
        {
            "rule_id": rule_id,
            "dataset": dataset,
            "company_id": company_id,
            "year": year,
            "field": field,
            "issue": issue,
            "severity": severity,
        }
    )


def numeric(series: pd.Series) -> pd.Series:
    """Convert values to numeric."""

    return pd.to_numeric(series, errors="coerce")


def validate_dq01(
    datasets: dict[str, pd.DataFrame],
    failures: list[dict[str, object]],
) -> None:
    """DQ-01: Company primary key uniqueness."""

    df = datasets["companies"]

    duplicate_mask = df["id"].duplicated(keep=False)

    for _, row in df.loc[duplicate_mask].iterrows():
        add_failure(
            failures,
            "DQ-01",
            "companies",
            row["id"],
            "",
            "id",
            "Duplicate company primary key",
            "CRITICAL",
        )


def validate_dq02(
    datasets: dict[str, pd.DataFrame],
    failures: list[dict[str, object]],
) -> None:
    """DQ-02: Annual primary key uniqueness."""

    for dataset_name in (
        "profitandloss",
        "balancesheet",
        "cashflow",
    ):
        df = datasets[dataset_name]

        duplicate_mask = df.duplicated(
            subset=["company_id", "year"],
            keep=False,
        )

        for _, row in df.loc[duplicate_mask].iterrows():
            add_failure(
                failures,
                "DQ-02",
                dataset_name,
                row["company_id"],
                row["year"],
                "company_id,year",
                "Duplicate company_id/year combination",
                "CRITICAL",
            )


def validate_dq03(
    datasets: dict[str, pd.DataFrame],
    failures: list[dict[str, object]],
) -> None:
    """DQ-03: Foreign key integrity."""

    valid_ids = set(datasets["companies"]["id"].dropna())

    for dataset_name in (
        "profitandloss",
        "balancesheet",
        "cashflow",
        "analysis",
        "documents",
        "prosandcons",
    ):
        df = datasets[dataset_name]

        if "company_id" not in df.columns:
            continue

        invalid_rows = df[~df["company_id"].isin(valid_ids)]

        for _, row in invalid_rows.iterrows():
            year = row.get("year", row.get("Year", ""))

            add_failure(
                failures,
                "DQ-03",
                dataset_name,
                row["company_id"],
                year,
                "company_id",
                "company_id not found in companies table",
                "CRITICAL",
            )


def validate_dq04(
    datasets: dict[str, pd.DataFrame],
    failures: list[dict[str, object]],
) -> None:
    """DQ-04: Balance sheet balance check."""

    df = datasets["balancesheet"]

    assets = numeric(df["total_assets"])
    liabilities = numeric(df["total_liabilities"])

    ratio = (
        (assets - liabilities).abs()
        / assets.abs().replace(0, pd.NA)
    )

    invalid_mask = ratio >= 0.01

    for index, row in df.loc[invalid_mask].iterrows():
        add_failure(
            failures,
            "DQ-04",
            "balancesheet",
            row["company_id"],
            row["year"],
            "total_assets,total_liabilities",
            f"Balance sheet mismatch ratio={ratio.loc[index]:.4f}",
            "WARNING",
        )


def validate_dq05(
    datasets: dict[str, pd.DataFrame],
    failures: list[dict[str, object]],
) -> None:
    """DQ-05: OPM cross-check."""

    df = datasets["profitandloss"]

    sales = numeric(df["sales"])
    operating_profit = numeric(df["operating_profit"])
    source_opm = numeric(df["opm_percentage"])

    computed_opm = (
        operating_profit
        / sales.replace(0, pd.NA)
        * 100
    )

    difference = (source_opm - computed_opm).abs()

    invalid_mask = difference >= 1.0

    for index, row in df.loc[invalid_mask].iterrows():
        add_failure(
            failures,
            "DQ-05",
            "profitandloss",
            row["company_id"],
            row["year"],
            "opm_percentage",
            f"OPM difference={difference.loc[index]:.2f}",
            "WARNING",
        )


def validate_dq06(
    datasets: dict[str, pd.DataFrame],
    failures: list[dict[str, object]],
) -> None:
    """DQ-06: Sales must be positive."""

    df = datasets["profitandloss"]
    sales = numeric(df["sales"])

    invalid_mask = sales <= 0

    for _, row in df.loc[invalid_mask].iterrows():
        add_failure(
            failures,
            "DQ-06",
            "profitandloss",
            row["company_id"],
            row["year"],
            "sales",
            f"Sales must be positive: {row['sales']}",
            "WARNING",
        )


def validate_dq07(
    datasets: dict[str, pd.DataFrame],
    failures: list[dict[str, object]],
) -> None:
    """DQ-07: Year format check."""

    for dataset_name in (
        "profitandloss",
        "balancesheet",
        "cashflow",
    ):
        df = datasets[dataset_name]

        for _, row in df.iterrows():
            year = str(row["year"]).strip()

            if year == "TTM":
                continue

            if not YEAR_PATTERN.fullmatch(year):
                add_failure(
                    failures,
                    "DQ-07",
                    dataset_name,
                    row["company_id"],
                    year,
                    "year",
                    f"Invalid year format: {year}",
                    "CRITICAL",
                )


def validate_dq08(
    datasets: dict[str, pd.DataFrame],
    failures: list[dict[str, object]],
) -> None:
    """DQ-08: Ticker format check."""

    for dataset_name in (
        "profitandloss",
        "balancesheet",
        "cashflow",
        "analysis",
        "documents",
        "prosandcons",
    ):
        df = datasets[dataset_name]

        if "company_id" not in df.columns:
            continue

        for _, row in df.iterrows():
            ticker = str(row["company_id"])

            valid = (
                ticker == ticker.strip()
                and ticker == ticker.upper()
                and 2 <= len(ticker) <= 12
            )

            if not valid:
                year = row.get("year", row.get("Year", ""))

                add_failure(
                    failures,
                    "DQ-08",
                    dataset_name,
                    ticker,
                    year,
                    "company_id",
                    f"Invalid ticker: {ticker}",
                    "CRITICAL",
                )


def validate_dq09(
    datasets: dict[str, pd.DataFrame],
    failures: list[dict[str, object]],
) -> None:
    """DQ-09: Net cash check."""

    df = datasets["cashflow"]

    operating = numeric(df["operating_activity"])
    investing = numeric(df["investing_activity"])
    financing = numeric(df["financing_activity"])
    net_cash = numeric(df["net_cash_flow"])

    computed = operating + investing + financing

    difference = (net_cash - computed).abs()

    invalid_mask = difference > 10

    for index, row in df.loc[invalid_mask].iterrows():
        add_failure(
            failures,
            "DQ-09",
            "cashflow",
            row["company_id"],
            row["year"],
            "net_cash_flow",
            f"Cash flow mismatch={difference.loc[index]:.2f}",
            "WARNING",
        )


def validate_dq10(
    datasets: dict[str, pd.DataFrame],
    failures: list[dict[str, object]],
) -> None:
    """DQ-10: Non-negative fixed assets."""

    df = datasets["balancesheet"]
    values = numeric(df["fixed_assets"])

    invalid_mask = values < 0

    for _, row in df.loc[invalid_mask].iterrows():
        add_failure(
            failures,
            "DQ-10",
            "balancesheet",
            row["company_id"],
            row["year"],
            "fixed_assets",
            f"Negative fixed assets: {row['fixed_assets']}",
            "WARNING",
        )


def validate_dq11(
    datasets: dict[str, pd.DataFrame],
    failures: list[dict[str, object]],
) -> None:
    """DQ-11: Tax rate range."""

    df = datasets["profitandloss"]
    values = numeric(df["tax_percentage"])

    invalid_mask = (values < 0) | (values > 60)

    for _, row in df.loc[invalid_mask].iterrows():
        add_failure(
            failures,
            "DQ-11",
            "profitandloss",
            row["company_id"],
            row["year"],
            "tax_percentage",
            f"Tax percentage outside 0-60: {row['tax_percentage']}",
            "WARNING",
        )


def validate_dq12(
    datasets: dict[str, pd.DataFrame],
    failures: list[dict[str, object]],
) -> None:
    """DQ-12: Dividend payout cap."""

    df = datasets["profitandloss"]
    values = numeric(df["dividend_payout"])

    invalid_mask = values > 200

    for _, row in df.loc[invalid_mask].iterrows():
        add_failure(
            failures,
            "DQ-12",
            "profitandloss",
            row["company_id"],
            row["year"],
            "dividend_payout",
            f"Dividend payout exceeds 200: {row['dividend_payout']}",
            "WARNING",
        )


def validate_dq13(
    datasets: dict[str, pd.DataFrame],
    failures: list[dict[str, object]],
    check_urls: bool,
) -> None:
    """DQ-13: Annual report URL validity."""

    if not check_urls:
        logger.info(
            "DQ-13 URL checks skipped. Use --check-urls to enable."
        )
        return

    df = datasets["documents"]

    for _, row in df.iterrows():
        url = row.get("Annual_Report")

        if pd.isna(url) or not str(url).strip():
            continue

        try:
            response = requests.head(
                str(url).strip(),
                allow_redirects=True,
                timeout=5,
            )

            if response.status_code != 200:
                add_failure(
                    failures,
                    "DQ-13",
                    "documents",
                    row["company_id"],
                    row.get("Year", ""),
                    "Annual_Report",
                    f"HTTP status={response.status_code}",
                    "WARNING",
                )

        except requests.RequestException as error:
            add_failure(
                failures,
                "DQ-13",
                "documents",
                row["company_id"],
                row.get("Year", ""),
                "Annual_Report",
                f"URL request failed: {error}",
                "WARNING",
            )


def validate_dq14(
    datasets: dict[str, pd.DataFrame],
    failures: list[dict[str, object]],
) -> None:
    """DQ-14: EPS sign consistency."""

    df = datasets["profitandloss"]

    net_profit = numeric(df["net_profit"])
    eps = numeric(df["eps"])

    invalid_mask = (net_profit > 0) & ((eps <= 0) | eps.isna())

    for _, row in df.loc[invalid_mask].iterrows():
        add_failure(
            failures,
            "DQ-14",
            "profitandloss",
            row["company_id"],
            row["year"],
            "eps",
            (
                f"Positive net profit={row['net_profit']} "
                f"but EPS={row['eps']}"
            ),
            "WARNING",
        )


def validate_dq15(
    datasets: dict[str, pd.DataFrame],
    failures: list[dict[str, object]],
) -> None:
    """DQ-15: Strict balance informational check."""

    df = datasets["balancesheet"]

    assets = numeric(df["total_assets"])
    liabilities = numeric(df["total_liabilities"])

    invalid_mask = assets != liabilities

    for _, row in df.loc[invalid_mask].iterrows():
        add_failure(
            failures,
            "DQ-15",
            "balancesheet",
            row["company_id"],
            row["year"],
            "total_assets,total_liabilities",
            (
                f"assets={row['total_assets']}, "
                f"liabilities={row['total_liabilities']}"
            ),
            "INFO",
        )


def validate_dq16(
    datasets: dict[str, pd.DataFrame],
    failures: list[dict[str, object]],
) -> None:
    """DQ-16: Minimum five-year history."""

    company_ids = datasets["companies"]["id"].tolist()

    for dataset_name in (
        "profitandloss",
        "balancesheet",
        "cashflow",
    ):
        df = datasets[dataset_name]

        valid_year_rows = df[df["year"] != "TTM"]

        coverage = (
            valid_year_rows.groupby("company_id")["year"]
            .nunique()
            .to_dict()
        )

        for company_id in company_ids:
            years = int(coverage.get(company_id, 0))

            if years < 5:
                add_failure(
                    failures,
                    "DQ-16",
                    dataset_name,
                    company_id,
                    "",
                    "year",
                    f"Only {years} years available; minimum is 5",
                    "WARNING",
                )


def validate_all(
    datasets: dict[str, pd.DataFrame],
    check_urls: bool = False,
) -> pd.DataFrame:
    """Run all 16 data-quality rules."""

    failures: list[dict[str, object]] = []

    validate_dq01(datasets, failures)
    validate_dq02(datasets, failures)
    validate_dq03(datasets, failures)
    validate_dq04(datasets, failures)
    validate_dq05(datasets, failures)
    validate_dq06(datasets, failures)
    validate_dq07(datasets, failures)
    validate_dq08(datasets, failures)
    validate_dq09(datasets, failures)
    validate_dq10(datasets, failures)
    validate_dq11(datasets, failures)
    validate_dq12(datasets, failures)
    validate_dq13(datasets, failures, check_urls)
    validate_dq14(datasets, failures)
    validate_dq15(datasets, failures)
    validate_dq16(datasets, failures)

    columns = [
        "rule_id",
        "dataset",
        "company_id",
        "year",
        "field",
        "issue",
        "severity",
    ]

    return pd.DataFrame(
        failures,
        columns=columns,
    )


def main() -> None:
    """Run N100 validation workflow."""

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--check-urls",
        action="store_true",
        help="Enable DQ-13 annual report URL checks.",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(message)s",
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    logger.info("Loading all 7 core datasets...")

    datasets = load_all_core_datasets()

    logger.info("Running DQ-01 through DQ-16...")

    failures = validate_all(
        datasets,
        check_urls=args.check_urls,
    )

    failures.to_csv(
        FAILURE_FILE,
        index=False,
    )

    if failures.empty:
        logger.info("Validation completed with 0 failures.")
    else:
        summary = (
            failures.groupby("severity")
            .size()
            .to_dict()
        )

        logger.info(
            "Validation completed. Total failures=%d Summary=%s",
            len(failures),
            summary,
        )

    logger.info(
        "Saved validation report: %s",
        FAILURE_FILE,
    )


if __name__ == "__main__":
    main()