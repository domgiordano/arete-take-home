"""
Inventory health analysis functions.

Computes metrics for:
- Stockout risk
- Dead/slow-moving inventory
- Channel comparison
- Reconciliation gaps
"""

from datetime import datetime, timedelta
import pandas as pd
import numpy as np


def compute_sales_velocity(
    transactions_df: pd.DataFrame,
    sku_col: str = "sku_normalized",
    qty_col: str = "quantity",
    date_col: str = "date_parsed",
    lookback_days: int = 90,
    reference_date: datetime | None = None,
) -> pd.DataFrame:
    """
    Compute daily sales velocity per product.

    Args:
        reference_date: Date to use as "now" for lookback. Defaults to max date in data.

    Returns DataFrame with:
    - sku
    - total_sold (in lookback period)
    - avg_daily_sales
    - days_with_sales
    - last_sale_date
    """
    # Use reference date or max date in data
    if reference_date is None:
        reference_date = transactions_df[date_col].max()
        if pd.isna(reference_date):
            return pd.DataFrame(columns=[sku_col, "total_sold", "avg_daily_sales"])

    # Filter to sales only (positive quantities) and recent period
    cutoff = reference_date - timedelta(days=lookback_days)
    recent = transactions_df[
        (transactions_df[qty_col] > 0) & (transactions_df[date_col] >= cutoff)
    ].copy()

    if len(recent) == 0:
        return pd.DataFrame(columns=[sku_col, "total_sold", "avg_daily_sales"])

    # Aggregate by SKU
    velocity = (
        recent.groupby(sku_col)
        .agg(
            total_sold=(qty_col, "sum"),
            days_with_sales=(date_col, "nunique"),
            last_sale_date=(date_col, "max"),
        )
        .reset_index()
    )

    # Compute daily average
    velocity["avg_daily_sales"] = velocity["total_sold"] / lookback_days

    return velocity


def identify_stockout_risks(
    inventory_df: pd.DataFrame,
    velocity_df: pd.DataFrame,
    inv_sku_col: str = "item_code_normalized",
    inv_qty_col: str = "qty_adjusted",
    inv_reorder_col: str = "reorder_level",
    vel_sku_col: str = "sku_normalized",
    critical_days: int = 7,
    high_days: int = 14,
    medium_days: int = 30,
) -> pd.DataFrame:
    """
    Identify products at risk of stockout.

    Returns DataFrame with products sorted by risk, including:
    - days_of_stock
    - risk_level (critical/high/medium)
    """
    # Handle empty velocity data
    if len(velocity_df) == 0:
        # No sales data - everything has infinite days of stock
        result = inventory_df.copy()
        result["avg_daily_sales"] = 0.0
        result["days_of_stock"] = np.inf
        result["risk_level"] = None
        return result[result["risk_level"].notna()]  # Empty df

    # Merge inventory with velocity
    merged = inventory_df.merge(
        velocity_df, left_on=inv_sku_col, right_on=vel_sku_col, how="left"
    )

    # Fill missing velocity with 0 (no recent sales)
    merged["avg_daily_sales"] = merged["avg_daily_sales"].fillna(0)

    # Compute days of stock (avoid division by zero)
    merged["days_of_stock"] = np.where(
        merged["avg_daily_sales"] > 0,
        merged[inv_qty_col] / merged["avg_daily_sales"],
        np.inf,  # Infinite if no sales
    )

    # Assign risk levels
    def get_risk_level(days):
        if days <= critical_days:
            return "critical"
        elif days <= high_days:
            return "high"
        elif days <= medium_days:
            return "medium"
        return None

    merged["risk_level"] = merged["days_of_stock"].apply(get_risk_level)

    # Filter to only at-risk items and sort
    at_risk = merged[merged["risk_level"].notna()].copy()
    risk_order = {"critical": 0, "high": 1, "medium": 2}
    at_risk["risk_order"] = at_risk["risk_level"].map(risk_order)
    at_risk = at_risk.sort_values(["risk_order", "days_of_stock"])

    return at_risk

