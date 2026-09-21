from __future__ import annotations

import ast
import codecs
from pathlib import Path


DOCSTRINGS = {
    ("src/analytics/analysis_parser.py", "parse_metric"):
        "Parse a metric value from the analysis dataset.",

    ("src/analytics/cashflow_intelligence.py", "quality_label"):
        "Return the cash-flow quality label for a numeric score.",

    ("src/analytics/peer.py", "load_peer_data"):
        "Load peer-group and supporting company data.",
    ("src/analytics/peer.py", "build_peer_percentiles"):
        "Compute peer-group percentile metrics for all companies.",
    ("src/analytics/peer.py", "save_peer_percentiles"):
        "Save computed peer-percentile data to the project output.",
    ("src/analytics/peer.py", "main"):
        "Run the peer-analysis workflow.",

    ("src/analytics/peer_export.py", "load_data"):
        "Load data required for the peer-comparison workbook.",
    ("src/analytics/peer_export.py", "safe_sheet_name"):
        "Return an Excel-safe worksheet name.",
    ("src/analytics/peer_export.py", "build_group_table"):
        "Build the comparison table for one peer group.",
    ("src/analytics/peer_export.py", "style_sheet"):
        "Apply formatting to a peer-comparison worksheet.",
    ("src/analytics/peer_export.py", "main"):
        "Generate the peer-comparison Excel workbook.",

    ("src/analytics/pros_cons_generator.py", "valid"):
        "Return whether a candidate value is valid and usable.",
    ("src/analytics/pros_cons_generator.py", "add"):
        "Add a generated pro or con when its condition is satisfied.",

    ("src/analytics/radar.py", "load_data"):
        "Load company, peer, and metric data for radar charts.",
    ("src/analytics/radar.py", "choose_company_year"):
        "Choose the best available financial year for a company.",
    ("src/analytics/radar.py", "get_comparison_group"):
        "Return the peer-comparison group for a company.",
    ("src/analytics/radar.py", "reference_values"):
        "Calculate reference values used for radar metrics.",
    ("src/analytics/radar.py", "normalise"):
        "Normalise a metric value for radar-chart comparison.",
    ("src/analytics/radar.py", "safe_filename"):
        "Return a filesystem-safe filename.",
    ("src/analytics/radar.py", "generate_chart"):
        "Generate and save a company peer-comparison radar chart.",
    ("src/analytics/radar.py", "main"):
        "Generate radar charts for the configured company universe.",

    ("src/analytics/validate_sprint2_spotcheck.py", "year_number"):
        "Extract a sortable year number from a financial-year value.",

    ("src/screener/engine.py", "__init__"):
        "Initialise the screener engine and load its configuration.",
    ("src/screener/engine.py", "_load_yaml"):
        "Load and return a YAML configuration file.",
    ("src/screener/engine.py", "_load_metrics"):
        "Load configured screener metric definitions.",
    ("src/screener/engine.py", "_load_presets"):
        "Load configured preset screener definitions.",
    ("src/screener/engine.py", "available_metrics"):
        "Return the configured screener metric names.",
    ("src/screener/engine.py", "available_presets"):
        "Return the available preset screener names.",
    ("src/screener/engine.py", "_parse_filters"):
        "Parse command-line metric filters into numeric thresholds.",
    ("src/screener/engine.py", "main"):
        "Run the command-line screener workflow.",

    ("src/screener/export.py", "format_workbook"):
        "Apply presentation formatting to the screener workbook.",
    ("src/screener/export.py", "main"):
        "Generate the formatted screener workbook.",

    ("src/screener/ranking.py", "load_ranking_data"):
        "Load aligned data required for composite ranking.",
    ("src/screener/ranking.py", "sector_percentile"):
        "Calculate sector-relative percentile scores for a metric.",
    ("src/screener/ranking.py", "build_ranking"):
        "Build the sector-relative composite company ranking.",
    ("src/screener/ranking.py", "export_ranking"):
        "Export the composite ranking to an Excel workbook.",
    ("src/screener/ranking.py", "main"):
        "Run the ranking and export workflow.",

    ("src/dashboard/pages/02_profile.py", "pct"):
        "Format a numeric value as a percentage for display.",
    ("src/dashboard/pages/02_profile.py", "number"):
        "Format a numeric value for dashboard display.",
    ("src/dashboard/pages/02_profile.py", "crore"):
        "Format a monetary value in Indian rupees crore.",
}


