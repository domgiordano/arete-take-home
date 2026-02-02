"""
Client-specific data loader for the distressed retail client.

THIS FILE CONTAINS CLIENT-SPECIFIC HARDCODED LOGIC:
- POS date format variations specific to their system
- SKU normalization rules for their product codes
- Notes column parsing for their inventory management overrides
- Column mappings for their specific exports

To adapt for a new client:
1. Copy this file as a template
2. Update the column mappings in each loader method
3. Adjust the parsing rules (dates, SKUs, notes) to match their data
4. The core parsers and quality checkers can be reused as-is
"""

import re
import json
from pathlib import Path
from dataclasses import dataclass
import pandas as pd

# Handle both package and direct imports
try:
    from ..core.parsers import DateParser, SKUNormalizer, ProductNameNormalizer
    from ..core.quality import DataQualityChecker, DataQualityReport
except ImportError:
    from core.parsers import DateParser, SKUNormalizer, ProductNameNormalizer
    from core.quality import DataQualityChecker, DataQualityReport


@dataclass
class LoadedData:
    """Container for all loaded and cleaned data sources."""

    pos_transactions: pd.DataFrame
    inventory: pd.DataFrame
    ecommerce_orders: pd.DataFrame
    quality_reports: dict[str, DataQualityReport]