def identify_dead_inventory(
    inventory_df: pd.DataFrame,
    transactions_df: pd.DataFrame,
    inv_sku_col: str = "item_code_normalized",
    inv_qty_col: str = "qty_adjusted",
    inv_price_col: str = "retail_price",
    txn_sku_col: str = "sku_normalized",
    txn_date_col: str = "date_parsed",
    txn_qty_col: str = "quantity",
    dead_days_threshold: int = 60,
    min_quantity: int = 1,
    reference_date: datetime | None = None,
) -> pd.DataFrame:
    """
    Identify slow-moving or dead inventory.

    Dead inventory = no sales in X days + quantity on hand >= threshold

    Args:
        reference_date: Date to use as "today" for calculating days since last sale.
                       Defaults to max date in transactions data.

    Returns DataFrame sorted by value at risk.
    """
    # Get last sale date per SKU
    sales = transactions_df[transactions_df[txn_qty_col] > 0].copy()
    last_sales = (
        sales.groupby(txn_sku_col)[txn_date_col]
        .max()
        .reset_index()
        .rename(columns={txn_date_col: "last_sale_date"})
    )

    # Merge with inventory
    merged = inventory_df.merge(
        last_sales, left_on=inv_sku_col, right_on=txn_sku_col, how="left"
    )

    # 1. Handle the None case first (Type Narrowing)
    if reference_date is None:
        reference_date = transactions_df[txn_date_col].max()
    
    # 2. Add a fallback in case the dataframe was empty
    if pd.isna(reference_date):
        reference_date = datetime.now()

    # 3. Ensure last_sale_dates is a Datetime Series
    last_sale_dates = pd.to_datetime(merged["last_sale_date"])
    
    # 4. Perform the math (Pylance is happy now)
    merged["days_since_last_sale"] = (reference_date - last_sale_dates).dt.days

    merged["days_since_last_sale"] = merged["days_since_last_sale"].fillna(999)
    merged["value_at_risk"] = merged[inv_qty_col] * merged[inv_price_col]

    dead = merged[
        (merged["days_since_last_sale"] >= dead_days_threshold)
        & (merged[inv_qty_col] >= min_quantity)
    ].copy()

    return dead.sort_values("value_at_risk", ascending=False)


def compute_channel_comparison(
    pos_df: pd.DataFrame,
    ecom_df: pd.DataFrame,
    pos_qty_col: str = "quantity",
    pos_price_col: str = "unit_price",
    pos_date_col: str = "date_parsed",
    ecom_qty_col: str = "quantity",
    ecom_price_col: str = "unit_price",
    ecom_status_col: str = "status",
) -> dict:
    """
    Compare in-store vs online channel performance.

    Returns dict with various comparison metrics.
    """
    # Filter to sales only
    pos_sales = pos_df[pos_df[pos_qty_col] > 0].copy()
    ecom_sales = ecom_df[ecom_df[ecom_status_col].isin(["completed", "shipped"])].copy()

    # Compute metrics
    pos_revenue = (pos_sales[pos_qty_col] * pos_sales[pos_price_col]).sum()
    ecom_revenue = (ecom_sales[ecom_qty_col] * ecom_sales[ecom_price_col]).sum()

    pos_units = pos_sales[pos_qty_col].sum()
    ecom_units = ecom_sales[ecom_qty_col].sum()

    pos_transactions = len(pos_sales)
    ecom_transactions = len(ecom_sales)

    pos_aov = pos_revenue / pos_transactions if pos_transactions > 0 else 0
    ecom_aov = ecom_revenue / ecom_transactions if ecom_transactions > 0 else 0

    pos_avg_units = pos_units / pos_transactions if pos_transactions > 0 else 0
    ecom_avg_units = ecom_units / ecom_transactions if ecom_transactions > 0 else 0

    # Return rate comparison
    pos_returns = pos_df[pos_df[pos_qty_col] < 0][pos_qty_col].abs().sum()
    ecom_returns = len(ecom_df[ecom_df[ecom_status_col] == "refunded"])

    pos_return_rate = pos_returns / pos_units if pos_units > 0 else 0
    ecom_return_rate = ecom_returns / len(ecom_sales) if len(ecom_sales) > 0 else 0

    return {
        "in_store": {
            "total_revenue": float(pos_revenue),
            "total_units": int(pos_units),
            "transaction_count": pos_transactions,
            "avg_order_value": float(pos_aov),
            "avg_units_per_transaction": float(pos_avg_units),
            "return_rate": float(pos_return_rate),
        },
        "online": {
            "total_revenue": float(ecom_revenue),
            "total_units": int(ecom_units),
            "transaction_count": ecom_transactions,
            "avg_order_value": float(ecom_aov),
            "avg_units_per_transaction": float(ecom_avg_units),
            "return_rate": float(ecom_return_rate),
        },
        "comparison": {
            "revenue_split_instore_pct": float(
                pos_revenue / (pos_revenue + ecom_revenue) * 100
            )
            if (pos_revenue + ecom_revenue) > 0
            else 0,
            "aov_difference": float(ecom_aov - pos_aov),
            "return_rate_difference": float(ecom_return_rate - pos_return_rate),
        },
    }


