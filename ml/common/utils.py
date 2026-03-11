"""Encoding helpers, currency conversion, and shared constants."""

import pandas as pd
import numpy as np


# --- Currency conversion rates to USD ---
CURRENCY_RATES = {
    "USD": 1.0,
    "EUR": 1.08,
    "JPY": 0.0067,
    "SGD": 0.74,
    "KRW": 0.00075,
    "THB": 0.028,
    "CNY": 0.14,
    "VND": 0.000041,
    "GBP": 1.27,
    "CHF": 1.13,
}


def convert_to_usd(amount: float | pd.Series, currency: str | pd.Series) -> float | pd.Series:
    """Convert amount(s) to USD using fixed exchange rates.

    Args:
        amount: Scalar or Series of amounts.
        currency: Scalar or Series of currency codes.

    Returns:
        Amount(s) in USD.
    """
    if isinstance(currency, pd.Series):
        rates = currency.map(CURRENCY_RATES).fillna(1.0)
        return amount * rates
    return amount * CURRENCY_RATES.get(currency, 1.0)


# --- Country risk mapping ---
COUNTRY_RISK_MAP = {
    "JP": 1, "DE": 1, "US": 1,
    "SG": 2, "KR": 2,
    "TH": 3, "CN": 3,
    "VN": 4,
}


# --- Payment terms to days ---
PAYMENT_TERMS_DAYS = {
    "NET30": 30,
    "NET60": 60,
    "NET90": 90,
    "2/10NET30": 30,
    "IMMEDIATE": 0,
}


def encode_ordinal(series: pd.Series, mapping: dict) -> pd.Series:
    """Map categorical values to ordinal integers.

    Args:
        series: Categorical pandas Series.
        mapping: Dict mapping category values to integers.

    Returns:
        Integer-encoded Series. Unmapped values become -1.
    """
    return series.map(mapping).fillna(-1).astype(int)


def encode_onehot(df: pd.DataFrame, column: str, prefix: str | None = None) -> pd.DataFrame:
    """One-hot encode a column and drop the original.

    Args:
        df: Input DataFrame.
        column: Column name to encode.
        prefix: Prefix for new columns (defaults to column name).

    Returns:
        DataFrame with one-hot encoded columns replacing the original.
    """
    if prefix is None:
        prefix = column
    dummies = pd.get_dummies(df[column], prefix=prefix, dtype=int)
    return pd.concat([df.drop(columns=[column]), dummies], axis=1)


# --- Ordinal mappings for common fields ---
CRITICALITY_MAP = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
CONFIDENTIALITY_MAP = {"PUBLIC": 0, "INTERNAL": 1, "RESTRICTED": 2}
VENDOR_STATUS_MAP = {"ACTIVE": 2, "CONDITIONAL": 1, "BLOCKED": 0}
VENDOR_TYPE_MAP = {"OEM": 0, "DISTRIBUTOR": 1, "CONTRACT_MFG": 2, "LOGISTICS": 3, "SERVICE": 4}
