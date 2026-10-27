from pathlib import Path

import pandas as pd


# --------------------------------------------------
# 1. Define project paths
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_PATH = PROJECT_ROOT / "data" / "raw" / "b2b_invoices.csv"


# --------------------------------------------------
# 2. Define the columns we expect
# --------------------------------------------------

REQUIRED_COLUMNS = [
    "order_date",
    "invoice_no",
    "customer_id",
    "customer",
    "product_id",
    "product",
    "category",
    "segment",
    "quantity",
    "unit_cost",
    "unit_price",
    "revenue",
    "cost",
    "margin",
    "ship_date",
]


# --------------------------------------------------
# 3. Load the dataset
# --------------------------------------------------

def load_data(file_path: Path) -> pd.DataFrame:
    """Load the raw CSV file into a pandas DataFrame."""

    if not file_path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {file_path}"
        )

    return pd.read_csv(file_path)


# --------------------------------------------------
# 4. Inspect the dataset structure
# --------------------------------------------------

def inspect_structure(df: pd.DataFrame) -> None:
    """Display the basic structure of the dataset."""

    print("\n" + "=" * 50)
    print("DATASET OVERVIEW")
    print("=" * 50)

    print(f"Rows: {len(df):,}")
    print(f"Columns: {len(df.columns)}")

    print("\nColumn names and data types:")
    print(df.dtypes.to_string())

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    unexpected_columns = [
        column
        for column in df.columns
        if column not in REQUIRED_COLUMNS
    ]

    print("\nMissing required columns:")

    if missing_columns:
        print(missing_columns)
    else:
        print("None")

    print("\nUnexpected columns:")

    if unexpected_columns:
        print(unexpected_columns)
    else:
        print("None")


# --------------------------------------------------
# 5. Check data quality
# --------------------------------------------------

def validate_data(df: pd.DataFrame) -> None:
    """Run basic data quality checks."""

    print("\n" + "=" * 50)
    print("DATA QUALITY REPORT")
    print("=" * 50)

    # Missing values
    print("\nMissing values by column:")
    print(df.isna().sum().to_string())

    # Exact duplicate rows
    duplicate_count = df.duplicated().sum()

    print(f"\nExact duplicate rows: {duplicate_count}")

    # Date validation
    order_dates = pd.to_datetime(
        df["order_date"],
        errors="coerce",
    )

    ship_dates = pd.to_datetime(
        df["ship_date"],
        errors="coerce",
    )

    invalid_order_dates = order_dates.isna().sum()
    invalid_ship_dates = ship_dates.isna().sum()

    print(f"Invalid order dates: {invalid_order_dates}")
    print(f"Invalid ship dates: {invalid_ship_dates}")

    # Shipping date should not precede order date
    invalid_shipping_order = (
        ship_dates < order_dates
    ).sum()

    print(
        "Ship dates before order dates: "
        f"{invalid_shipping_order}"
    )

    # Financial calculations
    expected_revenue = (
        df["quantity"] * df["unit_price"]
    ).round(2)

    expected_cost = (
        df["quantity"] * df["unit_cost"]
    )

    expected_margin = (
        df["revenue"] - df["cost"]
    ).round(2)

    revenue_mismatches = (
        df["revenue"].round(2) != expected_revenue
    ).sum()

    cost_mismatches = (
        df["cost"] != expected_cost
    ).sum()

    margin_mismatches = (
        df["margin"].round(2) != expected_margin
    ).sum()

    print(
        "Revenue calculation mismatches: "
        f"{revenue_mismatches}"
    )

    print(
        "Cost calculation mismatches: "
        f"{cost_mismatches}"
    )

    print(
        "Margin calculation mismatches: "
        f"{margin_mismatches}"
    )

    # Positive-value checks
    numeric_columns = [
        "quantity",
        "unit_cost",
        "unit_price",
        "revenue",
        "cost",
    ]

    non_positive_values = (
        df[numeric_columns] <= 0
    ).any(axis=1).sum()

    print(
        "Rows containing non-positive quantities "
        f"or financial values: {non_positive_values}"
    )

    # Investigate unusually large quantities
    large_quantity_count = (
        df["quantity"] > 100
    ).sum()

    print(
        "Rows with quantity above 100 "
        f"(review required): {large_quantity_count}"
    )


# --------------------------------------------------
# 6. Run the inspection
# --------------------------------------------------

def main() -> None:
    """Run the dataset inspection workflow."""

    df = load_data(DATA_PATH)

    inspect_structure(df)

    missing_required_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing_required_columns:
        raise ValueError(
            "Cannot validate the dataset. "
            "Required columns are missing: "
            f"{missing_required_columns}"
        )

    validate_data(df)

    print("\nInspection completed.")


if __name__ == "__main__":
    main()