import json
import logging
from typing import Optional, Dict, Any
from google.adk.runners import Runner
from google.genai.types import Content, Part
from agents.chart_generator import chart_generator, ChartDecision, ChartConfig
from config.session import session_service

logger = logging.getLogger(__name__)


def convert_to_highcharts(config: ChartConfig) -> Dict[str, Any]:
    """Convert simplified ChartConfig to full Highcharts configuration."""

    # Frontend color scheme
    COLORS = {
        "primary": "#1A56DB",      # Primary blue
        "secondary": "#1d4ed8",    # Darker blue
        "text": "#E5E7EB",         # Light text
        "text_muted": "#9CA3AF",   # Muted text
        "text_dim": "#6B7280",     # Dim text
        "bg_dark": "#0D0D0D",      # Dark background
        "bg_card": "#161616",      # Card background
        "border": "#1E1E1E",       # Border color
        "grid": "#1E1E1E",         # Grid lines
    }

    # Color palette for multi-series charts
    COLOR_PALETTE = [
        "#1A56DB",  # Primary blue
        "#10B981",  # Green
        "#F59E0B",  # Amber
        "#EF4444",  # Red
        "#8B5CF6",  # Purple
        "#EC4899",  # Pink
        "#06B6D4",  # Cyan
        "#F97316",  # Orange
    ]

    highcharts_config = {
        "chart": {
            "type": config.type,
            "backgroundColor": "transparent",
            "style": {
                "fontFamily": "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
            }
        },
        "title": {
            "text": config.title,
            "style": {
                "color": COLORS["text"],
                "fontSize": "14px",
                "fontWeight": "600"
            }
        },
        "colors": COLOR_PALETTE,
    }

    # Configure axes
    if config.type != "pie":
        if config.categories:
            highcharts_config["xAxis"] = {
                "categories": config.categories,
                "labels": {
                    "style": {
                        "color": COLORS["text_muted"],
                        "fontSize": "11px"
                    }
                },
                "lineColor": COLORS["border"],
                "tickColor": COLORS["border"],
                "gridLineColor": COLORS["grid"],
            }
            if config.xAxisTitle:
                highcharts_config["xAxis"]["title"] = {
                    "text": config.xAxisTitle,
                    "style": {
                        "color": COLORS["text_dim"],
                        "fontSize": "11px",
                        "textTransform": "uppercase",
                        "letterSpacing": "0.05em"
                    }
                }

        if config.yAxisTitle:
            highcharts_config["yAxis"] = {
                "title": {
                    "text": config.yAxisTitle,
                    "style": {
                        "color": COLORS["text_dim"],
                        "fontSize": "11px",
                        "textTransform": "uppercase",
                        "letterSpacing": "0.05em"
                    }
                },
                "labels": {
                    "style": {
                        "color": COLORS["text_muted"],
                        "fontSize": "11px"
                    }
                },
                "gridLineColor": COLORS["grid"],
            }
        else:
            # Default yAxis styling even without title
            highcharts_config["yAxis"] = {
                "labels": {
                    "style": {
                        "color": COLORS["text_muted"],
                        "fontSize": "11px"
                    }
                },
                "gridLineColor": COLORS["grid"],
            }

    # Configure series
    if config.type == "pie":
        # Pie chart uses special data format
        pie_data = []
        labels = config.pieLabels or config.categories or []

        # Warn if labels are missing - helps debug chart generator issues
        if len(labels) < len(config.seriesData):
            logger.warning(
                f"Pie chart has {len(config.seriesData)} data points but only {len(labels)} labels. "
                f"Missing labels will show as 'Item X'. Check chart generator data extraction."
            )

        for i, value in enumerate(config.seriesData):
            label = labels[i] if i < len(labels) else f"Item {i+1}"
            pie_data.append({
                "name": label,
                "y": value
            })

        highcharts_config["series"] = [{
            "name": config.seriesName,
            "data": pie_data,
            "dataLabels": {
                "style": {
                    "color": COLORS["text"],
                    "fontSize": "11px",
                    "textOutline": "none"
                }
            }
        }]
        # Pie chart specific styling
        highcharts_config["plotOptions"] = {
            "pie": {
                "borderColor": COLORS["bg_dark"],
                "borderWidth": 2,
                "dataLabels": {
                    "enabled": True,
                    "format": "{point.name}: {point.percentage:.1f}%",
                    "style": {
                        "color": COLORS["text"],
                        "fontSize": "11px",
                        "textOutline": "none"
                    }
                }
            }
        }
    else:
        # Standard series for line, column, bar, area
        highcharts_config["series"] = [{
            "name": config.seriesName,
            "data": config.seriesData,
            "color": COLORS["primary"],
        }]

    # Configure tooltip
    tooltip = {
        "backgroundColor": COLORS["bg_card"],
        "borderColor": COLORS["border"],
        "borderRadius": 4,
        "style": {
            "color": COLORS["text"],
            "fontSize": "12px"
        }
    }
    if config.valuePrefix:
        tooltip["valuePrefix"] = config.valuePrefix
    if config.valueSuffix:
        tooltip["valueSuffix"] = config.valueSuffix
    if config.valueDecimals is not None:
        tooltip["valueDecimals"] = config.valueDecimals

    highcharts_config["tooltip"] = tooltip

    # Legend styling
    highcharts_config["legend"] = {
        "itemStyle": {
            "color": COLORS["text_muted"],
            "fontSize": "11px"
        },
        "itemHoverStyle": {
            "color": COLORS["text"]
        }
    }

    # Disable credits
    highcharts_config["credits"] = {"enabled": False}

    return highcharts_config

