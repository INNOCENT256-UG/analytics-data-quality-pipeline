
"""
Reusable CSV data-cleaning engine.

Features:
- Trim whitespace from text columns.
- Convert configured numeric columns.
- Parse configured date columns.
- Report duplicate rows without deleting them.
- Report missing values and invalid conversions.
- Save cleaned datasets and cleaning reports separately.
"""

import argparse
import json
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPORT_DIR = PROJECT_ROOT / "reports"


def load_config(config_path):
    """Load dataset-specific cleaning configuration."""
    with open(config_path, "r", encoding="utf-8") as file:
        return json.load(file)


def clean_dataset(df, config):
    """Clean a DataFrame and accurately record transformations."""

    cleaned_df = df.copy()
    report = []

    dataset_name = config.get("dataset_name", "unknown")

    def record(
        column,
        operation,
        values_before,
        values_after,
        details="",
    ):
        report.append(
            {
                "dataset": dataset_name,
                "column": column,
                "operation": operation,
                "values_before": values_before,
                "values_after": values_after,
                "details": details,
            }
        )

    # 1. Trim whitespace and convert blank strings to missing values.
    text_columns = cleaned_df.select_dtypes(
        include=["object", "string"]
    ).columns

    for column in text_columns:
        original = cleaned_df[column].copy()

        non_missing = original.notna()

        trimmed = original.copy()
        trimmed.loc[non_missing] = (
            original.loc[non_missing].astype(str).str.strip()
        )

        changed_mask = (
            original.notna()
            & trimmed.notna()
            & original.astype("string").ne(
                trimmed.astype("string")
            ).fillna(False)
        )

        whitespace_changes = int(changed_mask.sum())

        cleaned_df[column] = trimmed

        record(
            column,
            "trim_whitespace",
            int(non_missing.sum()),
            whitespace_changes,
            (
                f"Values examined: {int(non_missing.sum())}; "
                f"values changed: {whitespace_changes}."
            ),
        )

        blank_mask = (
            cleaned_df[column]
            .astype("string")
            .eq("")
            .fillna(False)
        )

        blank_count = int(blank_mask.sum())

        if blank_count:
            cleaned_df.loc[blank_mask, column] = pd.NA

        record(
            column,
            "blank_to_missing",
            blank_count,
            blank_count,
            (
                f"Whitespace-only values converted to missing: "
                f"{blank_count}."
            ),
        )

    # 2. Convert explicitly configured numeric columns.
    numeric_columns = config.get("numeric_columns", [])

    for column in numeric_columns:
        if column not in cleaned_df.columns:
            record(
                column,
                "numeric_conversion",
                0,
                0,
                "SKIPPED: configured column does not exist.",
            )
            continue

        original = cleaned_df[column].copy()
        converted = pd.to_numeric(original, errors="coerce")

        newly_missing = original.notna() & converted.isna()

        valid_before = int(original.notna().sum())
        valid_after = int(converted.notna().sum())
        invalid_count = int(newly_missing.sum())

        # Count values whose representation changed, including
        # string-to-number conversions.
        changed_count = 0

        for old_value, new_value in zip(original, converted):
            if pd.isna(old_value) and pd.isna(new_value):
                continue

            if pd.isna(old_value) or pd.isna(new_value):
                changed_count += 1
                continue

            try:
                if float(old_value) != float(new_value):
                    changed_count += 1
            except (TypeError, ValueError):
                changed_count += 1

        cleaned_df[column] = converted

        record(
            column,
            "numeric_conversion",
            valid_before,
            valid_after,
            (
                f"Values changed or converted: {changed_count}; "
                f"invalid values converted to missing: {invalid_count}; "
                f"valid values before: {valid_before}; "
                f"valid values after: {valid_after}."
            ),
        )

    # 3. Parse explicitly configured date columns.
    date_columns = config.get("date_columns", [])

    for column in date_columns:
        if column not in cleaned_df.columns:
            record(
                column,
                "date_conversion",
                0,
                0,
                "SKIPPED: configured column does not exist.",
            )
            continue

        original = cleaned_df[column].copy()

        converted = pd.to_datetime(
            original,
            errors="coerce",
            format="mixed",
        )

        newly_missing = original.notna() & converted.isna()

        valid_before = int(original.notna().sum())
        valid_after = int(converted.notna().sum())
        invalid_count = int(newly_missing.sum())

        cleaned_df[column] = converted

        record(
            column,
            "date_conversion",
            valid_before,
            valid_after,
            (
                f"Values parsed: {valid_after}; "
                f"unparseable non-missing values: {invalid_count}; "
                f"missing before conversion: "
                f"{int(original.isna().sum())}."
            ),
        )

    # 4. Report missing values after cleaning.
    for column in cleaned_df.columns:
        missing_count = int(cleaned_df[column].isna().sum())

        record(
            column,
            "missing_value_check",
            missing_count,
            missing_count,
            "Missing values remaining after cleaning.",
        )

    # 5. Detect exact duplicate rows without deleting them.
    duplicate_count = int(cleaned_df.duplicated(keep="first").sum())

    record(
        "__all_columns__",
        "duplicate_detection",
        duplicate_count,
        duplicate_count,
        "Exact duplicate rows detected; no rows were deleted.",
    )

    return cleaned_df, pd.DataFrame(report)

