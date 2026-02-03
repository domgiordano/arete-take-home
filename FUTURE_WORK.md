# Future Work: Production Architecture

This document outlines what I would build with more time to move this from a one-time analysis to an ongoing operational system.

---

## Phase 1: Automated Data Pipeline (Week 1-2)

### Current State
- Manual data exports from 3 systems
- One-time analysis run locally

### Target State
```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  POS System │     │  Inventory  │     │  E-commerce │
│   (SFTP)    │     │   (API)     │     │   (API)     │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       ▼                   ▼                   ▼
┌──────────────────────────────────────────────────────┐
│                    S3 Raw Bucket                      │
│  s3://client-data/raw/{source}/{date}/               │
└──────────────────────────────────────────────────────┘
       │
       │ S3 Event Trigger
       ▼
┌──────────────────────────────────────────────────────┐
│              AWS Lambda: Ingestion                    │
│  - Validate file format                              │
│  - Run data quality checks                           │
│  - Write to processed bucket                         │
└──────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────┐
│                 S3 Processed Bucket                   │
│  s3://client-data/processed/{source}/{date}/         │
│  (Parquet format, partitioned by date)               │
└──────────────────────────────────────────────────────┘
```

### Implementation Details

**S3 Bucket Structure:**
```
s3://retail-client-data/
├── raw/
│   ├── pos/
│   │   └── 2024-12-15/pos_transactions.csv
│   ├── inventory/
│   │   └── 2024-12-15/inventory.xlsx
│   └── ecommerce/
│       └── 2024-12-15/orders.json
├── processed/
│   ├── pos/
│   │   └── date=2024-12-15/data.parquet
│   ├── inventory/
│   │   └── date=2024-12-15/data.parquet
│   └── unified/
│       └── date=2024-12-15/inventory_health.parquet
└── reports/
    └── 2024-12-15/
        ├── stockout_risks.csv
        ├── dead_inventory.csv
        └── executive_summary.pdf
```

**Lambda Trigger Configuration:**
```python
# terraform/s3.tf (pseudo-code)
resource "aws_s3_bucket_notification" "raw_data" {
  bucket = aws_s3_bucket.raw.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.ingestion.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "raw/"
  }
}
```

---

## Phase 2: Scheduled Analysis & Alerts (Week 2-3)

### Weekly Health Report Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                  EventBridge (Cron: Weekly)                  │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Step Functions Workflow                    │
│                                                              │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐    │
│  │ Load Latest  │──▶│ Run Analysis │──▶│ Generate     │    │
│  │ Data         │   │ (Lambda/ECS) │   │ Report (PDF) │    │
│  └──────────────┘   └──────────────┘   └──────────────┘    │
│                              │                              │
│                              ▼                              │
│                     ┌──────────────┐                        │
│                     │ Check Alerts │                        │
│                     └──────────────┘                        │
│                              │                              │
│              ┌───────────────┼───────────────┐              │
│              ▼               ▼               ▼              │
│       ┌──────────┐    ┌──────────┐    ┌──────────┐         │
│       │ Email    │    │ Slack    │    │ Save to  │         │
│       │ CFO      │    │ Ops Team │    │ S3       │         │
│       └──────────┘    └──────────┘    └──────────┘         │
└─────────────────────────────────────────────────────────────┘
```

### Alert Rules

| Alert | Trigger | Channel | Priority |
|-------|---------|---------|----------|
| Critical Stockout | Item < 3 days stock | Slack + Email | P1 |
| High Stockout | Item < 7 days stock | Slack | P2 |
| Data Quality Failure | >5% missing values | Email (Data Team) | P2 |
| Reconciliation Gap | >$10K discrepancy | Email (Finance) | P2 |

---

## Phase 3: Self-Service Dashboard (Week 3-4)

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         CloudFront                           │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    ECS Fargate Service                       │
│                    (Streamlit Dashboard)                     │
│                                                              │
│  - Auto-scaling based on CPU                                │
│  - ALB health checks                                        │
│  - Cognito authentication                                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      S3 (Data Layer)                         │
│                                                              │
│  - Pre-computed aggregates (updated nightly)                │
│  - Historical snapshots for trend analysis                  │
└─────────────────────────────────────────────────────────────┘
```

### Features to Add

1. **File Upload UI** - Drag-and-drop data files directly to S3
2. **Historical Trends** - Track stockout risk over time
3. **What-If Scenarios** - "What if we order 100 units of X?"
4. **Export to Excel** - CFO-friendly download option

