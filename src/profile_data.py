
from pathlib import Path
import argparse

import pandas as pd


# ============================================================
# 1. LOAD THE DATASET
# ============================================================

def load_data(file_path: Path) -> pd.DataFrame:
    """Load a CSV file into a pandas DataFrame."""

    if not file_path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {file_path}"
        )

    if not file_path.is_file():
        raise ValueError(
            f"The supplied path is not a file: {file_path}"
        )

    if file_path.suffix.lower() != ".csv":
        raise ValueError(
            "This profiler currently supports CSV files only."
        )

    df = pd.read_csv(file_path)

    if len(df.columns) == 0:
        raise ValueError(
            "The CSV file does not contain any columns."
        )

    return df


# ============================================================
# 2. PROFILE DATASET STRUCTURE
# ============================================================

def profile_structure(df: pd.DataFrame) -> None:
    """Display the dataset's overall structure."""

    print("\n" + "=" * 60)
    print("DATASET OVERVIEW")
    print("=" * 60)

    print(f"Number of rows: {len(df):,}")
    print(f"Number of columns: {len(df.columns)}")

    print("\nColumn names:")

    for column in df.columns:
        print(f"  - {column}")

    print("\nData types:")
    print(df.dtypes.to_string())


# ============================================================
# 3. PROFILE MISSING VALUES
# ============================================================

def profile_missing_values(df: pd.DataFrame) -> None:
    """Count missing values in each column."""

    print("\n" + "=" * 60)
    print("MISSING VALUES")
    print("=" * 60)

    missing_counts = df.isna().sum()

    missing_report = pd.DataFrame({
        "missing_count": missing_counts,
        "missing_percentage": (
            missing_counts / len(df) * 100
            if len(df) > 0
            else 0
        ),
    })

    print(missing_report.to_string())


# ============================================================
# 4. PROFILE DUPLICATE ROWS
# ============================================================

def profile_duplicates(df: pd.DataFrame) -> None:
    """Count exact duplicate rows."""

    print("\n" + "=" * 60)
    print("DUPLICATE ROWS")
    print("=" * 60)

    duplicate_count = int(df.duplicated().sum())

    print(f"Exact duplicate rows: {duplicate_count:,}")


# ============================================================
# 5. PROFILE UNIQUE VALUES
# ============================================================

def profile_unique_values(df: pd.DataFrame) -> None:
    """Count distinct values in each column."""

    print("\n" + "=" * 60)
    print("UNIQUE VALUES")
    print("=" * 60)

    for column in df.columns:
        unique_count = df[column].nunique(dropna=True)

        print(
            f"{column}: {unique_count:,} unique values"
        )


# ============================================================
# 6. PROFILE NUMERIC COLUMNS
# ============================================================

def profile_numeric_columns(df: pd.DataFrame) -> None:
    """Display statistics for numeric columns."""

    print("\n" + "=" * 60)
    print("NUMERIC COLUMN STATISTICS")
    print("=" * 60)

    numeric_df = df.select_dtypes(include="number")

    if numeric_df.empty:
        print("No numeric columns detected.")
        return

    print(numeric_df.describe().round(2).to_string())


# ============================================================
# 7. PROFILE CATEGORICAL COLUMNS
# ============================================================

def profile_categorical_columns(
    df: pd.DataFrame,
    top_n: int = 5,
) -> None:
    """Display the most common values in categorical columns."""

    print("\n" + "=" * 60)
    print("CATEGORICAL COLUMN STATISTICS")
    print("=" * 60)

    categorical_df = df.select_dtypes(
        include=["object", "category", "string"]
    )

    if categorical_df.empty:
        print("No categorical columns detected.")
        return

    for column in categorical_df.columns:
        print(f"\nColumn: {column}")

        print(
            df[column]
            .value_counts(dropna=False)
            .head(top_n)
            .to_string()
        )


# ============================================================
# 8. CREATE A REUSABLE PROFILE REPORT
# ============================================================

def create_profile_report(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """Create a summary report for every column."""

    missing_counts = df.isna().sum()

    if len(df) > 0:
        missing_percentages = (
            df.isna().mean().mul(100).round(2)
        )
    else:
        missing_percentages = pd.Series(
            0.0,
            index=df.columns,
        )

    report = pd.DataFrame({
        "column_name": df.columns,
        "data_type": [
            str(dtype) for dtype in df.dtypes
        ],
        "missing_count": missing_counts.values,
        "missing_percentage": missing_percentages.values,
        "unique_values": [
            df[column].nunique(dropna=True)
            for column in df.columns
        ],
    })

    # Exact duplicate count applies to the entire dataset,
    # not to an individual column.
    report["dataset_exact_duplicate_rows"] = int(
        df.duplicated().sum()
    )

    return report


# ============================================================
# 9. SAVE THE PROFILE REPORT
# ============================================================

def save_profile_report(
    report: pd.DataFrame,
    source_file: Path,
) -> Path:
    """Save the profile report in the project's reports folder."""

    # The project root is the parent of the source folder
    # containing this Python script.
    project_root = Path(__file__).resolve().parents[1]

    report_dir = project_root / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    # Use the source filename to avoid overwriting reports
    # for different datasets.
    report_path = (
        report_dir / f"{source_file.stem}_profile_report.csv"
    )

    report.to_csv(report_path, index=False)

    return report_path


# ============================================================
# 10. RUN THE COMPLETE PROFILING WORKFLOW
# ============================================================

def profile_dataset(df: pd.DataFrame) -> None:
    """Run all general-purpose profiling functions."""

    profile_structure(df)
    profile_missing_values(df)
    profile_duplicates(df)
    profile_unique_values(df)
    profile_numeric_columns(df)
    profile_categorical_columns(df)


# ============================================================
# 11. COMMAND-LINE ENTRY POINT
# ============================================================

def main() -> None:
    """Accept a CSV path, profile it, and save a report."""

    parser = argparse.ArgumentParser(
        description=(
            "Profile a CSV dataset and save a summary report."
        )
    )

    parser.add_argument(
        "file_path",
        help="Path to the CSV file to profile.",
    )

    args = parser.parse_args()

    file_path = Path(args.file_path)

    try:
        df = load_data(file_path)

        print(f"\nProfiling file: {file_path.resolve()}")

        profile_dataset(df)

        report = create_profile_report(df)

        report_path = save_profile_report(
            report,
            file_path,
        )

        print("\n" + "=" * 60)
        print("REPORT GENERATED SUCCESSFULLY")
        print("=" * 60)

        print(f"Report saved to: {report_path}")

        print("\nProfiling completed successfully.")

    except (FileNotFoundError, ValueError, pd.errors.ParserError) as error:
        parser.exit(
            status=1,
            message=f"\nERROR: {error}\n",
        )


if __name__ == "__main__":
    main()