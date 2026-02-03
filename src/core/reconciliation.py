"""
Reusable reconciliation engine for matching records across data sources.

Handles the common retail challenge of matching products/inventory
across systems that use different identifiers.
"""

from dataclasses import dataclass, field
from typing import Callable, Any
from enum import Enum
import pandas as pd


class MatchType(Enum):
    """How a match was determined."""

    EXACT_ID = "exact_id"  # Matched on normalized ID
    EXACT_NAME = "exact_name"  # Matched on normalized name
    FUZZY_NAME = "fuzzy_name"  # Matched on fuzzy name similarity
    MANUAL = "manual"  # Manual mapping provided
    UNMATCHED = "unmatched"  # No match found


@dataclass
class MatchResult:
    """Result of matching a single record."""

    source_key: Any
    target_key: Any | None
    match_type: MatchType
    confidence: float  # 0-1
    source_record: dict
    target_record: dict | None = None


@dataclass
class ReconciliationResult:
    """Summary of reconciliation between two data sources."""

    source_name: str
    target_name: str
    total_source_records: int
    matched_records: int
    unmatched_records: int
    matches: list[MatchResult] = field(default_factory=list)

    @property
    def match_rate(self) -> float:
        if self.total_source_records == 0:
            return 0
        return self.matched_records / self.total_source_records

    def unmatched_items(self) -> list[MatchResult]:
        return [m for m in self.matches if m.match_type == MatchType.UNMATCHED]

    def summary(self) -> dict:
        return {
            "source": self.source_name,
            "target": self.target_name,
            "total": self.total_source_records,
            "matched": self.matched_records,
            "unmatched": self.unmatched_records,
            "match_rate": f"{self.match_rate:.1%}",
        }