def read_source(path: Path):
    """Read Python source while preserving an existing UTF-8 BOM."""

    raw = path.read_bytes()
    has_bom = raw.startswith(codecs.BOM_UTF8)

    if has_bom:
        text = raw[len(codecs.BOM_UTF8):].decode("utf-8")
    else:
        text = raw.decode("utf-8")

    return text, has_bom


def write_source(
    path: Path,
    text: str,
    has_bom: bool,
):
    """Write source while preserving its original BOM state."""

    raw = text.encode("utf-8")

    if has_bom:
        raw = codecs.BOM_UTF8 + raw

    path.write_bytes(raw)


targets_found = set()
total_added = 0

for path in Path("src").rglob("*.py"):

    if "__pycache__" in path.parts:
        continue

    relative = path.as_posix()

    source, has_bom = read_source(path)

    tree = ast.parse(
        source,
        filename=relative,
    )

    newline = (
        "\r\n"
        if "\r\n" in source
        else "\n"
    )

    lines = source.splitlines(
        keepends=True
    )

    insertions = []

    for node in ast.walk(tree):

        if not isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            continue

        key = (
            relative,
            node.name,
        )

        if key not in DOCSTRINGS:
            continue

        targets_found.add(key)

        if ast.get_docstring(node):
            continue

        if not node.body:
            raise RuntimeError(
                f"No function body found for {key}"
            )

        first_statement = node.body[0]

        if (
            first_statement.lineno
            <= node.lineno
        ):
            raise RuntimeError(
                "One-line function cannot be "
                f"safely modified automatically: {key}"
            )

        insert_at = (
            first_statement.lineno - 1
        )

        indent = (
            " " * first_statement.col_offset
        )

        docstring = (
            f'{indent}"""'
            f'{DOCSTRINGS[key]}'
            f'"""{newline}'
        )

        insertions.append(
            (
                insert_at,
                docstring,
                key,
            )
        )

    for (
        insert_at,
        docstring,
        key,
    ) in sorted(
        insertions,
        key=lambda item: item[0],
        reverse=True,
    ):
        lines.insert(
            insert_at,
            docstring,
        )

        total_added += 1

    if insertions:
        write_source(
            path,
            "".join(lines),
            has_bom,
        )


missing_targets = (
    set(DOCSTRINGS)
    - targets_found
)

if missing_targets:
    print(
        "WARNING: mapped functions "
        "not found:"
    )

    for key in sorted(
        missing_targets
    ):
        print(key)


# ------------------------------------------------------------
# Re-audit every Python object
# ------------------------------------------------------------

remaining = []

files_checked = 0
objects_checked = 0

for path in Path("src").rglob("*.py"):

    if "__pycache__" in path.parts:
        continue

    files_checked += 1

    source, _ = read_source(path)

    tree = ast.parse(
        source,
        filename=str(path),
    )

    for node in ast.walk(tree):

        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
            ),
        ):
            objects_checked += 1

            if not ast.get_docstring(node):
                remaining.append(
                    (
                        path.as_posix(),
                        node.lineno,
                        node.name,
                    )
                )


print()
print(
    "=== D44 DOCSTRING UPDATE ==="
)
print(
    "Docstrings added:",
    total_added,
)
print(
    "Python files checked:",
    files_checked,
)
print(
    "Functions/classes checked:",
    objects_checked,
)
print(
    "Remaining missing docstrings:",
    len(remaining),
)

if remaining:
    print()
    print(
        "--- STILL MISSING ---"
    )

    for item in remaining:
        print(
            f"{item[0]}:"
            f"{item[1]} | "
            f"{item[2]}"
        )
