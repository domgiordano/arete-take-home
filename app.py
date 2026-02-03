"""
Inventory Health Dashboard

A Streamlit dashboard for exploring inventory health insights.
Run with: streamlit run app.py
"""

import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from clients.retail_client import RetailClientLoader
from core.analysis import (
    compute_sales_velocity,
    identify_stockout_risks,
    identify_dead_inventory,
    compute_channel_comparison,
)

# Page config
st.set_page_config(
    page_title="Inventory Health Dashboard",
    page_icon="📦",
    layout="wide",
)

st.title("📦 Inventory Health Dashboard")
st.caption("Retail Client - December 2024 Analysis")


def aggregate_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate duplicate products by normalized description.

    Same product with multiple item_codes gets combined:
    - qty_adjusted: SUM (total inventory across all codes)
    - reorder_level: MAX (most conservative threshold)
    - retail_price: MEAN (average for valuation)
    - Other fields: FIRST (keep one representative value)
    """
    result = df.groupby('description_normalized').agg({
        'item_code': 'first',
        'description': 'first',
        'category': 'first',
        'qty_on_hand': 'sum',
        'qty_adjusted': 'sum',
        'reorder_level': 'max',
        'retail_price': 'mean',
        'physical_count_override': 'first',
    }).reset_index()

    # Recalculate below_reorder_level AFTER aggregation
    # (aggregated qty vs aggregated reorder level)
    result['below_reorder_level'] = result['qty_adjusted'] < result['reorder_level']

    return result


@st.cache_data
def load_data():
    """Load and process all data (cached for performance)."""
    loader = RetailClientLoader(Path("data/raw"))
    data = loader.load_all()

    # --- DATA QUALITY FIXES ---
    # Note: description_normalized (inventory) and product_name_normalized (POS)
    # are already created by the RetailClientLoader

    # 1. Aggregate duplicates in inventory (51 products have multiple item codes)
    inv_aggregated = aggregate_duplicates(data.inventory)

    # 2. Filter placeholder dates (1900-01-01) before velocity calculation
    pos_clean = data.pos_transactions[
        data.pos_transactions['date_parsed'] >= datetime(2020, 1, 1)
    ].copy()

    # 3. Use reference date from data (not system date) - data is from Dec 2024
    reference_date = pos_clean['date_parsed'].max()

    # Compute velocity using product_name_normalized (POS column name)
    velocity = compute_sales_velocity(
        pos_clean,
        sku_col="product_name_normalized",
        qty_col="quantity",
        date_col="date_parsed",
        reference_date=reference_date,
    )

    # Compute stockout risks with CORRECT thresholds (3/7/14 for high-velocity retail)
    # Note: inventory uses description_normalized, velocity uses product_name_normalized
    # These should match as they're both normalized product names
    stockout = identify_stockout_risks(
        inv_aggregated,
        velocity,
        inv_sku_col="description_normalized",
        inv_qty_col="qty_adjusted",
        vel_sku_col="product_name_normalized",
        critical_days=3,   # ≤3 days = critical (reorder TODAY)
        high_days=7,       # ≤7 days = high (reorder THIS WEEK)
        medium_days=14,    # ≤14 days = medium
    )

    # Compute dead inventory
    dead = identify_dead_inventory(
        inv_aggregated,
        pos_clean,
        inv_sku_col="description_normalized",
        inv_qty_col="qty_adjusted",
        inv_price_col="retail_price",
        txn_sku_col="product_name_normalized",
        txn_date_col="date_parsed",
        reference_date=reference_date,
    )

    # Channel comparison
    channel = compute_channel_comparison(data.pos_transactions, data.ecommerce_orders)

    # Compute key metrics
    pos_sales = pos_clean[pos_clean["quantity"] > 0]
    ecom_sales = data.ecommerce_orders[data.ecommerce_orders["status"].isin(["completed", "shipped"])]

    total_pos_revenue = (pos_sales["quantity"] * pos_sales["unit_price"]).sum()
    total_ecom_revenue = (ecom_sales["quantity"] * ecom_sales["unit_price"]).sum()

    metrics = {
        "total_skus_in_inventory": len(inv_aggregated),
        "total_skus_raw": len(data.inventory),
        "duplicates_found": len(data.inventory) - len(inv_aggregated),
        "total_inventory_value": float(
            (inv_aggregated["qty_adjusted"] * inv_aggregated["retail_price"]).sum()
        ),
        "total_pos_transactions": len(data.pos_transactions),
        "total_pos_revenue": float(total_pos_revenue),
        "total_ecom_orders": len(data.ecommerce_orders),
        "total_ecom_revenue": float(total_ecom_revenue),
        "products_at_stockout_risk": len(stockout),
        "critical_stockout_count": len(stockout[stockout["risk_level"] == "critical"]),
        "high_stockout_count": len(stockout[stockout["risk_level"] == "high"]),
        "dead_inventory_value": float(dead["value_at_risk"].sum()) if len(dead) > 0 else 0,
        "dead_inventory_count": len(dead),
        "items_below_reorder_level": int(inv_aggregated["below_reorder_level"].sum()),
        "placeholder_dates_filtered": len(data.pos_transactions) - len(pos_clean),
    }

    return data, inv_aggregated, velocity, stockout, dead, channel, metrics


# Load data
with st.spinner("Loading data..."):
    data, inv_aggregated, velocity, stockout_risks, dead_inventory, channel_data, key_metrics = load_data()

# --- Key Metrics Row ---
st.header("Key Metrics")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Total Inventory Value",
        f"${key_metrics['total_inventory_value']:,.0f}",
        delta=f"{key_metrics['total_skus_in_inventory']} products",
    )

with col2:
    critical_count = key_metrics["critical_stockout_count"]
    high_count = key_metrics["high_stockout_count"]
    st.metric(
        "Stockout Risks",
        f"{key_metrics['products_at_stockout_risk']}",
        delta=f"{critical_count} critical, {high_count} high",
        delta_color="inverse",
    )

with col3:
    st.metric(
        "Dead Stock Value",
        f"${key_metrics['dead_inventory_value']:,.0f}",
        delta=f"{key_metrics['dead_inventory_count']} products",
        delta_color="inverse",
    )

with col4:
    st.metric(
        "Below Reorder Level",
        f"{key_metrics['items_below_reorder_level']}",
        delta="Need attention",
        delta_color="inverse",
    )

st.divider()

# --- Two Column Layout ---
left_col, right_col = st.columns([2, 1])

with left_col:
    # Stockout Risks Table
    st.subheader("🚨 Stockout Risks")

    if len(stockout_risks) > 0:
        # Add filter
        risk_filter = st.multiselect(
            "Filter by risk level:",
            ["critical", "high", "medium"],
            default=["critical", "high"],
        )

        filtered = stockout_risks[stockout_risks["risk_level"].isin(risk_filter)]

        # Display table
        display_cols = [
            "item_code",
            "description",
            "category",
            "qty_adjusted",
            "avg_daily_sales",
            "days_of_stock",
            "risk_level",
        ]
        display_df = filtered[display_cols].copy()
        display_df.columns = [
            "SKU",
            "Product",
            "Category",
            "Stock",
            "Daily Sales",
            "Days Left",
            "Risk",
        ]
        display_df["Daily Sales"] = display_df["Daily Sales"].round(1)
        display_df["Days Left"] = display_df["Days Left"].round(0).astype(int)

        # Add risk emoji for better visibility
        risk_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡"}
        display_df["Risk"] = display_df["Risk"].apply(lambda x: f"{risk_emoji.get(x, '')} {x.upper()}")

        st.dataframe(
            display_df.head(20),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Stock": st.column_config.NumberColumn(format="%d"),
                "Daily Sales": st.column_config.NumberColumn(format="%.1f"),
                "Days Left": st.column_config.NumberColumn(format="%d"),
            }
        )

        st.caption(f"Showing top 20 of {len(filtered)} items at risk")
    else:
        st.info("No stockout risks identified")

with right_col:
    # Channel Comparison
    st.subheader("📊 Channel Performance")

    # Revenue pie chart
    fig_revenue = go.Figure(
        data=[
            go.Pie(
                labels=["In-Store", "Online"],
                values=[
                    channel_data["in_store"]["total_revenue"],
                    channel_data["online"]["total_revenue"],
                ],
                hole=0.4,
                marker_colors=["#2ecc71", "#3498db"],
            )
        ]
    )
    fig_revenue.update_layout(
        title="Revenue Split",
        height=250,
        margin=dict(t=40, b=20, l=20, r=20),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2),
    )
    st.plotly_chart(fig_revenue, use_container_width=True)

    # AOV comparison
    fig_aov = go.Figure(
        data=[
            go.Bar(
                x=["In-Store", "Online"],
                y=[
                    channel_data["in_store"]["avg_order_value"],
                    channel_data["online"]["avg_order_value"],
                ],
                marker_color=["#2ecc71", "#3498db"],
                text=[
                    f"${channel_data['in_store']['avg_order_value']:.2f}",
                    f"${channel_data['online']['avg_order_value']:.2f}",
                ],
                textposition="outside",
            )
        ]
    )
    fig_aov.update_layout(
        title="Avg Order Value",
        height=200,
        margin=dict(t=40, b=20, l=20, r=20),
        yaxis_title="$",
    )
    st.plotly_chart(fig_aov, use_container_width=True)

st.divider()

# --- Dead Inventory Section ---
st.subheader("🏚️ Dead Inventory (No Sales in 60+ Days)")

if len(dead_inventory) > 0:
    col1, col2 = st.columns([2, 1])

    with col1:
        # Top dead inventory by value
        dead_display = dead_inventory[
            ["item_code", "description", "category", "qty_adjusted", "retail_price", "value_at_risk", "days_since_last_sale"]
        ].head(15).copy()
        dead_display.columns = ["SKU", "Product", "Category", "Qty", "Unit Price", "Value at Risk", "Days Since Sale"]
        dead_display["Unit Price"] = dead_display["Unit Price"].apply(lambda x: f"${x:.2f}")
        dead_display["Value at Risk"] = dead_display["Value at Risk"].apply(lambda x: f"${x:,.0f}")

        st.dataframe(dead_display, use_container_width=True, hide_index=True)

    with col2:
        # Dead inventory by category
        dead_by_cat = (
            dead_inventory.groupby("category")["value_at_risk"]
            .sum()
            .sort_values(ascending=True)
            .tail(10)
        )

        fig_dead = go.Figure(
            data=[
                go.Bar(
                    x=dead_by_cat.values,
                    y=dead_by_cat.index,
                    orientation="h",
                    marker_color="#e74c3c",
                )
            ]
        )
        fig_dead.update_layout(
            title="Dead Stock by Category",
            height=300,
            margin=dict(t=40, b=20, l=20, r=20),
            xaxis_title="Value at Risk ($)",
        )
        st.plotly_chart(fig_dead, use_container_width=True)
else:
    st.info("No dead inventory identified")

st.divider()

# --- Data Quality Section ---
st.subheader("🔧 Data Quality: Issues Found & Fixes Applied")

st.markdown("""
Before running the analysis, we identified and corrected several data quality issues.
The numbers above reflect the **cleaned data** — here's what we fixed:
""")

# Issues and Fixes Table
quality_data = [
    {
        "Issue": "51 duplicate product codes",
        "Impact": "Inventory was split across multiple records",
        "Fix Applied": f"Aggregated by product name → {key_metrics['total_skus_raw']} records → {key_metrics['total_skus_in_inventory']} unique products",
        "Status": "✅ Fixed"
    },
    {
        "Issue": f"Placeholder dates (1900-01-01)",
        "Impact": "Would skew velocity calculations",
        "Fix Applied": f"Filtered {key_metrics['placeholder_dates_filtered']:,} test/void transactions",
        "Status": "✅ Fixed"
    },
    {
        "Issue": "No common product ID across systems",
        "Impact": "Couldn't match inventory to sales",
        "Fix Applied": "Matched by normalized product name (lowercase, stripped)",
        "Status": "✅ Fixed"
    },
    {
        "Issue": "Analysis date mismatch",
        "Impact": "Running in 2026 on 2024 data would show everything as 'dead'",
        "Fix Applied": "Used latest date in data (Dec 14, 2024) as reference",
        "Status": "✅ Fixed"
    },
]

import pandas as pd
quality_df = pd.DataFrame(quality_data)
st.dataframe(
    quality_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Issue": st.column_config.TextColumn("Issue Found", width="medium"),
        "Impact": st.column_config.TextColumn("Impact", width="medium"),
        "Fix Applied": st.column_config.TextColumn("Fix Applied", width="large"),
        "Status": st.column_config.TextColumn("Status", width="small"),
    }
)

# Raw issues from quality reports (expandable)
with st.expander("📋 View Raw Data Quality Reports"):
    quality_col1, quality_col2, quality_col3 = st.columns(3)

    with quality_col1:
        st.markdown("**POS System**")
        pos_report = data.quality_reports["pos"]
        for issue in pos_report.issues[:5]:
            icon = "🔴" if issue.severity == "critical" else "🟡" if issue.severity == "warning" else "🔵"
            st.markdown(f"{icon} {issue.column}: {issue.description}")

    with quality_col2:
        st.markdown("**Inventory System**")
        inv_report = data.quality_reports["inventory"]
        for issue in inv_report.issues[:5]:
            icon = "🔴" if issue.severity == "critical" else "🟡" if issue.severity == "warning" else "🔵"
            st.markdown(f"{icon} {issue.column}: {issue.description}")

    with quality_col3:
        st.markdown("**E-commerce**")
        ecom_report = data.quality_reports["ecommerce"]
        if ecom_report.issues:
            for issue in ecom_report.issues[:5]:
                icon = "🔴" if issue.severity == "critical" else "🟡" if issue.severity == "warning" else "🔵"
                st.markdown(f"{icon} {issue.column}: {issue.description}")
        else:
            st.markdown("✅ No issues found")

# --- Methodology Section ---
st.divider()
st.subheader("📐 Methodology")

method_col1, method_col2 = st.columns(2)

with method_col1:
    st.markdown("**Stockout Risk Calculation**")
    st.markdown("""
    1. Look at last 90 days of sales
    2. Calculate: `Daily Sales = Units Sold ÷ 90`
    3. Calculate: `Days of Stock = Current Inventory ÷ Daily Sales`

    **Thresholds (adjusted for high-velocity retail):**
    - 🔴 **Critical (≤3 days):** Reorder TODAY
    - 🟠 **High (≤7 days):** Reorder THIS WEEK
    - 🟡 **Medium (≤14 days):** Monitor closely
    """)

with method_col2:
    st.markdown("**Why These Thresholds?**")
    st.markdown("""
    Standard retail uses 7/14/30 day thresholds, but this is a
    **high-velocity retailer**:

    - Average daily sales: **38 units/product**
    - Median days of stock: **2.9 days**

    Using standard thresholds would flag everything as "critical" —
    not actionable. Our adjusted thresholds separate urgent from important.
    """)

# --- Footer ---
st.divider()
st.caption(
    "Built with Streamlit | Data period: Jan-Dec 2024 | "
    f"POS: {len(data.pos_transactions):,} txns | "
    f"Inventory: {key_metrics['total_skus_in_inventory']} products (de-duplicated from {key_metrics['total_skus_raw']}) | "
    f"E-commerce: {len(data.ecommerce_orders):,} orders"
)