class ReconciliationEngine:
    """
    Matches records across data sources using multiple strategies.

    Reusable pattern:
    1. Try exact ID match (after normalization)
    2. Try exact name match (after normalization)
    3. Optionally try fuzzy name matching
    4. Apply any manual mappings

    Usage:
        engine = ReconciliationEngine(source_df, target_df)
        engine.add_id_match("sku", "item_code", normalizer=sku_normalizer)
        engine.add_name_match("product_name", "description")
        result = engine.reconcile()
    """

    def __init__(
        self,
        source_df: pd.DataFrame,
        target_df: pd.DataFrame,
        source_name: str = "source",
        target_name: str = "target",
    ):
        self.source_df = source_df.copy()
        self.target_df = target_df.copy()
        self.source_name = source_name
        self.target_name = target_name
        self._matchers: list[
            tuple[str, Callable[[pd.Series, pd.DataFrame], pd.Series | None]]
        ] = []
        self._manual_mappings: dict[Any, Any] = {}

    def add_id_match(
        self,
        source_col: str,
        target_col: str,
        normalizer: Callable[[Any], Any] | None = None,
    ) -> "ReconciliationEngine":
        """Add an ID-based matching strategy."""

        def matcher(source_vals: pd.Series, target: pd.DataFrame) -> pd.Series:
            # Normalize if needed
            if normalizer:
                src_normalized = source_vals.apply(normalizer)
                tgt_normalized = target[target_col].apply(normalizer)
            else:
                src_normalized = source_vals
                tgt_normalized = target[target_col]

            # Create lookup
            tgt_lookup = dict(zip(tgt_normalized, target.index))

            # Match
            return src_normalized.map(tgt_lookup)

        self._matchers.append((MatchType.EXACT_ID.value, matcher))
        return self

    def add_name_match(
        self,
        source_col: str,
        target_col: str,
        normalizer: Callable[[Any], Any] | None = None,
    ) -> "ReconciliationEngine":
        """Add a name-based matching strategy."""

        def default_normalize(s):
            if pd.isna(s):
                return None
            return str(s).lower().strip()

        norm = normalizer or default_normalize

        def matcher(source_vals: pd.Series, target: pd.DataFrame) -> pd.Series:
            src_normalized = source_vals.apply(norm)
            tgt_normalized = target[target_col].apply(norm)

            # Create lookup
            tgt_lookup = dict(zip(tgt_normalized, target.index))

            # Match
            return src_normalized.map(tgt_lookup)

        self._matchers.append((MatchType.EXACT_NAME.value, matcher))
        return self

    def add_manual_mapping(self, mappings: dict[Any, Any]) -> "ReconciliationEngine":
        """Add manual source->target mappings for known problem cases."""
        self._manual_mappings.update(mappings)
        return self

    def reconcile(self, source_key_col: str) -> ReconciliationResult:
        """
        Run reconciliation and return results.

        Args:
            source_key_col: Column to use as source key for tracking matches
        """
        matches = []
        matched_count = 0

        for idx, row in self.source_df.iterrows():
            source_key = row[source_key_col]
            matched_idx = None
            match_type = MatchType.UNMATCHED
            confidence = 0.0

            # Check manual mappings first
            if source_key in self._manual_mappings:
                target_key = self._manual_mappings[source_key]
                target_matches = self.target_df[
                    self.target_df.iloc[:, 0] == target_key
                ]
                if len(target_matches) > 0:
                    matched_idx = target_matches.index[0]
                    match_type = MatchType.MANUAL
                    confidence = 1.0

            # Try each matcher in order
            if matched_idx is None:
                for match_type_name, matcher in self._matchers:
                    result = matcher(pd.Series([source_key]), self.target_df)
                    if result is not None and pd.notna(result.iloc[0]):
                        matched_idx = result.iloc[0]
                        match_type = MatchType(match_type_name)
                        confidence = 1.0
                        break

            # Build result
            target_record = None
            target_key = None
            if matched_idx is not None:
                target_record = self.target_df.loc[matched_idx].to_dict()
                target_key = matched_idx
                matched_count += 1

            matches.append(
                MatchResult(
                    source_key=source_key,
                    target_key=target_key,
                    match_type=match_type,
                    confidence=confidence,
                    source_record=row.to_dict(),
                    target_record=target_record,
                )
            )

        return ReconciliationResult(
            source_name=self.source_name,
            target_name=self.target_name,
            total_source_records=len(self.source_df),
            matched_records=matched_count,
            unmatched_records=len(self.source_df) - matched_count,
            matches=matches,
        )


def aggregate_sales_by_product(
    transactions_df: pd.DataFrame,
    sku_col: str = "sku",
    qty_col: str = "quantity",
    price_col: str = "unit_price",
    date_col: str = "date",
) -> pd.DataFrame:
    """
    Aggregate transaction-level data to product-level sales summary.

    Reusable across retail clients - just specify column names.

    Returns DataFrame with:
    - total_units_sold
    - total_revenue
    - avg_unit_price
    - transaction_count
    - first/last_sale_date
    - return_units (negative quantities)
    """
    # Handle returns separately
    sales = transactions_df[transactions_df[qty_col] >= 0].copy()
    returns = transactions_df[transactions_df[qty_col] < 0].copy()

    # Aggregate sales
    sales_agg = (
        sales.groupby(sku_col)
        .agg(
            total_units_sold=(qty_col, "sum"),
            total_revenue=(
                qty_col,
                lambda x: (x * sales.loc[x.index, price_col]).sum(),
            ),
            avg_unit_price=(price_col, "mean"),
            transaction_count=(sku_col, "count"),
            first_sale_date=(date_col, "min"),
            last_sale_date=(date_col, "max"),
        )
        .reset_index()
    )

    # Aggregate returns
    if len(returns) > 0:
        return_agg = (
            returns.groupby(sku_col)[qty_col].sum().abs().reset_index()
        )
        return_agg.columns = [sku_col, "return_units"]
        sales_agg = sales_agg.merge(return_agg, on=sku_col, how="left")
        sales_agg["return_units"] = sales_agg["return_units"].fillna(0)
    else:
        sales_agg["return_units"] = 0

    return sales_agg
