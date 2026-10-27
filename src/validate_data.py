
import argparse
import json
import sys
from pathlib import Path

import pandas as pd


# --------------------------------------------------
# 1. LOAD CONFIGURATION AND DATA
# --------------------------------------------------

def load_config(config_path):
    """Load validation rules from a JSON configuration."""
    path = Path(config_path)

    if not path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        config = json.load(file)

    if not isinstance(config, dict):
        raise ValueError("Configuration must be a JSON object.")

    return config


def load_dataset(dataset_path):
    """Load a CSV dataset."""
    path = Path(dataset_path)

    if not path.is_file():
        raise FileNotFoundError(f"Dataset not found: {path}")

    return pd.read_csv(path)


# --------------------------------------------------
# 2. RECORD VALIDATION RESULTS
# --------------------------------------------------

def add_result(results, rule, passed, details):
    """Record a validation result."""
    results.append({
        "rule": rule,
        "status": "PASS" if passed else "FAIL",
        "details": details,
    })


# --------------------------------------------------
# 3. REQUIRED COLUMNS
# --------------------------------------------------

def validate_required_columns(df, config, results):
    """Check that all required columns exist."""
    required = config.get("required_columns", [])
    missing = [column for column in required if column not in df.columns]

    add_result(
        results,
        "Required columns",
        not missing,
        f"Missing columns: {missing}" if missing
        else f"All {len(required)} required columns exist.",
    )


# --------------------------------------------------
# 4. MISSING VALUES
# --------------------------------------------------

def validate_missing_values(df, config, results):
    """Check required columns for missing or blank values."""
    required = config.get("required_columns", [])
    counts = {}

    for column in required:
        if column not in df.columns:
            continue

        series = df[column]
        missing = series.isna()

        if (
            pd.api.types.is_object_dtype(series)
            or pd.api.types.is_string_dtype(series)
        ):
            blank = series.astype("string").str.strip().eq("").fillna(False)
            missing = missing | blank

        count = int(missing.sum())

        if count:
            counts[column] = count

    add_result(
        results,
        "Missing values",
        not counts,
        f"Missing or blank values: {counts}" if counts
        else "No missing or blank values in existing required columns.",
    )


# --------------------------------------------------
# 5. POSITIVE VALUES
# --------------------------------------------------

def validate_positive_columns(df, config, results):
    """Check that configured columns contain numeric values greater than 0."""
    for column in config.get("positive_columns", []):
        name = f"Positive values: {column}"

        if column not in df.columns:
            add_result(results, name, False, "Column does not exist.")
            continue

        values = pd.to_numeric(df[column], errors="coerce")
        invalid = values.isna() | (values <= 0)
        count = int(invalid.sum())

        add_result(
            results,
            name,
            count == 0,
            f"{count} invalid values." if count
            else f"All {len(df)} values are positive.",
        )


# --------------------------------------------------
# 6. NON-NEGATIVE VALUES
# --------------------------------------------------

def validate_non_negative_columns(df, config, results):
    """Check that configured columns contain numeric values >= 0."""
    for column in config.get("non_negative_columns", []):
        name = f"Non-negative values: {column}"

        if column not in df.columns:
            add_result(results, name, False, "Column does not exist.")
            continue

        values = pd.to_numeric(df[column], errors="coerce")
        invalid = values.isna() | (values < 0)
        count = int(invalid.sum())

        add_result(
            results,
            name,
            count == 0,
            f"{count} negative or non-numeric values." if count
            else f"All {len(df)} values are numeric and non-negative.",
        )


# --------------------------------------------------
# 7. MINIMUM AND MAXIMUM RANGES
# --------------------------------------------------

def validate_range_rules(df, config, results):
    """Check numeric values against configured minimum and maximum."""
    for rule in config.get("range_rules", []):
        column = rule.get("column")
        minimum = rule.get("min")
        maximum = rule.get("max")
        name = f"Value range: {column}"

        if not column or column not in df.columns:
            add_result(results, name, False, "Column does not exist.")
            continue

        values = pd.to_numeric(df[column], errors="coerce")
        invalid = values.isna()

        if minimum is not None:
            invalid = invalid | (values < minimum)

        if maximum is not None:
            invalid = invalid | (values > maximum)

        count = int(invalid.sum())

        add_result(
            results,
            name,
            count == 0,
            (
                f"{count} values are non-numeric or outside "
                f"the allowed range [{minimum}, {maximum}]."
            ) if count else (
                f"All {len(df)} values are within "
                f"the allowed range [{minimum}, {maximum}]."
            ),
        )


# --------------------------------------------------
# 8. DATE VALIDATION
# --------------------------------------------------

