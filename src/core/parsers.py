"""
Reusable parsers for common retail data formats.

These parsers handle the messy reality of retail data:
- Multiple date formats from different POS systems
- Inconsistent SKU/product code formats
- Case normalization
"""

from datetime import datetime
import pandas as pd


class DateParser:
    """
    Robust date parser that handles multiple formats commonly found in retail data.

    Reusable: Yes - these date formats are common across retail POS systems.
    To extend: Add new format patterns to DATE_FORMATS.
    """

    # Common date formats found in retail systems, ordered by specificity
    DATE_FORMATS = [
        "%Y-%m-%d",      # ISO: 2024-07-25
        "%m/%d/%Y",      # US: 05/27/2024
        "%d-%m-%Y",      # EU: 25-08-2024
        "%m/%d/%y",      # US short: 03/21/24
        "%d/%m/%Y",      # EU slash: 25/08/2024
        "%d/%m/%y",      # EU short: 25/08/24
        "%Y/%m/%d",      # ISO slash: 2024/07/25
    ]

    def __init__(self, custom_formats: list[str] | None = None):
        """
        Args:
            custom_formats: Additional date formats to try (prepended to defaults)
        """
        self.formats = (custom_formats or []) + self.DATE_FORMATS
        self._cache: dict[str, datetime | None] = {}

    def parse(self, date_str: str | None) -> datetime | None:
        """Parse a date string, trying multiple formats."""
        if pd.isna(date_str) or not date_str:
            return None

        date_str = str(date_str).strip()

        if date_str in self._cache:
            return self._cache[date_str]

        for fmt in self.formats:
            try:
                result = datetime.strptime(date_str, fmt)
                self._cache[date_str] = result
                return result
            except ValueError:
                continue

        self._cache[date_str] = None
        return None

    def parse_series(self, series: pd.Series) -> pd.Series:
        """Parse an entire pandas Series of dates."""
        return series.apply(self.parse)


class SKUNormalizer:
    """
    Normalizes SKU/product codes to enable matching across systems.

    Reusable: The normalization logic is reusable.
    Client-specific: The prefix patterns may need customization per client.

    Common patterns handled:
    - SKU-12345 -> 12345
    - SKU12345 -> 12345
    - 012345 -> 12345 (leading zeros)
    - 12345A -> 12345A (preserves meaningful suffixes)
    """

    # Common prefixes to strip (case-insensitive)
    DEFAULT_PREFIXES = ["SKU-", "SKU", "PROD-", "PROD", "ITEM-", "ITEM"]

    def __init__(
        self,
        strip_prefixes: list[str] | None = None,
        strip_leading_zeros: bool = True,
        uppercase: bool = True,
    ):
        """
        Args:
            strip_prefixes: Prefixes to remove (defaults to common retail prefixes)
            strip_leading_zeros: Whether to remove leading zeros from numeric parts
            uppercase: Whether to uppercase the result
        """
        self.prefixes = strip_prefixes or self.DEFAULT_PREFIXES
        self.strip_leading_zeros = strip_leading_zeros
        self.uppercase = uppercase
        # Sort by length descending to match longer prefixes first
        self.prefixes = sorted(self.prefixes, key=len, reverse=True)

    def normalize(self, sku: str | None) -> str | None:
        """Normalize a single SKU."""
        if pd.isna(sku) or not sku:
            return None

        result = str(sku).strip()

        if self.uppercase:
            result = result.upper()

        # Strip known prefixes
        for prefix in self.prefixes:
            prefix_check = prefix.upper() if self.uppercase else prefix
            if result.startswith(prefix_check):
                result = result[len(prefix):]
                break

        # Strip leading zeros from purely numeric SKUs
        if self.strip_leading_zeros and result.isdigit():
            result = result.lstrip("0") or "0"

        return result

    def normalize_series(self, series: pd.Series) -> pd.Series:
        """Normalize an entire pandas Series of SKUs."""
        return series.apply(self.normalize)


class ProductNameNormalizer:
    """
    Normalizes product names for fuzzy matching across systems.

    Handles:
    - Case normalization
    - Extra whitespace
    - Common word variations (e.g., "Set of" prefix)
    """

    def __init__(self, lowercase: bool = True, strip_common_prefixes: bool = True):
        self.lowercase = lowercase
        self.strip_common_prefixes = strip_common_prefixes
        self.common_prefixes = ["set of", "pack of", "box of"]

    def normalize(self, name: str | None) -> str | None:
        """Normalize a product name."""
        if pd.isna(name) or not name:
            return None

        result = str(name).strip()

        # Normalize whitespace
        result = " ".join(result.split())

        if self.lowercase:
            result = result.lower()

        # Optionally strip common prefixes
        if self.strip_common_prefixes:
            for prefix in self.common_prefixes:
                check = prefix if self.lowercase else prefix.title()
                if result.startswith(check + " "):
                    result = result[len(check) + 1:]
                    break

        return result

    def normalize_series(self, series: pd.Series) -> pd.Series:
        """Normalize an entire pandas Series of product names."""
        return series.apply(self.normalize)
