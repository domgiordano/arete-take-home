"""
Inventory Health Dashboard

A Streamlit dashboard for exploring inventory health insights.
Run with: streamlit run app.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import streamlit as st
import plotly.graph_objects as go

from clients.retail_client import RetailClientLoader
from core.analysis import (
    compute_sales_velocity,
    identify_stockout_risks,
    identify_dead_inventory,
    compute_channel_comparison,
    compute_key_metrics,
)

# Page config
st.set_page_config(
    page_title="Inventory Health Dashboard",
    page_icon="📦",
    layout="wide",
)

st.title("📦 Inventory Health Dashboard")
st.caption("Retail Client - December 2024 Analysis")


@st.cache_data
def load_data():
    """Load and process all data (cached for performance)."""
    loader = RetailClientLoader(Path("data/raw"))
    data = loader.load_all()

    # Compute velocity
    velocity = compute_sales_velocity(
        data.pos_transactions,
        sku_col="sku_normalized",
        qty_col="quantity",
        date_col="date_parsed",
    )

    # Compute stockout risks
    stockout = identify_stockout_risks(
        data.inventory,
        velocity,
        inv_sku_col="item_code_normalized",
        inv_qty_col="qty_adjusted",
    )

    # Compute dead inventory
    dead = identify_dead_inventory(
        data.inventory,
        data.pos_transactions,
        inv_sku_col="item_code_normalized",
        inv_qty_col="qty_adjusted",
        inv_price_col="retail_price",
        txn_sku_col="sku_normalized",
        txn_date_col="date_parsed",
    )

    # Channel comparison
    channel = compute_channel_comparison(data.pos_transactions, data.ecommerce_orders)

    # Key metrics
    metrics = compute_key_metrics(
        data.inventory, data.pos_transactions, data.ecommerce_orders, stockout, dead
    )

    return data, velocity, stockout, dead, channel, metrics


# Load data
with st.spinner("Loading data..."):
    data, velocity, stockout_risks, dead_inventory, channel_data, key_metrics = load_data()

# --- Key Metrics Row ---
st.header("Key Metrics")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Total Inventory Value",
        f"${key_metrics['total_inventory_value']:,.0f}",
    )

with col2:
    critical_count = key_metrics["critical_stockout_count"]
    st.metric(
        "Stockout Risks",
        f"{key_metrics['products_at_stockout_risk']}",
        delta=f"{critical_count} critical",
        delta_color="inverse",
    )

with col3:
    st.metric(
        "Dead Stock Value",
        f"${key_metrics['dead_inventory_value']:,.0f}",
        delta="60+ days no sales",
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
st.subheader("🔧 Data Quality Issues")

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

# --- Footer ---
st.divider()
st.caption(
    "Built with Streamlit | Data period: Jan-Dec 2024 | "
    f"POS: {len(data.pos_transactions):,} txns | "
    f"Inventory: {len(data.inventory):,} SKUs | "
    f"E-commerce: {len(data.ecommerce_orders):,} orders"
)