class RetailClientLoader:
    """
    Loads and cleans data for the distressed retail client.

    Client-specific quirks handled:
    - POS system uses 4+ different date formats (likely different stores/cashiers)
    - SKUs have inconsistent prefixes (SKU-, SKU, or none) and leading zeros
    - Inventory has manual overrides in Notes column with specific patterns:
      - "Adj: +/-N per Name M/D" (manual adjustments)
      - "Physical count: N (system wrong)" (physical count corrections)
    - E-commerce uses completely different product IDs (ECOM-XXXXXX)
    """

    # Client-specific payment method normalization
    PAYMENT_METHOD_MAP = {
        "cash": "CASH",
        "card": "CARD",
        "credit": "CREDIT",
        "debit": "DEBIT",
        "void": "VOID",
        "test": "TEST",
    }

    def __init__(self, data_dir: Path | str):
        self.data_dir = Path(data_dir)
        self.date_parser = DateParser()
        self.sku_normalizer = SKUNormalizer()
        self.name_normalizer = ProductNameNormalizer()

    def load_all(self) -> LoadedData:
        """Load and clean all data sources."""
        pos = self.load_pos_transactions()
        inv = self.load_inventory()
        ecom = self.load_ecommerce()

        # Run quality checks
        quality_reports = {
            "pos": self._check_pos_quality(pos),
            "inventory": self._check_inventory_quality(inv),
            "ecommerce": self._check_ecommerce_quality(ecom),
        }

        return LoadedData(
            pos_transactions=pos,
            inventory=inv,
            ecommerce_orders=ecom,
            quality_reports=quality_reports,
        )

    def load_pos_transactions(self) -> pd.DataFrame:
        """
        Load and clean POS transaction data.

        Client-specific handling:
        - Multiple date formats
        - SKU normalization
        - Payment method standardization
        - Quantity can be negative (returns)
        """
        df = pd.read_csv(self.data_dir / "pos_transactions.csv")

        # Parse dates (handles multiple formats)
        df["date_parsed"] = self.date_parser.parse_series(df["date"])

        # Normalize SKUs
        df["sku_normalized"] = self.sku_normalizer.normalize_series(df["sku"])

        # Normalize product names
        df["product_name_normalized"] = self.name_normalizer.normalize_series(
            df["product_name"]
        )

        # Standardize payment methods
        df["payment_method_clean"] = (
            df["payment_method"]
            .fillna("")
            .str.lower()
            .str.strip()
            .map(self.PAYMENT_METHOD_MAP)
        )

        # Flag returns
        df["is_return"] = df["quantity"] < 0

        # Calculate line total
        df["line_total"] = df["quantity"] * df["unit_price"]

        return df

    def load_inventory(self) -> pd.DataFrame:
        """
        Load and clean inventory management data.

        Client-specific handling:
        - Notes column contains manual overrides that ops team uses
        - Parse out physical count corrections
        - Parse out manual adjustments
        """
        df = pd.read_excel(self.data_dir / "inventory_management.xlsx")

        # Normalize column names
        df.columns = [c.lower().replace(" ", "_") for c in df.columns]

        # Normalize item codes to match POS SKUs
        df["item_code_normalized"] = self.sku_normalizer.normalize_series(
            df["item_code"]
        )

        # Normalize product names
        df["description_normalized"] = self.name_normalizer.normalize_series(
            df["description"]
        )

        # Parse notes column for corrections
        df["physical_count_override"] = df["notes"].apply(self._parse_physical_count)
        df["adjustment"] = df["notes"].apply(self._parse_adjustment)

        # Calculate "true" quantity (applying any physical count overrides)
        df["qty_adjusted"] = df.apply(
            lambda r: r["physical_count_override"]
            if pd.notna(r["physical_count_override"])
            else r["qty_on_hand"],
            axis=1,
        )

        # Flag items below reorder level
        df["below_reorder_level"] = df["qty_adjusted"] < df["reorder_level"]

        # Parse last count date
        df["last_count_date_parsed"] = self.date_parser.parse_series(
            df["last_count_date"]
        )

        return df

    def _parse_physical_count(self, notes: str | None) -> int | None:
        """
        Parse physical count from notes.

        Pattern: "Physical count: 78 (system wrong)"
        """
        if pd.isna(notes):
            return None

        match = re.search(r"Physical count:\s*(\d+)", notes, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None

    def _parse_adjustment(self, notes: str | None) -> int | None:
        """
        Parse adjustment from notes.

        Pattern: "Adj: +15 per Sarah 5/4" or "Adj: -3 per Mike 6/21"
        """
        if pd.isna(notes):
            return None

        match = re.search(r"Adj:\s*([+-]?\d+)", notes, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None

    def load_ecommerce(self) -> pd.DataFrame:
        """
        Load and clean e-commerce order data.

        Client-specific handling:
        - Different product ID scheme (ECOM-XXXXXX)
        - Order status filtering (completed, shipped, cancelled, refunded)
        """
        with open(self.data_dir / "ecommerce_export.json") as f:
            data = json.load(f)

        df = pd.DataFrame(data["orders"])

        # Store metadata
        df["export_date"] = data["export_date"]
        df["platform"] = data["platform"]

        # Parse order dates
        df["order_date_parsed"] = pd.to_datetime(df["order_date"])

        # Normalize product names to enable matching
        df["product_name_normalized"] = self.name_normalizer.normalize_series(
            df["product_name"]
        )

        # Extract numeric part of product ID for potential matching
        df["product_id_numeric"] = df["product_id"].str.extract(r"ECOM-(\d+)")[0]

        # Flag completed orders (for sales analysis)
        df["is_sale"] = df["status"].isin(["completed", "shipped"])

        return df

    def _check_pos_quality(self, df: pd.DataFrame) -> DataQualityReport:
        """Run quality checks on POS data."""
        checker = DataQualityChecker("POS Transactions")

        # Check for unparseable dates
        checker.add_check(
            lambda d: self._check_unparsed(d, "date", "date_parsed", "unparsed_date")
        )

        # Check for test/void transactions
        checker.check_invalid_values(
            "payment_method_clean",
            valid_values={"CASH", "CARD", "CREDIT", "DEBIT"},
            severity="warning",
        )

        # Check for unusual quantities
        checker.check_outliers("quantity", min_val=-50, max_val=100, severity="warning")

        # Check for unusual prices
        checker.check_outliers(
            "unit_price", min_val=0.01, max_val=500, severity="warning"
        )

        return checker.run(df)

    def _check_inventory_quality(self, df: pd.DataFrame) -> DataQualityReport:
        """Run quality checks on inventory data."""
        try:
            from ..core.quality import DataQualityIssue
        except ImportError:
            from core.quality import DataQualityIssue

        checker = DataQualityChecker("Inventory Management")

        # Check for negative quantities
        checker.check_outliers("qty_on_hand", min_val=0, severity="critical")

        # Check for items with overrides (info level - these are expected)
        def check_overrides(d):
            if d["physical_count_override"].notna().any():
                count = d["physical_count_override"].notna().sum()
                return [
                    DataQualityIssue(
                        column="physical_count_override",
                        issue_type="manual_override",
                        severity="info",
                        count=count,
                        percentage=(count / len(d)) * 100,
                        description=f"{count} items have manual count overrides",
                    )
                ]
            return []

        checker.add_check(check_overrides)

        return checker.run(df)

    def _check_ecommerce_quality(self, df: pd.DataFrame) -> DataQualityReport:
        """Run quality checks on e-commerce data."""
        checker = DataQualityChecker("E-commerce Orders")

        # Check order status distribution
        checker.check_invalid_values(
            "status",
            valid_values={"completed", "shipped", "cancelled", "refunded", "processing"},
            severity="critical",
        )

        return checker.run(df)

    def _check_unparsed(
        self, df: pd.DataFrame, original_col: str, parsed_col: str, issue_type: str
    ) -> list:
        """Check for values that couldn't be parsed."""
        try:
            from ..core.quality import DataQualityIssue
        except ImportError:
            from core.quality import DataQualityIssue

        unparsed = df[original_col].notna() & df[parsed_col].isna()
        count = unparsed.sum()
        if count > 0:
            samples = df.loc[unparsed, original_col].head(5).tolist()
            return [
                DataQualityIssue(
                    column=original_col,
                    issue_type=issue_type,
                    severity="warning",
                    count=count,
                    percentage=(count / len(df)) * 100,
                    sample_values=samples,
                    description=f"{count:,} values couldn't be parsed",
                )
            ]
        return []
