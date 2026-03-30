# Chart Generation Feature

## Overview

The analytics system now automatically evaluates whether a chart/graph would enhance the answer and generates Highcharts configuration objects that the frontend can use to render visualizations.

## Architecture

### Flow

```
User Question → Planner → Executor/Critic → Final Answer → Chart Generator → Response with Chart
```

1. **Question Analysis**: The planner determines intent and creates an analysis plan
2. **Data Execution**: The executor runs queries and generates a draft answer
3. **Validation**: The critic validates the answer
4. **Chart Generation**: The chart generator evaluates if a chart is needed and generates Highcharts config
5. **Response**: The final answer includes an optional `chart` field with the Highcharts configuration

### Components

#### 1. `models/answer.py`
- **FinalAnswer** model now includes an optional `chart` field
- The chart field contains a complete Highcharts configuration object

#### 2. `agents/chart_generator.py`
- LLM-based agent that decides if a chart is beneficial
- Generates appropriate chart type (line, column, bar, pie, area)
- Uses simplified `ChartConfig` schema (compatible with Google GenAI structured output)
- Simplified schema avoids `Dict[str, Any]` which causes API errors

#### 3. `orchestrator/chart_runner.py`
- Runner function that coordinates chart generation
- Passes context (question, answer, plan, query results) to the agent
- Converts simplified `ChartConfig` to full Highcharts configuration
- Returns Highcharts config dict or None

#### 4. `orchestrator/session_utils.py`
- Utilities for extracting tool results from ADK events
- Helper functions for accessing session state

#### 5. `api/routes.py`
- Integrated chart generation into both fast path and full loop
- Chart generation happens after answer validation but before response
- Failures in chart generation don't break the response (graceful degradation)

## Chart Decision Logic

The chart generator evaluates:

### When to Create Charts
- ✅ Comparisons over time (trends, growth, drops)
- ✅ Comparisons across categories (by channel, product, region)
- ✅ Part-to-whole relationships (distribution, breakdown)
- ✅ Correlation between metrics

### When NOT to Create Charts
- ❌ Single value queries without comparison
- ❌ "Why" questions without dimensional data
- ❌ Clarification questions
- ❌ Error or no-data responses

## Chart Types

| Type | Use Case | Example |
|------|----------|---------|
| **line** | Time series, trends over time | Revenue over the last 30 days |
| **column** | Comparing values across categories | Revenue by channel |
| **bar** | Horizontal comparison (long labels) | Revenue by product name |
| **pie** | Part-to-whole, percentage breakdown | Traffic source distribution |
| **area** | Cumulative trends, stacked metrics | Sessions trend over time |

## Response Format

### Without Chart
```json
{
  "answer": {
    "summary": "Total revenue for last 7 days: $125,430.00.",
    "findings": ["Total revenue: $125,430.00"],
    "evidence": ["Source: revenue / last_7_days"],
    "confidence": 0.95,
    "validated": true,
    "chart": null
  }
}
```

### With Chart
```json
{
  "answer": {
    "summary": "Revenue by channel for last 7 days (4 segments).",
    "findings": [
      "Organic: 45000.0",
      "Paid: 32000.0",
      "Social: 28000.0",
      "Direct: 20430.0"
    ],
    "evidence": ["Source: revenue / last_7_days"],
    "confidence": 0.95,
    "validated": true,
    "chart": {
      "chart": {"type": "column"},
      "title": {"text": "Revenue by Channel"},
      "xAxis": {
        "categories": ["Organic", "Paid", "Social", "Direct"],
        "title": {"text": "Channel"}
      },
      "yAxis": {"title": {"text": "Revenue ($)"}},
      "series": [{
        "name": "Revenue",
        "data": [45000, 32000, 28000, 20430]
      }],
      "tooltip": {
        "valuePrefix": "$",
        "valueDecimals": 0
      }
    }
  }
}
```

## Frontend Integration

The frontend can check for the `chart` field in the response:

```typescript
if (response.answer.chart) {
  // Render chart using Highcharts
  Highcharts.chart('container', response.answer.chart);
} else {
  // Display text-only answer
}
```

## Configuration

The chart generator uses the planner model (default: `gemini-2.5-pro`) for high-quality visualization decisions.

You can configure this in `config/settings.py`:
```python
MODEL_PLANNER=gemini-2.5-pro  # Used for both planning and chart generation
```

## Technical Details

### Schema Compatibility

The chart generator uses a simplified `ChartConfig` Pydantic model instead of `Dict[str, Any]` to avoid Google GenAI API errors. The API doesn't support `additionalProperties` in structured output schemas.

The simplified config includes:
- `type`: Chart type (line, column, bar, pie, area)
- `title`, `xAxisTitle`, `yAxisTitle`: Text labels
- `categories`: List of X-axis labels
- `seriesName`, `seriesData`: Data series
- `valuePrefix`, `valueSuffix`, `valueDecimals`: Formatting options

The `chart_runner.py` converts this simplified config to a full Highcharts configuration before returning to the API.

## Error Handling

- Chart generation failures are logged but don't break the response
- If chart generation fails, the answer is returned without a chart
- The system gracefully degrades to text-only responses
- All chart generation errors are logged with context for debugging

## Examples

### Example 1: Time Series
**Question**: "Show me revenue over the last 30 days"

**Chart Type**: Line chart with date categories on X-axis

### Example 2: Category Comparison
**Question**: "What is revenue by channel?"

**Chart Type**: Column chart with channels on X-axis

### Example 3: Distribution
**Question**: "Show traffic source breakdown"

**Chart Type**: Pie chart showing percentage distribution

### Example 4: No Chart Needed
**Question**: "What was total revenue last week?"

**Chart**: None (single aggregate value doesn't benefit from visualization)

## Future Enhancements

Potential improvements:
- [ ] Multi-series charts for comparing multiple metrics
- [ ] Stacked bar/column charts for cumulative breakdowns
- [ ] Heatmaps for correlation matrices
- [ ] Time-based aggregation intelligence (daily vs weekly vs monthly)
- [ ] Custom color schemes based on metric types
- [ ] Interactive drilldown configurations
- [ ] Chart caching to avoid regeneration for similar queries
