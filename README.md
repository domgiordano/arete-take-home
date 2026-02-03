# Retail Inventory Reconciliation & Analysis

A data integration and analysis project for reconciling inventory across POS, inventory management, and e-commerce systems.

## Quick Start

```bash
# Install dependencies
pip install -e .

# Copy environment file
cp .env.example .env
# Add your OpenAI API key to .env (optional, for AI insights)

# Option 1: Run the analysis notebook
jupyter notebook notebooks/inventory_analysis.ipynb

# Option 2: Launch the interactive dashboard
streamlit run app.py
```

## Project Structure

```
├── app.py                    # Streamlit dashboard
├── data/
│   ├── raw/                  # Source data files
│   │   ├── pos_transactions.csv
│   │   ├── inventory_management.xlsx
│   │   └── ecommerce_export.json
│   └── processed/            # Cleaned/merged data (generated)
├── notebooks/
│   └── inventory_analysis.ipynb  # Main analysis walkthrough
├── outputs/
│   ├── executive_summary.md      # CFO-ready summary
│   ├── stockout_risks.csv        # Products at risk
│   ├── dead_inventory.csv        # Non-moving stock
│   └── key_metrics.json          # Summary metrics
├── src/
│   ├── core/                 # Reusable components
│   │   ├── parsers.py        # Date/SKU normalization
│   │   ├── quality.py        # Data quality framework
│   │   ├── reconciliation.py # Cross-system matching
│   │   ├── analysis.py       # Inventory health metrics
│   │   └── insights.py       # AI-powered insights
│   └── clients/              # Client-specific adapters
│       └── retail_client.py  # This client's data loader
├── FUTURE_WORK.md            # Production architecture plans
└── pyproject.toml
```

## What's Reusable vs. Client-Specific

### Reusable (src/core/)

These components can be used for any retail client with minimal changes:

| Module              | Purpose                                                |
| ------------------- | ------------------------------------------------------ |
| `parsers.py`        | Handles common date formats, SKU variations            |
| `quality.py`        | Configurable data quality checking framework           |
| `reconciliation.py` | Cross-system matching by ID or name                    |
| `analysis.py`       | Stockout risk, dead inventory, velocity calculations   |
| `insights.py`       | AI insight generation with Pydantic structured outputs |

### Client-Specific (src/clients/)

This contains hardcoded logic for this client:

- Column name mappings for their exports
- Notes column parsing patterns (e.g., "Adj: +15 per Sarah 5/4")
- SKU prefix patterns specific to their POS
- Payment method normalization rules

**To adapt for a new client:** Copy `retail_client.py`, update the column mappings and parsing rules.

## AI-Assisted Insights

The project uses OpenAI's GPT-4 with structured outputs (Pydantic models) to:

- Generate natural language summaries
- Synthesize patterns across data points
- Prioritize recommendations

**What the AI does well:** Pattern synthesis, natural language generation, prioritization.

**What's verified programmatically:** All numeric values, specific product identifiers, rankings.

Set `OPENAI_API_KEY` in your `.env` to enable AI features.

## Key Findings

See `outputs/executive_summary.md` for the CFO-ready summary.

### Data Quality Issues Found

1. **POS System**
   - 4+ date formats across transactions
   - 20% of transactions missing store_id
   - Inconsistent payment method casing
   - TEST/VOID transactions in production data

2. **Inventory System**
   - Manual overrides in Notes column indicate system distrust
   - Physical count corrections suggest inventory discrepancies

3. **Cross-System**
   - No common product identifier
   - Must match by normalized product name

### Recommendations

1. **Immediate:** Reorder critical stockout items
2. **This quarter:** Clearance program for dead inventory ($121K value)
3. **System fix:** Implement unified product ID across systems
4. **Process fix:** Move inventory adjustments from Notes to proper fields

## Running Tests

```bash
pytest tests/
```

## What I Would Do With More Time

See [FUTURE_WORK.md](FUTURE_WORK.md) for detailed production architecture plans, including:

- **Automated Pipeline:** S3 triggers → Lambda ingestion → processed data lake
- **Scheduled Reports:** Weekly PDF reports emailed to CFO
- **Real-time Alerts:** Slack notifications for critical stockouts
- **Self-Service Dashboard:** ECS-hosted Streamlit with Cognito auth

### Additional Enhancements

- Fuzzy name matching for product reconciliation (embeddings-based)
- Demand forecasting with Prophet for better stockout prediction
- Historical trend analysis for velocity calculations
- Anomaly detection for data quality issues

![Retail Analystics Architecture Diagram](retail-analytics-architecture.png)