def main():
    """Run the cleaning pipeline from the command line."""
    parser = argparse.ArgumentParser(
        description="Clean a CSV dataset using a JSON configuration."
    )

    parser.add_argument(
        "input_file",
        help="Path to the input CSV file.",
    )
    parser.add_argument(
        "config_file",
        help="Path to the dataset JSON configuration.",
    )

    args = parser.parse_args()

    input_path = Path(args.input_file)
    config_path = Path(args.config_file)

    if not input_path.is_absolute():
        input_path = PROJECT_ROOT / input_path

    if not config_path.is_absolute():
        config_path = PROJECT_ROOT / config_path

    if not input_path.exists():
        parser.error(f"Input CSV file not found: {input_path}")

    if not config_path.exists():
        parser.error(f"Configuration file not found: {config_path}")

    config = load_config(config_path)
    dataset_name = config.get("dataset_name", input_path.stem)

    print(f"Loading dataset: {dataset_name}")
    original_df = pd.read_csv(input_path)

    print(f"Input shape: {original_df.shape}")

    cleaned_df, cleaning_report = clean_dataset(original_df, config)

    processed_dir = PROJECT_ROOT / "data" / "processed"
    report_dir = DEFAULT_REPORT_DIR

    processed_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    cleaned_path = processed_dir / f"{dataset_name}_cleaned.csv"
    report_path = report_dir / f"{dataset_name}_cleaning_report.csv"

    cleaned_df.to_csv(cleaned_path, index=False)
    cleaning_report.to_csv(report_path, index=False)

    duplicate_row = cleaning_report[
        cleaning_report["operation"] == "duplicate_detection"
    ]

    duplicate_count = (
        int(duplicate_row.iloc[0]["values_before"])
        if not duplicate_row.empty
        else 0
    )

    missing_values = int(cleaned_df.isna().sum().sum())

    print("\nCLEANING SUMMARY")
    print("-" * 40)
    print(f"Dataset: {dataset_name}")
    print(f"Original shape: {original_df.shape}")
    print(f"Cleaned shape: {cleaned_df.shape}")
    print(f"Rows removed: {len(original_df) - len(cleaned_df)}")
    print(f"Duplicate rows detected: {duplicate_count}")
    print(f"Missing values remaining: {missing_values}")
    print(f"\nCleaned dataset saved to: {cleaned_path}")
    print(f"Cleaning report saved to: {report_path}")
    print("\nCLEANING COMPLETED")


if __name__ == "__main__":
    main()