---

## Phase 4: ML Enhancements (Future)

### Demand Forecasting
- Use historical POS data to predict future demand
- Improve stockout risk accuracy from "days of stock" to "probability of stockout"
- Prophet or similar for seasonality handling

### Anomaly Detection
- Flag unusual sales patterns automatically
- Detect potential data entry errors in real-time
- Alert on reconciliation gaps before they become big problems

### Product Matching
- Use embeddings (e.g., OpenAI) to fuzzy-match products across systems
- Reduce manual mapping effort for new products
- Handle SKU typos and variations automatically

---

## Cost Estimate (AWS)

| Service | Monthly Cost | Notes |
|---------|-------------|-------|
| S3 | ~$5 | <100GB data |
| Lambda | ~$10 | Low volume triggers |
| ECS Fargate | ~$50 | 1 small task, on-demand |
| Step Functions | ~$5 | Weekly executions |
| CloudWatch | ~$10 | Logs + metrics |
| **Total** | **~$80/mo** | Production-ready |

---

## What I'd Prioritize First

1. **S3 + Lambda ingestion** - Biggest ROI, removes manual export step
2. **Slack alerts for critical stockouts** - Immediate operational value
3. **Weekly PDF report via email** - CFO asked for this

The dashboard (Phase 3) is nice-to-have but the automated pipeline and alerts provide more value faster.

---

## Security Considerations

- IAM roles with least-privilege access
- S3 bucket policies restricting to VPC endpoints
- Cognito for dashboard authentication
- Secrets Manager for API keys
- VPC with private subnets for ECS tasks
- CloudTrail for audit logging

---

## Lessons Learned: Data Quality Patterns

Issues discovered during this analysis that should inform future data pipelines:

### 1. Temporal Reference Issues ("Time Machine Problem")
**Problem:** Using `datetime.now()` to calculate "days since last sale" when analyzing historical data produces wrong results (e.g., showing 2+ years of dead inventory when data is from 2024 but code runs in 2026).

**Solution:** Always use `reference_date = max(transactions[date_col])` as "today" for historical analysis.

**Future Implementation:** Add validation that warns if reference_date differs from system date by >30 days.

### 2. Placeholder Dates
**Problem:** System defaults like `1900-01-01` poison velocity calculations (appear as "never sold").

**Solution:** Filter `dates < 2020` before analysis. These were test/void transactions.

**Future Implementation:**
- Add configurable `min_valid_date` parameter
- Quarantine invalid dates rather than silently dropping
- Alert if >1% of transactions have invalid dates

### 3. Duplicate Product Identifiers
**Problem:** 51 products had same name but different item codes (e.g., "Large Lamp" with codes 97054 and 75733). This:
- Split inventory counts incorrectly
- Made reorder thresholds unreliable (sum vs max)

**Solution:** Aggregate by normalized product name:
- `qty_adjusted`: sum (total stock)
- `reorder_level`: max (conservative threshold)
- `retail_price`: mean (for valuation)

**Future Implementation:**
- Add deduplication as a pipeline step before analysis
- Generate "duplicate SKU" report for ops team to consolidate
- Consider fuzzy matching for near-duplicates ("Large Lamp" vs "Lamp, Large")

### 4. Cross-System Product Matching
**Problem:** No common identifier across POS, Inventory, and E-commerce systems.

**Solution:** Match by normalized product name (lowercase, stripped, standardized).

**Future Implementation:**
- Build a product master table with canonical IDs
- Use embedding-based fuzzy matching for unmatched products
- Generate "unmatched products" report for manual review

---

## Known Edge Cases (Not Yet Handled)

These edge cases are documented but not critical for the current dataset:

| Edge Case | Impact | Mitigation |
|-----------|--------|------------|
| NaN prices in inventory | `value_at_risk` becomes NaN | Add `fillna(0)` or exclude from dead inventory report |
| Future dates in transactions | Incorrect velocity if dates > reference_date | Add `date <= reference_date` filter |
| Empty input dataframes | Various function failures | Add empty check at start of pipeline |
| Negative physical_count_override | Negative adjusted quantity | Add validation in loader |
| Products in POS but not inventory | Missing from stockout analysis | Log as reconciliation gap |

For a production system, each of these should have explicit handling and alerting.
