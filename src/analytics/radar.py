"""Generate 92 traceable 8-axis company radar charts."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


DB_PATH = Path("data/nifty100.db")
OUTPUT_DIR = Path("reports/radar_charts")
MANIFEST_PATH = Path("output/radar_chart_manifest.csv")
BASELINE_YEAR = "2024-03"

METRICS = [
    ("ROE", "return_on_equity_pct", True),
    ("ROCE", "return_on_capital_employed_pct", True),
    ("NPM", "net_profit_margin_pct", True),
    ("D/E", "debt_to_equity", False),
    ("FCF", "free_cash_flow_cr", True),
    ("PAT CAGR 5Y", "pat_cagr_5yr", True),
    ("Revenue CAGR 5Y", "revenue_cagr_5yr", True),
    ("EPS CAGR 5Y", "eps_cagr_5yr", True),
]


def load_data():
    """Load company, peer, and metric data for radar charts."""
    with sqlite3.connect(DB_PATH) as conn:

        companies = pd.read_sql_query(
            """
            SELECT
                c.id AS company_id,
                c.company_name,
                s.broad_sector,
                s.sub_sector
            FROM companies c
            LEFT JOIN sectors s
                ON s.company_id = c.id
            ORDER BY c.id
            """,
            conn,
        )

        peers = pd.read_sql_query(
            """
            SELECT
                peer_group_name,
                company_id,
                is_benchmark
            FROM peer_groups
            ORDER BY peer_group_name, company_id
            """,
            conn,
        )

        metric_columns = ", ".join(
            column
            for _, column, _ in METRICS
        )

        ratios = pd.read_sql_query(
            f"""
            SELECT
                company_id,
                year,
                {metric_columns}
            FROM financial_ratios
            WHERE year <> 'TTM'
            """,
            conn,
        )

    return companies, peers, ratios


def choose_company_year(
    ratios: pd.DataFrame,
    company_id: str,
) -> pd.Series:

    """Choose the best available financial year for a company."""
    rows = ratios[
        ratios["company_id"] == company_id
    ].copy()

    metric_columns = [
        column
        for _, column, _ in METRICS
    ]

    rows["available_axes"] = (
        rows[metric_columns]
        .notna()
        .sum(axis=1)
    )

    rows = rows.sort_values(
        ["available_axes", "year"],
        ascending=[False, False],
    )

    return rows.iloc[0]


def get_comparison_group(
    company_id: str,
    company_row: pd.Series,
    companies: pd.DataFrame,
    peers: pd.DataFrame,
):

    """Return the peer-comparison group for a company."""
    official = peers[
        peers["company_id"] == company_id
    ]

    if not official.empty:
        group_name = official.iloc[0][
            "peer_group_name"
        ]

        members = peers.loc[
            peers["peer_group_name"] == group_name,
            "company_id",
        ].tolist()

        return (
            "Official Peer Group",
            group_name,
            members,
        )

    sector = company_row["broad_sector"]

    members = companies.loc[
        companies["broad_sector"] == sector,
        "company_id",
    ].tolist()

    return (
        "Sector Fallback",
        sector,
        members,
    )


def reference_values(
    ratios: pd.DataFrame,
    members: list[str],
    metric: str,
    target_year: str,
):

    """Calculate reference values used for radar metrics."""
    same_year = pd.to_numeric(
        ratios.loc[
            (ratios["company_id"].isin(members))
            & (ratios["year"] == target_year),
            metric,
        ],
        errors="coerce",
    ).dropna()

    if len(same_year) >= 2:
        return same_year, target_year, False

    baseline = pd.to_numeric(
        ratios.loc[
            (ratios["company_id"].isin(members))
            & (ratios["year"] == BASELINE_YEAR),
            metric,
        ],
        errors="coerce",
    ).dropna()

    if len(baseline) >= 2:
        return baseline, BASELINE_YEAR, True

    return same_year, target_year, False


def normalise(
    value,
    reference: pd.Series,
    higher_is_better: bool,
):

    """Normalise a metric value for radar-chart comparison."""
    if pd.isna(value):
        return np.nan

    values = np.asarray(
        reference,
        dtype=float,
    )

    values = values[
        np.isfinite(values)
    ]

    if len(values) == 0:
        return np.nan

    low = float(
        np.percentile(values, 10)
    )
    high = float(
        np.percentile(values, 90)
    )

    if np.isclose(low, high):
        return 50.0

    score = (
        (float(value) - low)
        / (high - low)
    )

    score = float(
        np.clip(score, 0.0, 1.0)
    )

    if not higher_is_better:
        score = 1.0 - score

    return score * 100.0


def safe_filename(company_id: str) -> str:
    """Return a filesystem-safe filename."""
    cleaned = re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        company_id,
    )
    return f"{cleaned}.png"


def generate_chart(
    company,
    selected,
    comparison_type,
    comparison_group,
    members,
    ratios,
):

    """Generate and save a company peer-comparison radar chart."""
    labels = []
    company_scores = []
    average_scores = []
    missing_axes = []
    fallback_axes = []

    selected_year = selected["year"]

    for (
        label,
        metric,
        higher_is_better,
    ) in METRICS:

        labels.append(label)

        reference, reference_year, fallback = (
            reference_values(
                ratios,
                members,
                metric,
                selected_year,
            )
        )

        if fallback:
            fallback_axes.append(label)

        company_value = selected[metric]

        if pd.isna(company_value):
            missing_axes.append(label)

        company_score = normalise(
            company_value,
            reference,
            higher_is_better,
        )

        peer_average_raw = (
            reference.mean()
            if len(reference)
            else np.nan
        )

        average_score = normalise(
            peer_average_raw,
            reference,
            higher_is_better,
        )

        company_scores.append(
            company_score
        )

        average_scores.append(
            average_score
        )

    count = len(labels)

    angles = np.linspace(
        0,
        2 * np.pi,
        count,
        endpoint=False,
    ).tolist()

    closed_angles = (
        angles + angles[:1]
    )

    company_plot = (
        company_scores
        + company_scores[:1]
    )

    average_plot = (
        average_scores
        + average_scores[:1]
    )

    fig = plt.figure(
        figsize=(9, 8)
    )

    ax = fig.add_subplot(
        111,
        polar=True,
    )

    ax.set_ylim(0, 100)

    ax.set_yticks(
        [20, 40, 60, 80, 100]
    )

    ax.set_xticks(angles)
    ax.set_xticklabels(
        labels,
        fontsize=8,
    )

    ax.plot(
        closed_angles,
        average_plot,
        linewidth=2,
        marker="o",
        label=(
            f"{comparison_group} Average"
        ),
    )

    company_array = np.asarray(
        company_plot,
        dtype=float,
    )

    ax.plot(
        closed_angles,
        company_array,
        linewidth=2.5,
        marker="o",
        label=company["company_id"],
    )

    for angle, score in zip(
        angles,
        company_scores,
    ):
        if pd.isna(score):
            ax.text(
                angle,
                104,
                "N/A",
                ha="center",
                va="center",
                fontsize=7,
            )

    title = (
        f"{company['company_id']} — Financial Radar\n"
        f"{comparison_type}: {comparison_group} | "
        f"Company data year: {selected_year}"
    )

    ax.set_title(
        title,
        pad=28,
        fontsize=11,
    )

    if missing_axes:
        fig.text(
            0.5,
            0.025,
            "Unavailable company metrics: "
            + ", ".join(missing_axes),
            ha="center",
            fontsize=8,
        )

    ax.legend(
        loc="upper right",
        bbox_to_anchor=(1.32, 1.14),
    )

    fig.tight_layout()

    filename = safe_filename(
        company["company_id"]
    )

    output_path = (
        OUTPUT_DIR / filename
    )

    fig.savefig(
        output_path,
        dpi=180,
        bbox_inches="tight",
    )

    plt.close(fig)

    return {
        "company_id": company["company_id"],
        "company_name": company["company_name"],
        "selected_year": selected_year,
        "available_axes": int(
            selected["available_axes"]
        ),
        "comparison_type": comparison_type,
        "comparison_group": comparison_group,
        "missing_axes": ", ".join(
            missing_axes
        ),
        "reference_fallback_axes": ", ".join(
            fallback_axes
        ),
        "file": str(output_path),
    }


def main():

    """Generate radar charts for the configured company universe."""
    companies, peers, ratios = load_data()

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    MANIFEST_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Remove only previous generated radar PNGs.
    for old_file in OUTPUT_DIR.glob(
        "*.png"
    ):
        old_file.unlink()

    manifest = []

    official_count = 0
    fallback_count = 0

    for _, company in companies.iterrows():

        selected = choose_company_year(
            ratios,
            company["company_id"],
        )

        (
            comparison_type,
            comparison_group,
            members,
        ) = get_comparison_group(
            company["company_id"],
            company,
            companies,
            peers,
        )

        if comparison_type == (
            "Official Peer Group"
        ):
            official_count += 1
        else:
            fallback_count += 1

        record = generate_chart(
            company,
            selected,
            comparison_type,
            comparison_group,
            members,
            ratios,
        )

        manifest.append(record)

    manifest_df = pd.DataFrame(
        manifest
    )

    manifest_df.to_csv(
        MANIFEST_PATH,
        index=False,
    )

    png_count = len(
        list(
            OUTPUT_DIR.glob("*.png")
        )
    )

    incomplete = int(
        (
            manifest_df["available_axes"]
            < 8
        ).sum()
    )

    print(
        "Generated PNGs:",
        png_count,
    )

    print(
        "Official peer charts:",
        official_count,
    )

    print(
        "Sector fallback charts:",
        fallback_count,
    )

    print(
        "Charts with N/A company axes:",
        incomplete,
    )

    print(
        "Manifest:",
        MANIFEST_PATH.resolve(),
    )

    if png_count != 92:
        raise RuntimeError(
            f"Expected 92 PNGs, got {png_count}"
        )


if __name__ == "__main__":
    main()

