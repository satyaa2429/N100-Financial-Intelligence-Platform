"""Robust KMeans clustering and statistical analysis for Nifty 100."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DB_PATH = PROJECT_ROOT / "data" / "nifty100.db"

CASHFLOW_FILE = (
    PROJECT_ROOT
    / "output"
    / "cashflow_intelligence.xlsx"
)

OUTPUT_DIR = PROJECT_ROOT / "output"

CLUSTER_DIR = (
    OUTPUT_DIR
    / "clustering"
)

CLUSTER_FILE = (
    OUTPUT_DIR
    / "cluster_labels.csv"
)

PROFILE_FILE = (
    CLUSTER_DIR
    / "cluster_profiles.csv"
)

DQ_FILE = (
    CLUSTER_DIR
    / "clustering_data_quality.csv"
)

ELBOW_FILE = (
    CLUSTER_DIR
    / "elbow_plot.png"
)

HEATMAP_FILE = (
    CLUSTER_DIR
    / "correlation_heatmap.png"
)

STATS_FILE = (
    CLUSTER_DIR
    / "portfolio_stats.csv"
)

OUTLIER_FILE = (
    CLUSTER_DIR
    / "outlier_report.csv"
)


# ============================================================
# MODEL CONFIGURATION
# ============================================================

CLUSTER_FEATURES = [
    "roe",
    "debt_to_equity",
    "revenue_cagr_5yr",
    "fcf_cagr_5yr",
    "opm",
]


CORRELATION_METRICS = [
    "roe",
    "roce",
    "npm",
    "opm",
    "debt_to_equity",
    "revenue_cagr_5yr",
    "pat_cagr_5yr",
    "eps_cagr_5yr",
    "free_cash_flow_cr",
    "cfo_pat_ratio",
]


PORTFOLIO_STATS_METRICS = [
    "roe",
    "debt_to_equity",
    "pe_ratio",
    "roce",
    "npm",
    "opm",
    "revenue_cagr_5yr",
    "pat_cagr_5yr",
    "eps_cagr_5yr",
    "free_cash_flow_cr",
]


# ============================================================
# DATA LOADING
# ============================================================

def load_latest_data() -> pd.DataFrame:
    """Load latest financial data for all 92 companies."""

    query = """
        SELECT
            c.id AS company_id,
            c.company_name,
            c.roe_percentage AS source_roe,

            COALESCE(
                s.broad_sector,
                'Not Available'
            ) AS broad_sector,

            r.year,

            r.return_on_equity_pct AS roe,
            r.return_on_capital_employed_pct AS roce,
            r.net_profit_margin_pct AS npm,
            r.operating_profit_margin_pct AS opm,

            r.debt_to_equity,

            r.revenue_cagr_5yr,
            r.pat_cagr_5yr,
            r.eps_cagr_5yr,

            r.free_cash_flow_cr,
            r.cfo_pat_ratio,

            m.pe_ratio,
            m.pb_ratio,
            m.dividend_yield_pct

        FROM companies c

        LEFT JOIN sectors s
            ON s.company_id = c.id

        LEFT JOIN financial_ratios r
            ON r.company_id = c.id
           AND r.year = (
                SELECT MAX(fr.year)
                FROM financial_ratios fr
                WHERE fr.company_id = c.id
                  AND fr.year <> 'TTM'
           )

        LEFT JOIN market_cap m
            ON m.company_id = c.id
           AND m.year = (
                SELECT MAX(mc.year)
                FROM market_cap mc
                WHERE mc.company_id = c.id
           )

        ORDER BY c.id
    """

    with sqlite3.connect(
        DB_PATH
    ) as conn:

        frame = pd.read_sql_query(
            query,
            conn,
        )

    return frame


def load_fcf_cagr() -> pd.DataFrame:
    """Load five-year FCF CAGR from cash-flow intelligence."""

    if not CASHFLOW_FILE.exists():

        return pd.DataFrame(
            columns=[
                "company_id",
                "fcf_cagr_5yr",
            ]
        )

    sheets = pd.read_excel(
        CASHFLOW_FILE,
        sheet_name=None,
    )

    for frame in sheets.values():

        required = {
            "company_id",
            "fcf_cagr_5yr_pct",
        }

        if not required.issubset(
            frame.columns
        ):
            continue

        result = frame[
            [
                "company_id",
                "fcf_cagr_5yr_pct",
            ]
        ].copy()

        result = result.rename(
            columns={
                "fcf_cagr_5yr_pct":
                    "fcf_cagr_5yr",
            }
        )

        result["company_id"] = (
            result["company_id"]
            .astype(str)
            .str.strip()
            .str.upper()
        )

        result = (
            result.drop_duplicates(
                subset=[
                    "company_id",
                ],
                keep="last",
            )
        )

        return result

    return pd.DataFrame(
        columns=[
            "company_id",
            "fcf_cagr_5yr",
        ]
    )


def prepare_raw_data() -> pd.DataFrame:
    """Merge database and cash-flow intelligence data."""

    data = load_latest_data()

    data["company_id"] = (
        data["company_id"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    fcf_data = load_fcf_cagr()

    data = data.merge(
        fcf_data,
        on="company_id",
        how="left",
    )

    numeric_columns = [
        "source_roe",
        "roe",
        "roce",
        "npm",
        "opm",
        "debt_to_equity",
        "revenue_cagr_5yr",
        "pat_cagr_5yr",
        "eps_cagr_5yr",
        "free_cash_flow_cr",
        "cfo_pat_ratio",
        "fcf_cagr_5yr",
        "pe_ratio",
        "pb_ratio",
        "dividend_yield_pct",
    ]

    for column in numeric_columns:

        data[column] = pd.to_numeric(
            data[column],
            errors="coerce",
        )

    return data


# ============================================================
# DATA QUALITY CORRECTION FOR ML
# ============================================================

def repair_roe_for_model(
    data: pd.DataFrame,
) -> tuple[pd.DataFrame, list[dict]]:
    """Repair extreme ROE only for clustering input."""

    result = data.copy()

    notes: list[dict] = []

    result["raw_roe"] = (
        result["roe"]
    )

    anomaly_mask = (
        result["roe"].abs()
        > 200
    )

    for index in result[
        anomaly_mask
    ].index:

        ticker = result.loc[
            index,
            "company_id",
        ]

        raw_value = result.loc[
            index,
            "roe",
        ]

        source_value = result.loc[
            index,
            "source_roe",
        ]

        if (
            pd.notna(source_value)
            and -100
            <= source_value
            <= 200
        ):

            result.loc[
                index,
                "roe",
            ] = source_value

            replacement = (
                source_value
            )

            method = (
                "source_roe_fallback"
            )

        else:

            result.loc[
                index,
                "roe",
            ] = np.nan

            replacement = np.nan

            method = (
                "sector_median_imputation"
            )

        notes.append(
            {
                "company_id": ticker,
                "feature": "roe",
                "raw_value": raw_value,
                "replacement_value":
                    replacement,
                "reason":
                    "Computed ROE exceeded "
                    "absolute 200% ML threshold",
                "method": method,
            }
        )

    return result, notes


def prepare_model_features(
    data: pd.DataFrame,
    notes: list[dict],
) -> pd.DataFrame:
    """Impute missing values and winsorize ML features."""

    result = data.copy()

    for feature in CLUSTER_FEATURES:

        raw_column = (
            f"raw_{feature}"
        )

        if raw_column not in result.columns:

            result[
                raw_column
            ] = result[
                feature
            ]

        missing_before = (
            result[
                feature
            ].isna()
        )

        sector_median = (
            result.groupby(
                "broad_sector"
            )[feature]
            .transform(
                "median"
            )
        )

        result[
            feature
        ] = (
            result[
                feature
            ]
            .fillna(
                sector_median
            )
        )

        global_median = (
            result[
                feature
            ]
            .median()
        )

        if pd.isna(
            global_median
        ):
            global_median = 0.0

        result[
            feature
        ] = (
            result[
                feature
            ]
            .fillna(
                global_median
            )
        )

        for index in result[
            missing_before
        ].index:

            notes.append(
                {
                    "company_id":
                        result.loc[
                            index,
                            "company_id",
                        ],
                    "feature":
                        feature,
                    "raw_value":
                        np.nan,
                    "replacement_value":
                        result.loc[
                            index,
                            feature,
                        ],
                    "reason":
                        "Missing ML feature",
                    "method":
                        "sector/global "
                        "median imputation",
                }
            )

        # --------------------------------------------
        # WINSORIZE EXTREMES
        # --------------------------------------------

        lower = (
            result[
                feature
            ]
            .quantile(
                0.05
            )
        )

        upper = (
            result[
                feature
            ]
            .quantile(
                0.95
            )
        )

        before_clip = (
            result[
                feature
            ].copy()
        )

        result[
            feature
        ] = (
            result[
                feature
            ]
            .clip(
                lower=lower,
                upper=upper,
            )
        )

        changed = (
            before_clip
            != result[
                feature
            ]
        )

        for index in result[
            changed
        ].index:

            notes.append(
                {
                    "company_id":
                        result.loc[
                            index,
                            "company_id",
                        ],
                    "feature":
                        feature,
                    "raw_value":
                        before_clip.loc[
                            index
                        ],
                    "replacement_value":
                        result.loc[
                            index,
                            feature,
                        ],
                    "reason":
                        "Extreme ML feature",
                    "method":
                        "5th/95th percentile "
                        "winsorization",
                }
            )

    return result


# ============================================================
# ELBOW ANALYSIS
# ============================================================

def create_elbow_plot(
    scaled: np.ndarray,
) -> None:
    """Generate elbow-method chart."""

    k_values = list(
        range(
            2,
            11,
        )
    )

    inertias = []

    for k in k_values:

        model = KMeans(
            n_clusters=k,
            random_state=42,
            n_init=50,
        )

        model.fit(
            scaled
        )

        inertias.append(
            model.inertia_
        )

    fig, ax = plt.subplots(
        figsize=(
            7,
            4.5,
        )
    )

    ax.plot(
        k_values,
        inertias,
        marker="o",
    )

    ax.axvline(
        5,
        linestyle="--",
        label="Selected k = 5",
    )

    ax.set_title(
        "KMeans Elbow Analysis"
    )

    ax.set_xlabel(
        "Number of Clusters"
    )

    ax.set_ylabel(
        "Within-Cluster Sum "
        "of Squares"
    )

    ax.grid(
        alpha=0.25
    )

    ax.legend()

    fig.tight_layout()

    fig.savefig(
        ELBOW_FILE,
        dpi=180,
        bbox_inches="tight",
    )

    plt.close(
        fig
    )


# ============================================================
# CLUSTER PROFILE
# ============================================================

def build_profiles(
    data: pd.DataFrame,
) -> pd.DataFrame:
    """Calculate average profile for each cluster."""

    profiles = (
        data.groupby(
            "cluster_id"
        )[
            CLUSTER_FEATURES
        ]
        .mean()
        .reset_index()
    )

    counts = (
        data.groupby(
            "cluster_id"
        )
        .size()
        .rename(
            "company_count"
        )
        .reset_index()
    )

    profiles = profiles.merge(
        counts,
        on="cluster_id",
    )

    return profiles


def zscore(
    series: pd.Series,
) -> pd.Series:
    """Standardize a cluster-profile metric."""

    numeric = pd.to_numeric(
        series,
        errors="coerce",
    )

    std = numeric.std(
        ddof=0
    )

    if (
        pd.isna(std)
        or std == 0
    ):

        return pd.Series(
            0.0,
            index=series.index,
        )

    return (
        numeric
        - numeric.mean()
    ) / std


# ============================================================
# CORRECTED CLUSTER NAMING
# ============================================================

def assign_cluster_names(
    profiles: pd.DataFrame,
) -> dict[int, str]:
    """Assign financially meaningful descriptive cluster names."""

    work = profiles.copy()

    for feature in CLUSTER_FEATURES:

        work[
            f"{feature}_z"
        ] = zscore(
            work[
                feature
            ]
        )

    # --------------------------------------------------------
    # DISTRESS:
    # High leverage + weak ROE + weak FCF growth
    # --------------------------------------------------------

    work[
        "distress_score"
    ] = (
        work[
            "debt_to_equity_z"
        ]
        - work[
            "roe_z"
        ]
        - work[
            "fcf_cagr_5yr_z"
        ]
    )

    # --------------------------------------------------------
    # HIGH QUALITY:
    # Strong ROE + cash growth + revenue growth +
    # margins + lower leverage
    # --------------------------------------------------------

    work[
        "quality_score"
    ] = (
        work[
            "roe_z"
        ]
        + work[
            "fcf_cagr_5yr_z"
        ]
        + 0.5
        * work[
            "revenue_cagr_5yr_z"
        ]
        + 0.5
        * work[
            "opm_z"
        ]
        - work[
            "debt_to_equity_z"
        ]
    )

    # --------------------------------------------------------
    # EMERGING GROWTH:
    # Revenue-led growth with some cash generation
    # --------------------------------------------------------

    work[
        "emerging_score"
    ] = (
        work[
            "revenue_cagr_5yr_z"
        ]
        + 0.25
        * work[
            "fcf_cagr_5yr_z"
        ]
        - 0.25
        * work[
            "debt_to_equity_z"
        ]
    )

    # --------------------------------------------------------
    # DEFENSIVE:
    # Lower growth + lower leverage + stable margins
    # --------------------------------------------------------

    work[
        "defensive_score"
    ] = (
        -work[
            "revenue_cagr_5yr_z"
        ]
        - work[
            "debt_to_equity_z"
        ]
        + 0.5
        * work[
            "opm_z"
        ]
        + 0.25
        * work[
            "roe_z"
        ]
    )

    names: dict[int, str] = {}

    remaining = set(
        work[
            "cluster_id"
        ]
        .astype(int)
        .tolist()
    )

    # --------------------------------------------------------
    # 1. DISTRESSED
    # --------------------------------------------------------

    candidate = work[
        work[
            "cluster_id"
        ].isin(
            remaining
        )
    ]

    distressed = int(
        candidate.loc[
            candidate[
                "distress_score"
            ].idxmax(),
            "cluster_id",
        ]
    )

    names[
        distressed
    ] = "Distressed"

    remaining.remove(
        distressed
    )

    # --------------------------------------------------------
    # 2. HIGH-QUALITY GROWTH
    # --------------------------------------------------------

    candidate = work[
        work[
            "cluster_id"
        ].isin(
            remaining
        )
    ]

    quality = int(
        candidate.loc[
            candidate[
                "quality_score"
            ].idxmax(),
            "cluster_id",
        ]
    )

    names[
        quality
    ] = "High-Quality Growth"

    remaining.remove(
        quality
    )

    # --------------------------------------------------------
    # 3. EMERGING GROWTH
    # --------------------------------------------------------

    candidate = work[
        work[
            "cluster_id"
        ].isin(
            remaining
        )
    ]

    emerging = int(
        candidate.loc[
            candidate[
                "emerging_score"
            ].idxmax(),
            "cluster_id",
        ]
    )

    names[
        emerging
    ] = "Emerging Growth"

    remaining.remove(
        emerging
    )

    # --------------------------------------------------------
    # 4. DEFENSIVE DIVIDEND
    # --------------------------------------------------------

    candidate = work[
        work[
            "cluster_id"
        ].isin(
            remaining
        )
    ]

    defensive = int(
        candidate.loc[
            candidate[
                "defensive_score"
            ].idxmax(),
            "cluster_id",
        ]
    )

    names[
        defensive
    ] = "Defensive Dividend"

    remaining.remove(
        defensive
    )

    # --------------------------------------------------------
    # 5. REMAINING CLUSTER
    # --------------------------------------------------------

    for cluster_id in remaining:

        names[
            int(
                cluster_id
            )
        ] = "Value Cyclicals"

    return names


# ============================================================
# CENTROID DISTANCE
# ============================================================

def calculate_centroid_distance(
    scaled: np.ndarray,
    model: KMeans,
) -> np.ndarray:
    """Calculate each company's distance from its centroid."""

    distances = []

    for index, cluster_id in enumerate(
        model.labels_
    ):

        centroid = (
            model.cluster_centers_[
                cluster_id
            ]
        )

        distance = (
            np.linalg.norm(
                scaled[
                    index
                ]
                - centroid
            )
        )

        distances.append(
            distance
        )

    return np.array(
        distances
    )