def validate_dates(df, config, results):
    """Validate date formats and date-order rules."""
    parsed_dates = {}

    for column in config.get("date_columns", []):
        name = f"Date parsing: {column}"

        if column not in df.columns:
            add_result(results, name, False, "Column does not exist.")
            continue

        original = df[column]
        parsed = pd.to_datetime(original, errors="coerce")
        invalid = original.notna() & parsed.isna()

        if (
            pd.api.types.is_object_dtype(original)
            or pd.api.types.is_string_dtype(original)
        ):
            blank = original.astype("string").str.strip().eq("").fillna(False)
            invalid = invalid | blank

        count = int(invalid.sum())
        parsed_dates[column] = parsed

        add_result(
            results,
            name,
            count == 0,
            f"{count} invalid dates." if count
            else "All non-missing dates are valid.",
        )

    for rule in config.get("date_order_rules", []):
        earlier = rule.get("earlier_date")
        later = rule.get("later_date")
        name = f"Date order: {earlier} <= {later}"

        if earlier not in parsed_dates or later not in parsed_dates:
            add_result(
                results,
                name,
                False,
                "Both columns must be listed in date_columns.",
            )
            continue

        start = parsed_dates[earlier]
        end = parsed_dates[later]
        comparable = start.notna() & end.notna()
        invalid = comparable & (start > end)
        count = int(invalid.sum())

        add_result(
            results,
            name,
            count == 0,
            f"{count} rows violate the date order." if count
            else "All comparable date pairs follow the expected order.",
        )


# --------------------------------------------------
# 9. CALCULATION VALIDATION
# --------------------------------------------------

def validate_calculations(df, config, results):
    """Validate configured multiplication and subtraction calculations."""
    for rule in config.get("calculation_rules", []):
        target = rule.get("target")
        operation = rule.get("operation")
        columns = rule.get("columns", [])
        name = f"Calculation: {target}"

        required = [target] + columns
        missing = [column for column in required if column not in df.columns]

        if missing:
            add_result(
                results,
                name,
                False,
                f"Missing columns: {missing}",
            )
            continue

        if len(columns) != 2 or operation not in ("multiply", "subtract"):
            add_result(
                results,
                name,
                False,
                "Rule must use two columns and multiply or subtract.",
            )
            continue

        first = pd.to_numeric(df[columns[0]], errors="coerce")
        second = pd.to_numeric(df[columns[1]], errors="coerce")
        actual = pd.to_numeric(df[target], errors="coerce")

        if operation == "multiply":
            expected = first * second
        else:
            expected = first - second

        comparable = expected.notna() & actual.notna()
        invalid = ~comparable
        mismatch = comparable & ((expected - actual).abs() > 0.01)

        mismatch_count = int(mismatch.sum())
        invalid_count = int(invalid.sum())
        passed = mismatch_count == 0 and invalid_count == 0

        add_result(
            results,
            name,
            passed,
            (
                f"{mismatch_count} mismatches; "
                f"{invalid_count} missing or non-numeric rows."
            ),
        )


# --------------------------------------------------
# 10. SAVE VALIDATION REPORT
# --------------------------------------------------

def save_report(results, dataset_path, report_dir):
    """Save validation results as a CSV report."""
    directory = Path(report_dir)
    directory.mkdir(parents=True, exist_ok=True)

    report_path = (
        directory
        / f"{Path(dataset_path).stem}_validation_report.csv"
    )

    pd.DataFrame(
        results,
        columns=["rule", "status", "details"],
    ).to_csv(report_path, index=False)

    print(f"\nValidation report saved to: {report_path.resolve()}")


# --------------------------------------------------
# 11. MAIN VALIDATION PIPELINE
# --------------------------------------------------

def main():
    """Run the configured validation pipeline."""
    parser = argparse.ArgumentParser(
        description="Validate CSV datasets using JSON configuration rules."
    )

    parser.add_argument("dataset", help="Path to the CSV dataset.")
    parser.add_argument("config", help="Path to the JSON configuration.")
    parser.add_argument(
        "--report-dir",
        default="reports",
        help="Directory where validation reports are saved.",
    )

    args = parser.parse_args()

    try:
        config = load_config(args.config)
        df = load_dataset(args.dataset)
        results = []

        # Execute every applicable validation category.
        validate_required_columns(df, config, results)
        validate_missing_values(df, config, results)
        validate_positive_columns(df, config, results)
        validate_non_negative_columns(df, config, results)
        validate_range_rules(df, config, results)
        validate_dates(df, config, results)
        validate_calculations(df, config, results)

        passed = sum(item["status"] == "PASS" for item in results)
        failed = sum(item["status"] == "FAIL" for item in results)

        print("\n" + "=" * 55)
        print(
            "DATA VALIDATION: "
            f"{config.get('dataset_name', Path(args.dataset).stem)}"
        )
        print("=" * 55)
        print(f"Rows checked: {len(df)}")
        print(f"Checks passed: {passed}")
        print(f"Checks failed: {failed}")
        print("-" * 55)

        for item in results:
            print(f"[{item['status']}] {item['rule']}")
            print(f"    {item['details']}")

        print("-" * 55)
        print(f"FINAL STATUS: {'PASS' if failed == 0 else 'FAIL'}")

        save_report(results, args.dataset, args.report_dir)

        if failed:
            sys.exit(1)

    except (FileNotFoundError, ValueError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(2)

    except pd.errors.ParserError as error:
        print(f"CSV ERROR: {error}", file=sys.stderr)
        sys.exit(2)


# Start the program when this file is executed directly.
if __name__ == "__main__":
    main()