runner = Runner(
    agent=chart_generator,
    app_name="chart_generator",
    session_service=session_service,
)


async def generate_chart(
    user_question: str,
    final_answer: Dict[str, Any],
    analysis_plan: Dict[str, Any],
    query_results: list,
) -> Optional[Dict[str, Any]]:
    """
    Evaluate if a chart is needed and generate Highcharts config.

    Args:
        user_question: The original user question
        final_answer: The FinalAnswer dict (summary, findings, evidence, etc.)
        analysis_plan: The AnalysisPlan dict (metrics, dimensions, time_range, etc.)
        query_results: List of query results from tools (run_query, compare_periods, etc.)

    Returns:
        Highcharts config dict if chart is needed, None otherwise
    """
    try:
        # Create a session with chart generation context
        session = await session_service.create_session(
            app_name="chart_generator",
            user_id="user",
            session_id=f"chart_{hash(user_question)}",
            state={
                "user_question": user_question,
                "final_answer": final_answer,
                "analysis_plan": analysis_plan,
                "query_results": query_results,
            },
        )

        # Prompt the chart generator to analyze and decide
        metrics = analysis_plan.get('metrics', [])
        dimensions = analysis_plan.get('dimensions', [])
        time_range = analysis_plan.get('time_range', '')

        # Detect if this is a distribution/breakdown query
        is_distribution = False
        if dimensions and len(dimensions) > 0:
            # Traffic/session metrics broken down by source/channel/device are distributions
            traffic_metrics = ['sessions', 'traffic', 'visitors', 'users', 'visits']
            distribution_dims = ['traffic_source', 'channel', 'device', 'device_os', 'utm_medium']

            if any(m in str(metrics).lower() for m in traffic_metrics):
                if any(d in str(dimensions).lower() for d in distribution_dims):
                    is_distribution = True

        prompt = (
            f"Analyze this analytics query and decide if a chart would be helpful:\n\n"
            f"Question: {user_question}\n\n"
            f"Answer Summary: {final_answer.get('summary', '')}\n\n"
            f"Metric(s): {metrics}\n"
            f"Dimension(s): {dimensions}\n"
            f"Time Range: {time_range}\n\n"
        )

        if is_distribution:
            prompt += (
                f"NOTE: This appears to be a distribution/breakdown query "
                f"(showing how {metrics} is split across {dimensions}). "
                f"Consider using a PIE chart to show parts of a whole.\n\n"
            )

        prompt += f"Data available in query_results."

        message = Content(role="user", parts=[Part(text=prompt)])

        events = []
        async for event in runner.run_async(
            user_id="user",
            session_id=session.id,
            new_message=message,
        ):
            events.append(event)

        # Extract the chart decision
        final_event = next(
            (e.content for e in reversed(events) if e.content),
            None,
        )

        if final_event is None:
            logger.warning("Chart generator produced no output")
            return None

        # Parse the response
        raw_text = " ".join(
            p.text for p in final_event.parts if getattr(p, "text", None)
        ).strip()

        decision = ChartDecision.model_validate_json(raw_text)

        if decision.needs_chart and decision.chart_config:
            # Convert simplified config to full Highcharts config
            chart_config = convert_to_highcharts(decision.chart_config)
            logger.info(
                f"Chart generated: type={decision.chart_config.type}, "
                f"title={decision.chart_config.title}"
            )
            return chart_config
        else:
            logger.info("No chart needed for this query")
            return None

    except Exception as e:
        logger.warning(f"Chart generation failed: {e}", exc_info=True)
        return None  # Fail gracefully - don't break the response
