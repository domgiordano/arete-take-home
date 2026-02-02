"""
AI-assisted insight generation using structured outputs.

Uses Pydantic models to ensure LLM outputs are well-structured
and can be programmatically processed.
"""

from typing import Literal
from pydantic import BaseModel, Field
from openai import OpenAI
import json
import os


class StockoutRisk(BaseModel):
    """A product at risk of stockout."""

    sku: str = Field(description="The product SKU/code")
    product_name: str = Field(description="The product name")
    current_stock: int = Field(description="Current quantity on hand")
    days_of_stock: float = Field(description="Estimated days until stockout based on velocity")
    risk_level: Literal["critical", "high", "medium"] = Field(
        description="Risk level based on days remaining"
    )
    recommendation: str = Field(description="Specific action to take")


class DeadInventory(BaseModel):
    """A product that's not moving and tying up capital."""

    sku: str
    product_name: str
    quantity_on_hand: int
    days_since_last_sale: int
    estimated_value: float = Field(description="Retail value of dead stock")
    recommendation: str


class ReconciliationGap(BaseModel):
    """A discrepancy between systems that needs investigation."""

    sku: str
    product_name: str
    pos_quantity: int = Field(description="Quantity implied by POS (sales - returns)")
    inventory_quantity: int = Field(description="Quantity per inventory system")
    ecommerce_quantity: int | None = Field(description="E-commerce sales if applicable")
    discrepancy: int = Field(description="Size of the gap")
    likely_cause: str = Field(description="Most probable reason for the discrepancy")
    priority: Literal["high", "medium", "low"]


class ChannelInsight(BaseModel):
    """Insight comparing in-store vs online performance."""

    metric: str = Field(description="What's being compared")
    in_store_value: float
    online_value: float
    insight: str = Field(description="What this comparison means")
    recommendation: str | None = None


class DataQualityRecommendation(BaseModel):
    """A recommendation for fixing data quality issues."""

    system: Literal["POS", "Inventory", "E-commerce"]
    issue: str = Field(description="The data quality problem")
    business_impact: str = Field(description="Why this matters to the business")
    fix_recommendation: str = Field(description="What the client should do")
    priority: Literal["critical", "high", "medium", "low"]


class InventoryHealthReport(BaseModel):
    """Complete AI-generated inventory health analysis."""

    executive_summary: str = Field(
        description="2-3 sentence summary for a CFO who won't read details"
    )
    stockout_risks: list[StockoutRisk] = Field(
        description="Products at risk of running out"
    )
    dead_inventory: list[DeadInventory] = Field(
        description="Products not selling that tie up capital"
    )
    reconciliation_gaps: list[ReconciliationGap] = Field(
        description="Major discrepancies between systems"
    )
    channel_insights: list[ChannelInsight] = Field(
        description="Comparisons between in-store and online"
    )
    data_quality_recommendations: list[DataQualityRecommendation] = Field(
        description="What to fix in the source systems"
    )
    key_metrics: dict[str, float | int | str] = Field(
        description="Key numbers the CFO should know"
    )


class InsightGenerator:
    """
    Generates insights using an LLM with structured output.

    The LLM is used to:
    1. Synthesize patterns across the data analysis
    2. Generate natural language explanations
    3. Prioritize recommendations

    What to trust vs verify:
    - TRUST: Pattern synthesis, natural language generation
    - VERIFY: Specific numbers (always compute these programmatically)
    - VERIFY: Ranking/prioritization (cross-check with data)
    """

    def __init__(self, model: str = "gpt-4o-mini"):
        self.client = OpenAI()
        self.model = model

    def generate_insights(
        self,
        stockout_data: list[dict],
        dead_inventory_data: list[dict],
        reconciliation_data: list[dict],
        channel_data: dict,
        quality_issues: list[dict],
        key_metrics: dict,
    ) -> InventoryHealthReport:
        """
        Generate a structured inventory health report.

        All numeric data should be pre-computed and passed in.
        The LLM adds interpretation and recommendations.
        """
        prompt = self._build_prompt(
            stockout_data,
            dead_inventory_data,
            reconciliation_data,
            channel_data,
            quality_issues,
            key_metrics,
        )

        response = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": """You are a retail analytics expert helping a CFO understand their inventory health.

Your job is to:
1. Interpret the data provided and generate actionable insights
2. Write clearly for a non-technical audience
3. Prioritize the most important issues
4. Provide specific, actionable recommendations

Be direct and specific. Avoid jargon. Focus on what matters to the business.""",
                },
                {"role": "user", "content": prompt},
            ],
            response_format=InventoryHealthReport,
        )

        return response.choices[0].message.parsed

    def _build_prompt(
        self,
        stockout_data: list[dict],
        dead_inventory_data: list[dict],
        reconciliation_data: list[dict],
        channel_data: dict,
        quality_issues: list[dict],
        key_metrics: dict,
    ) -> str:
        """Build the prompt with all the pre-computed data."""
        return f"""Analyze this retail inventory data and generate a comprehensive health report.

## Key Metrics (pre-computed, use these exact numbers)
{json.dumps(key_metrics, indent=2)}

## Products at Stockout Risk
{json.dumps(stockout_data[:20], indent=2)}

## Slow-Moving/Dead Inventory
{json.dumps(dead_inventory_data[:20], indent=2)}

## System Reconciliation Gaps
{json.dumps(reconciliation_data[:15], indent=2)}

## Channel Performance (In-Store vs Online)
{json.dumps(channel_data, indent=2)}

## Data Quality Issues Found
{json.dumps(quality_issues, indent=2)}

Generate a complete InventoryHealthReport with:
1. A 2-3 sentence executive summary a CFO can read in 10 seconds
2. The top stockout risks with specific actions
3. Dead inventory recommendations
4. Key reconciliation gaps to investigate
5. Channel performance insights
6. Data quality fixes prioritized by business impact

Be specific and actionable. Use the exact numbers provided."""

    def generate_executive_summary(
        self,
        key_findings: list[str],
        key_metrics: dict,
        top_recommendations: list[str],
    ) -> str:
        """
        Generate a natural language executive summary.

        Separate method for when you just need the summary,
        not the full structured report.
        """
        prompt = f"""Write a 1-page executive summary for a CFO about their inventory health.

Key Findings:
{chr(10).join(f'- {f}' for f in key_findings)}

Key Metrics:
{json.dumps(key_metrics, indent=2)}

Top Recommendations:
{chr(10).join(f'{i+1}. {r}' for i, r in enumerate(top_recommendations))}

Write in clear, non-technical language. Be direct about problems.
Structure: Summary paragraph, Key Numbers section, Immediate Actions section.
Keep it under 400 words."""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You write clear, direct executive summaries for retail CFOs.",
                },
                {"role": "user", "content": prompt},
            ],
        )

        return response.choices[0].message.content
