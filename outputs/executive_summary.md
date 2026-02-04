# Inventory Health Report: Executive Summary

**Prepared for:** CFO
**Date:** December 2024
**Data Period:** January - December 2024

---

## The Bottom Line

**We're losing money every day.** After reconciling three data systems, we found:

- **~$320K/day in revenue at risk** from 97 critical products (≤3 days of stock)
- **$121K tied up in dead inventory** — 15 products that were never activated for sale
- **51 duplicate SKUs** causing inventory miscounts and unreliable reorder triggers

The stockout problem is urgent: our top-selling products are running out. "Set of Rug" is already at zero inventory but sells 34 units/day at $57.82 each — that's **~$2,000/day in lost sales** for just one product. Across all 97 critical items, we estimate **~$320,000/day in revenue at risk** if stockouts continue.

*Note: Revenue at risk = daily sales velocity × retail price. Products already at zero stock are losing this revenue TODAY.*

---

## Key Numbers

| Metric | Value | Business Impact |
|--------|-------|-----------------|
| **Daily Revenue at Risk (Critical)** | **~$320,000** | 97 products ≤3 days stock |
| **Daily Revenue at Risk (All)** | **~$616,000** | All 190 at-risk products |
| **Dead Inventory Value** | **$121,174** | Capital tied up, recoverable |
| Products at Stockout Risk | 190 items (93%) | Widespread issue |
| — Critical (≤3 days stock) | 97 items | Reorder TODAY |
| — High (≤7 days stock) | 93 items | Reorder THIS WEEK |
| Duplicate Product Names | 51 | Miscounted inventory |
| Total Inventory Value | $1,971,540 | — |

---

## How We Calculated These Numbers

### Stockout Risk Methodology

**The Question:** "How many days until we run out of each product?"

**The Calculation:**
1. We looked at the last 90 days of sales (Sep 15 - Dec 14, 2024)
2. For each product, we calculated: `Average Daily Sales = Total Units Sold ÷ 90 days`
3. Then: `Days of Stock = Current Inventory ÷ Average Daily Sales`

**Example — "Set of Rug":**
- Sold 3,091 units in the last 90 days
- Average daily sales: 3,091 ÷ 90 = **34 units/day**
- Current inventory: **0 units**
- Days of stock: 0 ÷ 34 = **0 days** (Critical!)

**Why These Thresholds?**
This is a high-velocity retailer (average 38 units/day per product). We adjusted thresholds to be actionable:
- **Critical (≤3 days):** Will stock out this week — reorder immediately
- **High (≤7 days):** Will stock out in ~1 week — reorder this week

---

## Immediate Actions Required

### 1. Emergency Reorder Required (97 Critical Items) — ~$320K/day at Risk

97 products have less than 3 days of stock at current sales velocity. **Prioritized by daily revenue at risk:**

| Product | Stock | Daily Sales | Unit Price | Days Left | Daily Revenue at Risk |
|---------|-------|-------------|------------|-----------|----------------------|
| Organic Desk Organizer | 4 | 32/day | $147.97 | <1 | **$4,796/day** |
| Set of Cushion | 6 | 31/day | $146.29 | <1 | **$4,496/day** |
| Premium Rug | 3 | 31/day | $121.99 | <1 | **$3,744/day** |
| Large Bird Feeder | 2 | 33/day | $78.26 | <1 | **$2,596/day** |
| Set of Rug | 0 | 34/day | $57.82 | **0** | **$1,986/day** |

*Revenue = daily sales × actual retail price from inventory data*

**What this means:** The 97 critical items represent ~$320K/day in revenue at risk. Products like "Organic Desk Organizer" have higher revenue impact than "Set of Rug" despite similar velocity — because unit price matters. **Prioritize reorders by revenue at risk, not just days of stock.**

### 2. Activate or Clear Dead Inventory ($121K)

15 "New Product" items have never been sold. These appear to be products added to inventory but never activated for sale:
- Either launch these products with marketing support
- Or return to vendor / write off if no longer viable

**Opportunity:** Free up ~$121K in working capital.

### 3. Fix the Data Quality Issues

**Duplicate Products:** 51 product names exist with multiple item codes (e.g., "Handmade Notebook" has 3 different codes: 21534, 10206, 58925). This:
- Splits inventory counts across multiple records
- Makes reorder analysis unreliable
- **Fix:** Consolidate to unique product identifiers

**POS Data Issues:**
- 4+ different date formats across transactions
- 20% of transactions missing store_id
- Placeholder dates (1900-01-01) in test transactions

---

## Data Quality Issues We Corrected

Before we could trust the numbers, we had to fix several issues:

| Issue Found | How We Fixed It | Impact |
|-------------|-----------------|--------|
| 51 products had duplicate names with different item codes | Aggregated by name: summed quantities, used max reorder level | Without this, inventory was under-counted |
| Placeholder dates (1900-01-01) | Filtered out dates before 2020 | These were test/void transactions that would have skewed velocity |
| No common product ID across systems | Matched by normalized product name (lowercase, stripped) | Enabled cross-system analysis |
| Running analysis in 2026 on 2024 data | Used max date in data (Dec 14, 2024) as reference, not today's date | Prevented "time machine" bug showing 2+ years of dead inventory |

---

## Channel Performance

| Channel | Revenue | Avg Transaction | Return Rate |
|---------|---------|-----------------|-------------|
| In-Store | $642.9M (96.5%) | $1,391 | 3.2% |
| Online | $23.2M (3.5%) | $232 | 6.3% |

**Insight:** In-store drives 97% of revenue with 6x higher transaction values. Online has nearly double the return rate, suggesting potential issues with product expectations.

---

## What We'd Recommend Next

1. **This week:** Emergency reorder for 97 critical stockout items — **prioritize by revenue at risk, not just days of stock**
2. **This month:** Decide fate of 15 inactive "New Product" items ($121K recoverable)
3. **This quarter:** Consolidate duplicate product codes into master catalog
4. **Ongoing:** Set up automated stockout alerts that flag items by **revenue at risk**, not just inventory level

### Future Enhancement: Revenue-Based Reorder Prioritization

Currently, most systems flag items when `quantity < reorder_level`. This treats all products equally.

**Better approach:** Prioritize by `daily_revenue_at_risk = daily_sales × unit_price`

This means:
- A $500 item selling 2/day (=$1,000/day at risk) gets priority over
- A $10 item selling 5/day (=$50/day at risk)

**Implementation:** Add `revenue_at_risk` column to stockout reports. Sort by this instead of days-of-stock. Focus reorder efforts where the money is.

---

## Technical Note

This analysis corrected for several data quality issues that would have skewed results:
- **De-duplicated** 265 inventory records → 205 unique products
- **Filtered** placeholder dates (1900-01-01) from velocity calculations
- **Used relative dating** (latest sale as reference) instead of current date
- **Adjusted thresholds** for high-velocity retail (critical ≤3 days vs. standard ≤7 days)

We've built a reusable analysis framework that can run this health check weekly.

---

*Full technical analysis available in the accompanying Jupyter notebook.*