def find_reconciliation_gaps(
    inventory_df: pd.DataFrame,
    pos_agg_df: pd.DataFrame,
    inv_sku_col: str = "item_code_normalized",
    inv_qty_col: str = "qty_adjusted",
    pos_sku_col: str = "sku_normalized",
    pos_sold_col: str = "total_sold",
    pos_returns_col: str = "return_units",
    min_gap_pct: float = 0.1,  # 10% discrepancy threshold
) -> pd.DataFrame:
    """
    Find discrepancies between inventory system and POS-implied inventory.

    This is a simplified check - real reconciliation would need opening balances.
    We flag items where the sales volume seems inconsistent with current stock.
    """
    # Merge
    merged = inventory_df.merge(
        pos_agg_df, left_on=inv_sku_col, right_on=pos_sku_col, how="outer"
    )

    # Fill NAs
    merged[inv_qty_col] = merged[inv_qty_col].fillna(0)
    merged[pos_sold_col] = merged[pos_sold_col].fillna(0)
    merged[pos_returns_col] = merged[pos_returns_col].fillna(0)

    # Net POS movement
    merged["pos_net_sold"] = merged[pos_sold_col] - merged[pos_returns_col]

    # Flag gaps - items that appear in one system but not the other
    merged["in_inventory_only"] = merged[pos_sku_col].isna()
    merged["in_pos_only"] = merged[inv_sku_col].isna()

    # For items in both, flag unusual ratios
    both_systems = merged[~merged["in_inventory_only"] & ~merged["in_pos_only"]].copy()

    # Flag if current stock < 10% of sales (might be missing inventory)
    # or sales < 10% of stock (system might be wrong)
    both_systems["potential_gap"] = (
        (both_systems[inv_qty_col] < both_systems["pos_net_sold"] * 0.1)
        | (both_systems["pos_net_sold"] < both_systems[inv_qty_col] * 0.1)
    ) & (both_systems[inv_qty_col] > 10)

    gaps = merged[
        merged["in_inventory_only"] | merged["in_pos_only"]
    ].copy()

    return gaps


def compute_key_metrics(
    inventory_df: pd.DataFrame,
    pos_df: pd.DataFrame,
    ecom_df: pd.DataFrame,
    stockout_risks: pd.DataFrame,
    dead_inventory: pd.DataFrame,
) -> dict:
    """Compute summary metrics for the report."""
    pos_sales = pos_df[pos_df["quantity"] > 0]
    ecom_sales = ecom_df[ecom_df["status"].isin(["completed", "shipped"])]

    total_pos_revenue = (pos_sales["quantity"] * pos_sales["unit_price"]).sum()
    total_ecom_revenue = (ecom_sales["quantity"] * ecom_sales["unit_price"]).sum()

    return {
        "total_skus_in_inventory": len(inventory_df),
        "total_inventory_value": float(
            (inventory_df["qty_adjusted"] * inventory_df["retail_price"]).sum()
        ),
        "total_pos_transactions": len(pos_df),
        "total_pos_revenue": float(total_pos_revenue),
        "total_ecom_orders": len(ecom_df),
        "total_ecom_revenue": float(total_ecom_revenue),
        "products_at_stockout_risk": len(stockout_risks),
        "critical_stockout_count": len(
            stockout_risks[stockout_risks["risk_level"] == "critical"]
        ),
        "dead_inventory_value": float(dead_inventory["value_at_risk"].sum())
        if len(dead_inventory) > 0
        else 0,
        "items_below_reorder_level": int(inventory_df["below_reorder_level"].sum()),
        "items_with_manual_overrides": int(
            inventory_df["physical_count_override"].notna().sum()
        ),
        "pos_return_rate": float(
            len(pos_df[pos_df["quantity"] < 0]) / len(pos_sales) * 100
        )
        if len(pos_sales) > 0
        else 0,
    }