# ============================================================
# CORRELATION HEATMAP
# ============================================================

def create_heatmap(
    data: pd.DataFrame,
) -> None:
    """Generate robust KPI correlation heatmap."""

    matrix_data = (
        data[
            CORRELATION_METRICS
        ]
        .apply(
            pd.to_numeric,
            errors="coerce",
        )
        .copy()
    )

    for column in (
        matrix_data.columns
    ):

        lower = (
            matrix_data[
                column
            ]
            .quantile(
                0.05
            )
        )

        upper = (
            matrix_data[
                column
            ]
            .quantile(
                0.95
            )
        )

        matrix_data[
            column
        ] = (
            matrix_data[
                column
            ]
            .clip(
                lower=lower,
                upper=upper,
            )
        )

    correlation = (
        matrix_data.corr()
    )

    fig, ax = plt.subplots(
        figsize=(
            10,
            8,
        )
    )

    image = ax.imshow(
        correlation.values,
        vmin=-1,
        vmax=1,
        cmap="coolwarm",
    )

    labels = [
        value.replace(
            "_",
            " ",
        )
        for value
        in correlation.columns
    ]

    ax.set_xticks(
        range(
            len(labels)
        )
    )

    ax.set_yticks(
        range(
            len(labels)
        )
    )

    ax.set_xticklabels(
        labels,
        rotation=45,
        ha="right",
        fontsize=8,
    )

    ax.set_yticklabels(
        labels,
        fontsize=8,
    )

    for row in range(
        len(correlation)
    ):

        for column in range(
            len(correlation)
        ):

            value = correlation.iloc[
                row,
                column,
            ]

            if pd.notna(
                value
            ):

                ax.text(
                    column,
                    row,
                    f"{value:.2f}",
                    ha="center",
                    va="center",
                    fontsize=6,
                )

    ax.set_title(
        "Robust Latest-Year "
        "KPI Correlation Matrix"
    )

    fig.colorbar(
        image,
        ax=ax,
        label=(
            "Pearson Correlation"
        ),
    )

    fig.tight_layout()

    fig.savefig(
        HEATMAP_FILE,
        dpi=180,
        bbox_inches="tight",
    )

    plt.close(
        fig
    )


