# Inventory Health Report: Executive Summary

**Prepared for:** CFO
**Date:** December 2024
**Data Period:** January - December 2024

---

## The Bottom Line

After reconciling three separate data systems and correcting for data quality issues, we found **190 of 205 products are at stockout risk**, with **97 products critically low (less than 3 days of stock)**. We also identified **$121K tied up in dead stock** (15 new products never activated for sale), and **51 duplicate product entries** that were splitting inventory counts incorrectly.

---

## Key Numbers

| Metric | Value |
|--------|-------|
| Total Inventory Value | $1,971,540 |
| Unique Products (after de-duplication) | 205 |
| **Products at Stockout Risk** | **190 items (93% of catalog)** |
| — Critical (≤3 days stock) | 97 items |
| — High (≤7 days stock) | 93 items |
| Dead Inventory Value | $121,174 |
| Dead Inventory Items | 15 (new products not yet active) |
| Items Below Reorder Level | 31 items |
| Duplicate Product Names Found | 51 (affects 111 records) |

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

### 1. Emergency Reorder Required (97 Critical Items)

97 products have less than 3 days of stock at current sales velocity. Top priorities:

| Product | Current Stock | Daily Sales | Days Left |
|---------|---------------|-------------|-----------|
| Set of Rug | 0 | 34/day | 0 |
| Large Bird Feeder | 2 | 33/day | <1 |
| Premium Rug | 3 | 31/day | <1 |
| Budget Rug | 3 | 28/day | <1 |
| Organic Desk Organizer | 4 | 32/day | <1 |

**Risk if not addressed:** Lost sales, customer attrition. At 34 units/day, one week of stockout on "Set of Rug" = 238 missed sales.

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

1. **This week:** Emergency reorder for 97 critical stockout items
2. **This month:** Decide fate of 15 inactive "New Product" items
3. **This quarter:** Consolidate duplicate product codes into master catalog
4. **Ongoing:** Set up automated stockout alerts based on the velocity analysis

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
