# Core reusable components for retail data reconciliation
# These patterns can be reused across different retail clients

from .parsers import DateParser, SKUNormalizer, ProductNameNormalizer
from .quality import DataQualityReport, DataQualityChecker
from .reconciliation import ReconciliationEngine, ReconciliationResult
from .analysis import (
    compute_sales_velocity,
    identify_stockout_risks,
    identify_dead_inventory,
    compute_channel_comparison,
    find_reconciliation_gaps,
    compute_key_metrics,
)
from .insights import InsightGenerator, InventoryHealthReport

__all__ = [
    "DateParser",
    "SKUNormalizer",
    "ProductNameNormalizer",
    "DataQualityReport",
    "DataQualityChecker",
    "ReconciliationEngine",
    "ReconciliationResult",
    "compute_sales_velocity",
    "identify_stockout_risks",
    "identify_dead_inventory",
    "compute_channel_comparison",
    "find_reconciliation_gaps",
    "compute_key_metrics",
    "InsightGenerator",
    "InventoryHealthReport",
]