# ============================================================
# PORTFOLIO STATISTICS
# ============================================================

def create_portfolio_stats(
    data: pd.DataFrame,
) -> pd.DataFrame:
    """Calculate portfolio percentile statistics."""

    rows = []

    for metric in (
        PORTFOLIO_STATS_METRICS
    ):

        if metric not in data.columns:
            continue

        values = pd.to_numeric(
            data[
                metric
            ],
            errors="coerce",
        ).dropna()

        if values.empty:
            continue

        rows.append(
            {
                "metric":
                    metric,

                "p10":
                    values.quantile(
                        0.10
                    ),

                "p25":
                    values.quantile(
                        0.25
                    ),

                "p50":
                    values.quantile(
                        0.50
                    ),

                "p75":
                    values.quantile(
                        0.75
                    ),

                "p90":
                    values.quantile(
                        0.90
                    ),

                "mean":
                    values.mean(),

                "std":
                    values.std(),

                "observations":
                    len(
                        values
                    ),
            }
        )

    return pd.DataFrame(
        rows
    )


# ============================================================
# OUTLIER REPORT
# ============================================================

def create_outlier_report(
    raw_data: pd.DataFrame,
) -> pd.DataFrame:
    """Detect raw sector-relative outliers."""

    metrics = [
        "roe",
        "roce",
        "npm",
        "opm",
        "debt_to_equity",
        "revenue_cagr_5yr",
        "pat_cagr_5yr",
        "free_cash_flow_cr",
    ]

    rows = []

    for sector, group in (
        raw_data.groupby(
            "broad_sector"
        )
    ):

        for metric in metrics:

            values = pd.to_numeric(
                group[
                    metric
                ],
                errors="coerce",
            )

            mean = (
                values.mean()
            )

            std = (
                values.std(
                    ddof=0
                )
            )

            if (
                pd.isna(std)
                or std == 0
            ):
                continue

            scores = (
                values
                - mean
            ) / std

            for index, score in (
                scores.dropna()
                .items()
            ):

                if abs(
                    score
                ) <= 3:
                    continue

                row = (
                    group.loc[
                        index
                    ]
                )

                rows.append(
                    {
                        "company_id":
                            row[
                                "company_id"
                            ],

                        "company_name":
                            row[
                                "company_name"
                            ],

                        "metric":
                            metric,

                        "value":
                            values.loc[
                                index
                            ],

                        "z_score":
                            score,

                        "sector":
                            sector,

                        "sector_mean":
                            mean,

                        "sector_std":
                            std,
                    }
                )

    return pd.DataFrame(
        rows,
        columns=[
            "company_id",
            "company_name",
            "metric",
            "value",
            "z_score",
            "sector",
            "sector_mean",
            "sector_std",
        ],
    )


