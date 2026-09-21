"""Config-driven investment screener for the N100 platform."""

from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


DEFAULT_DB_PATH = Path("data/nifty100.db")
DEFAULT_CONFIG_PATH = Path("config/screener_config.yaml")

TABLE_ALIASES = {
    "financial_ratios": "r",
    "market_cap": "m",
    "profitandloss": "p",
}

IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

PRESET_OPERATORS = {"gt", "lt", "eq"}


class ScreenerEngine:
    """Apply custom filters and preset screens to the N100 universe."""

    def __init__(
        self,
        db_path: str | Path = DEFAULT_DB_PATH,
        config_path: str | Path = DEFAULT_CONFIG_PATH,
        ratio_year: str = "2024-03",
        pnl_year: str = "2024-03",
        market_cap_year: int = 2024,
    ) -> None:
        """Initialise the screener engine and load its configuration."""
        self.db_path = Path(db_path)
        self.config_path = Path(config_path)
        self.ratio_year = ratio_year
        self.pnl_year = pnl_year
        self.market_cap_year = market_cap_year

        self.config = self._load_yaml()
        self.metrics = self._load_metrics()
        self.presets = self._load_presets()

    def _load_yaml(self) -> dict[str, Any]:
        """Load and return a YAML configuration file."""
        with self.config_path.open("r", encoding="utf-8") as file:
            return yaml.safe_load(file) or {}

    def _load_metrics(self) -> dict[str, dict[str, Any]]:
        """Load configured screener metric definitions."""
        metrics = self.config.get("metrics", {})

        if not metrics:
            raise ValueError("No metrics found in screener configuration.")

        for metric_name, details in metrics.items():
            table = details.get("table")
            column = details.get("column")
            operator = details.get("operator")

            if table not in TABLE_ALIASES:
                raise ValueError(
                    f"Unsupported table '{table}' for metric '{metric_name}'."
                )

            if not column or not IDENTIFIER_PATTERN.fullmatch(column):
                raise ValueError(
                    f"Invalid column '{column}' for metric '{metric_name}'."
                )

            if operator not in {"min", "max"}:
                raise ValueError(
                    f"Metric '{metric_name}' must use operator 'min' or 'max'."
                )

        return metrics

    def _load_presets(self) -> dict[str, dict[str, Any]]:
        """Load configured preset screener definitions."""
        presets = self.config.get("presets", {})

        for preset_name, preset in presets.items():
            conditions = preset.get("conditions", [])

            if not conditions:
                raise ValueError(
                    f"Preset '{preset_name}' has no conditions."
                )

            for condition in conditions:
                operator = condition.get("operator")

                if operator not in PRESET_OPERATORS:
                    raise ValueError(
                        f"Invalid preset operator '{operator}' "
                        f"in '{preset_name}'."
                    )

                if "metric" in condition:
                    if condition["metric"] not in self.metrics:
                        raise ValueError(
                            f"Unknown metric '{condition['metric']}' "
                            f"in preset '{preset_name}'."
                        )

                elif "column" in condition:
                    if condition["column"] != "total_debt_cr":
                        raise ValueError(
                            f"Unsupported direct column "
                            f"'{condition['column']}' "
                            f"in preset '{preset_name}'."
                        )

                else:
                    raise ValueError(
                        f"Preset '{preset_name}' condition requires "
                        f"'metric' or 'column'."
                    )

        return presets

    def available_metrics(self) -> list[str]:
        """Return the configured screener metric names."""
        return list(self.metrics.keys())

    def available_presets(self) -> list[str]:
        """Return the available preset screener names."""
        return list(self.presets.keys())

    def load_universe(self) -> pd.DataFrame:
        """Load companies using each company's latest available annual data."""

        metric_selects = []

        for metric_name, details in self.metrics.items():
            table_alias = TABLE_ALIASES[details["table"]]
            column = details["column"]

            metric_selects.append(
                f'{table_alias}."{column}" AS "{metric_name}"'
            )

        select_metrics = ",\n                ".join(metric_selects)

        query = f"""
            SELECT
                c.id AS company_id,
                c.company_name,
                r.year AS ratio_year,
                p.year AS pnl_year,
                m.year AS market_cap_year,
                r.total_debt_cr AS total_debt_cr,
                {select_metrics}

            FROM companies AS c

            LEFT JOIN financial_ratios AS r
                ON r.company_id = c.id
               AND r.year = (
                    SELECT MAX(fr.year)
                    FROM financial_ratios AS fr
                    WHERE fr.company_id = c.id
                      AND fr.year <> 'TTM'
               )

            LEFT JOIN profitandloss AS p
                ON p.company_id = c.id
               AND p.year = (
                    SELECT MAX(pl.year)
                    FROM profitandloss AS pl
                    WHERE pl.company_id = c.id
                      AND pl.year <> 'TTM'
               )

            LEFT JOIN market_cap AS m
                ON m.company_id = c.id
               AND m.year = (
                    SELECT MAX(mc.year)
                    FROM market_cap AS mc
                    WHERE mc.company_id = c.id
               )

            ORDER BY c.id
        """

        with sqlite3.connect(self.db_path) as connection:
            return pd.read_sql_query(
                query,
                connection,
            )

    def screen(
        self,
        filters: dict[str, float] | None = None,
    ) -> pd.DataFrame:
        """Apply custom min/max filters."""

        frame = self.load_universe()

        if not filters:
            return frame.reset_index(drop=True)

        for metric_name, threshold in filters.items():
            if metric_name not in self.metrics:
                raise KeyError(
                    f"Unknown screener metric '{metric_name}'."
                )

            operator = self.metrics[metric_name]["operator"]
            values = pd.to_numeric(
                frame[metric_name],
                errors="coerce",
            )

            threshold = float(threshold)

            if operator == "min":
                mask = values >= threshold
            else:
                mask = values <= threshold

            frame = frame.loc[mask].copy()

        return frame.reset_index(drop=True)

    def run_preset(
        self,
        preset_name: str,
    ) -> pd.DataFrame:
        """Execute one configured preset screener."""

        if preset_name not in self.presets:
            raise KeyError(
                f"Unknown preset '{preset_name}'. "
                f"Available: {', '.join(self.available_presets())}"
            )

        frame = self.load_universe()
        conditions = self.presets[preset_name]["conditions"]

        for condition in conditions:

            column = condition.get(
                "metric",
                condition.get("column"),
            )

            values = pd.to_numeric(
                frame[column],
                errors="coerce",
            )

            threshold = float(condition["value"])
            operator = condition["operator"]

            if operator == "gt":
                mask = values > threshold

            elif operator == "lt":
                mask = values < threshold

            else:
                mask = values == threshold

            frame = frame.loc[mask].copy()

        return frame.reset_index(drop=True)

    def coverage(self) -> pd.DataFrame:
        """Return coverage for all 15 configurable metrics."""

        frame = self.load_universe()
        total = len(frame)

        rows = []

        for metric_name, details in self.metrics.items():
            available = int(
                frame[metric_name].notna().sum()
            )

            rows.append(
                {
                    "metric": metric_name,
                    "label": details["label"],
                    "available_companies": available,
                    "missing_companies": total - available,
                    "coverage_pct": round(
                        (available / total) * 100,
                        2,
                    )
                    if total
                    else 0.0,
                }
            )

        return pd.DataFrame(rows)


