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
