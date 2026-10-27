
import sys
from pathlib import Path

import pandas as pd
import pytest

# Make the project's src directory available to Python.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from clean_data import clean_dataset


@pytest.fixture
def sample_dataframe():
    """Provide a small dataset for repeatable cleaning tests."""
    return pd.DataFrame(
        {
            "customer": [" Alice ", "Bob", "   ", "Bob"],
            "quantity": ["2", "3", "4", "3"],
            "order_date": [
                "2026-01-01",
                "2026-01-02",
                "2026-01-03",
                "2026-01-02",
            ],
        }
    )


@pytest.fixture
def sample_config():
    """Provide the configuration used in the tests."""
    return {
        "dataset_name": "test_sales",
        "numeric_columns": ["quantity"],
        "date_columns": ["order_date"],
    }


def test_clean_dataset_does_not_modify_original(
    sample_dataframe, sample_config
):
    original = sample_dataframe.copy(deep=True)

    clean_dataset(sample_dataframe, sample_config)

    pd.testing.assert_frame_equal(sample_dataframe, original)


def test_whitespace_is_trimmed(sample_dataframe, sample_config):
    cleaned, _ = clean_dataset(sample_dataframe, sample_config)

    assert cleaned.loc[0, "customer"] == "Alice"
    assert cleaned.loc[1, "customer"] == "Bob"


def test_blank_strings_become_missing_values(
    sample_dataframe, sample_config
):
    cleaned, _ = clean_dataset(sample_dataframe, sample_config)

    assert pd.isna(cleaned.loc[2, "customer"])


def test_numeric_columns_are_converted(sample_dataframe, sample_config):
    cleaned, _ = clean_dataset(sample_dataframe, sample_config)

    assert pd.api.types.is_numeric_dtype(cleaned["quantity"])
    assert cleaned["quantity"].tolist() == [2, 3, 4, 3]


def test_date_columns_are_converted(sample_dataframe, sample_config):
    cleaned, _ = clean_dataset(sample_dataframe, sample_config)

    assert pd.api.types.is_datetime64_any_dtype(cleaned["order_date"])


def test_duplicate_rows_are_reported_not_deleted(
    sample_dataframe, sample_config
):
    cleaned, report = clean_dataset(sample_dataframe, sample_config)

    duplicate_report = report.loc[
        report["operation"] == "duplicate_detection"
    ]

    assert len(cleaned) == len(sample_dataframe)
    assert len(duplicate_report) == 1
    assert duplicate_report.iloc[0]["values_before"] == 1


def test_invalid_numeric_values_become_missing():
    df = pd.DataFrame({"quantity": ["10", "invalid", "20"]})

    config = {
        "dataset_name": "invalid_numeric_test",
        "numeric_columns": ["quantity"],
    }

    cleaned, report = clean_dataset(df, config)

    assert cleaned["quantity"].isna().sum() == 1

    conversion_report = report.loc[
        (report["column"] == "quantity")
        & (report["operation"] == "numeric_conversion")
    ]

    assert len(conversion_report) == 1

    assert (
        "invalid values converted to missing: 1"
        in conversion_report.iloc[0]["details"]
    )


def test_invalid_dates_become_missing():
    df = pd.DataFrame(
        {"order_date": ["2026-01-01", "not-a-date"]}
    )

    config = {
        "dataset_name": "invalid_date_test",
        "date_columns": ["order_date"],
    }

    cleaned, report = clean_dataset(df, config)

    assert cleaned["order_date"].isna().sum() == 1

    date_report = report.loc[
        (report["column"] == "order_date")
        & (report["operation"] == "date_conversion")
    ]

    assert len(date_report) == 1

    assert (
        "unparseable non-missing values: 1"
        in date_report.iloc[0]["details"]
    )


def test_missing_configured_columns_are_reported():
    df = pd.DataFrame({"customer": ["Alice"]})

    config = {
        "dataset_name": "missing_column_test",
        "numeric_columns": ["quantity"],
        "date_columns": ["order_date"],
    }

    _, report = clean_dataset(df, config)

    skipped = report.loc[
        report["operation"].isin(
            ["numeric_conversion", "date_conversion"]
        )
    ]

    assert len(skipped) == 2

    assert all(
        skipped["details"].str.contains(
            "SKIPPED: configured column does not exist."
        )
    )


def test_cleaning_report_has_expected_columns(
    sample_dataframe, sample_config
):
    _, report = clean_dataset(sample_dataframe, sample_config)

    expected_columns = {
        "dataset",
        "column",
        "operation",
        "values_before",
        "values_after",
        "details",
    }

    assert expected_columns.issubset(set(report.columns))
    assert not report.empty