def _parse_filters(raw_filters: list[str]) -> dict[str, float]:
    """Parse command-line metric filters into numeric thresholds."""
    parsed: dict[str, float] = {}

    for item in raw_filters:
        if "=" not in item:
            raise ValueError(
                f"Invalid filter '{item}'. "
                f"Expected metric=value."
            )

        metric, value = item.split("=", 1)
        parsed[metric.strip()] = float(value.strip())

    return parsed


def main() -> None:
    """Run the command-line screener workflow."""
    parser = argparse.ArgumentParser(
        description="N100 configurable investment screener"
    )

    parser.add_argument(
        "--filter",
        action="append",
        default=[],
    )

    parser.add_argument(
        "--preset",
        choices=[
            "quality",
            "value",
            "growth",
            "dividend",
            "momentum",
            "debt_free",
        ],
    )

    parser.add_argument(
        "--coverage",
        action="store_true",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=100,
    )

    args = parser.parse_args()

    engine = ScreenerEngine()

    if args.coverage:
        print(engine.coverage().to_string(index=False))
        return

    if args.preset:
        result = engine.run_preset(args.preset)

        print(f"Preset: {args.preset}")
        print(f"Universe companies: {len(engine.load_universe())}")
        print(f"Matched companies: {len(result)}")

        print(
            result[
                ["company_id", "company_name"]
            ]
            .head(args.limit)
            .to_string(index=False)
        )
        return

    filters = _parse_filters(args.filter)
    result = engine.screen(filters)

    print(f"Universe companies: {len(engine.load_universe())}")
    print(f"Matched companies: {len(result)}")

    display_columns = [
        "company_id",
        "company_name",
        *filters.keys(),
    ]

    print(
        result[display_columns]
        .head(args.limit)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