# ============================================================
# MAIN PIPELINE
# ============================================================

def main() -> None:
    """Run complete D36-D37 clustering workflow."""

    if not DB_PATH.exists():

        raise FileNotFoundError(
            f"Database not found: "
            f"{DB_PATH}"
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    CLUSTER_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # LOAD
    # --------------------------------------------------------

    raw = prepare_raw_data()

    print(
        "Companies loaded:",
        len(raw),
    )

    if len(raw) != 92:

        raise RuntimeError(
            "Expected 92 companies, "
            f"found {len(raw)}."
        )

    # --------------------------------------------------------
    # ROE DATA QUALITY FIX
    # --------------------------------------------------------

    cleaned, notes = (
        repair_roe_for_model(
            raw
        )
    )

    # --------------------------------------------------------
    # IMPUTE + WINSORIZE
    # --------------------------------------------------------

    prepared = (
        prepare_model_features(
            cleaned,
            notes,
        )
    )

    # --------------------------------------------------------
    # SCALE
    # --------------------------------------------------------

    feature_matrix = (
        prepared[
            CLUSTER_FEATURES
        ]
    )

    scaler = (
        StandardScaler()
    )

    scaled = (
        scaler.fit_transform(
            feature_matrix
        )
    )

    # --------------------------------------------------------
    # ELBOW
    # --------------------------------------------------------

    create_elbow_plot(
        scaled
    )

    # --------------------------------------------------------
    # KMEANS
    # --------------------------------------------------------

    model = KMeans(
        n_clusters=5,
        random_state=42,
        n_init=50,
    )

    prepared[
        "cluster_id"
    ] = (
        model.fit_predict(
            scaled
        )
    )

    prepared[
        "distance_from_centroid"
    ] = (
        calculate_centroid_distance(
            scaled,
            model,
        )
    )

    # --------------------------------------------------------
    # CLUSTER PROFILES
    # --------------------------------------------------------

    profiles = (
        build_profiles(
            prepared
        )
    )

    names = (
        assign_cluster_names(
            profiles
        )
    )

    prepared[
        "cluster_name"
    ] = (
        prepared[
            "cluster_id"
        ]
        .map(
            names
        )
    )

    profiles[
        "cluster_name"
    ] = (
        profiles[
            "cluster_id"
        ]
        .map(
            names
        )
    )

    # --------------------------------------------------------
    # EXPORT CLUSTER LABELS
    # --------------------------------------------------------

    output_columns = [
        "company_id",
        "company_name",
        "broad_sector",
        "cluster_id",
        "cluster_name",
        "distance_from_centroid",
        "source_roe",
    ]

    for feature in (
        CLUSTER_FEATURES
    ):

        raw_name = (
            f"raw_{feature}"
        )

        if raw_name in (
            prepared.columns
        ):

            output_columns.append(
                raw_name
            )

        output_columns.append(
            feature
        )

    cluster_output = (
        prepared[
            output_columns
        ]
        .copy()
    )

    cluster_output = (
        cluster_output
        .sort_values(
            [
                "cluster_id",
                "distance_from_centroid",
            ]
        )
    )

    cluster_output.to_csv(
        CLUSTER_FILE,
        index=False,
    )

    # --------------------------------------------------------
    # EXPORT CLUSTER PROFILES
    # --------------------------------------------------------

    profiles = (
        profiles.sort_values(
            "cluster_id"
        )
    )

    profiles.to_csv(
        PROFILE_FILE,
        index=False,
    )

    # --------------------------------------------------------
    # DATA QUALITY LOG
    # --------------------------------------------------------

    dq_frame = (
        pd.DataFrame(
            notes
        )
    )

    if not dq_frame.empty:

        dq_frame = (
            dq_frame
            .drop_duplicates()
        )

    dq_frame.to_csv(
        DQ_FILE,
        index=False,
    )

    # --------------------------------------------------------
    # HEATMAP
    # --------------------------------------------------------

    create_heatmap(
        cleaned
    )

    # --------------------------------------------------------
    # PORTFOLIO STATS
    # --------------------------------------------------------

    portfolio_stats = (
        create_portfolio_stats(
            cleaned
        )
    )

    portfolio_stats.to_csv(
        STATS_FILE,
        index=False,
    )

    # --------------------------------------------------------
    # OUTLIERS
    # --------------------------------------------------------

    outliers = (
        create_outlier_report(
            raw
        )
    )

    outliers.to_csv(
        OUTLIER_FILE,
        index=False,
    )

    # --------------------------------------------------------
    # TERMINAL OUTPUT
    # --------------------------------------------------------

    print()

    print(
        "--- CLUSTER DISTRIBUTION ---"
    )

    print(
        cluster_output[
            "cluster_name"
        ]
        .value_counts()
        .to_string()
    )

    print()

    print(
        "--- CLUSTER PROFILES ---"
    )

    print(
        profiles[
            [
                "cluster_id",
                "cluster_name",
                "company_count",
                "roe",
                "debt_to_equity",
                "revenue_cagr_5yr",
                "fcf_cagr_5yr",
                "opm",
            ]
        ]
        .round(
            2
        )
        .to_string(
            index=False
        )
    )

    print()

    print(
        "Cluster rows:",
        len(
            cluster_output
        ),
    )

    print(
        "Unique clusters:",
        cluster_output[
            "cluster_id"
        ].nunique(),
    )

    print(
        "Null cluster IDs:",
        cluster_output[
            "cluster_id"
        ]
        .isna()
        .sum(),
    )

    print(
        "Null cluster names:",
        cluster_output[
            "cluster_name"
        ]
        .isna()
        .sum(),
    )

    print(
        "DQ adjustments:",
        len(
            dq_frame
        ),
    )

    print(
        "Outliers detected:",
        len(
            outliers
        ),
    )

    print()

    print(
        "Created:",
        CLUSTER_FILE,
    )

    print(
        "Created:",
        PROFILE_FILE,
    )

    print(
        "Created:",
        DQ_FILE,
    )

    print(
        "Created:",
        ELBOW_FILE,
    )

    print(
        "Created:",
        HEATMAP_FILE,
    )

    print(
        "Created:",
        STATS_FILE,
    )

    print(
        "Created:",
        OUTLIER_FILE,
    )


if __name__ == "__main__":
    main()