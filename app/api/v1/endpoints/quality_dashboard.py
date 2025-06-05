"""
Quality Dashboard API Endpoints

This module provides REST API endpoints for the quality dashboard,
including metrics visualization, reporting, and real-time monitoring.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from app.api.v1.services.quality_dashboard_service import QualityDashboardService
from app.api.v1.services.quality_metrics_collector import QualityMetricsCollector

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["Quality Dashboard"])

# Initialize services
dashboard_service = QualityDashboardService()
metrics_collector = QualityMetricsCollector()


class DashboardRequest(BaseModel):
    """Request model for dashboard data"""

    project_id: Optional[str] = Field(None, description="Project identifier")
    time_range: str = Field("7d", description="Time range (1d, 7d, 30d, 90d)")


class ReportRequest(BaseModel):
    """Request model for report generation"""

    project_id: Optional[str] = Field(None, description="Project identifier")
    time_range: str = Field("30d", description="Time range for the report")
    format: str = Field("json", description="Report format (json, html)")
    include_charts: bool = Field(True, description="Include chart data")


@router.get("/", summary="Get Dashboard Data")
async def get_dashboard(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    time_range: str = Query("7d", description="Time range (1d, 7d, 30d, 90d)"),
) -> Dict[str, Any]:
    """
    Get comprehensive dashboard data including metrics, trends, and insights.

    Returns:
        Dashboard data with metrics, charts, and insights
    """
    try:
        dashboard_data = dashboard_service.get_dashboard_data(
            project_id=project_id, time_range=time_range
        )

        if "error" in dashboard_data:
            raise HTTPException(status_code=500, detail=dashboard_data["error"])

        return dashboard_data

    except Exception as e:
        logger.error(f"Failed to get dashboard data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics", summary="Get Metrics Summary")
async def get_metrics_summary(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    language: Optional[str] = Query(None, description="Filter by language"),
    days: int = Query(7, description="Number of days to include"),
) -> Dict[str, Any]:
    """
    Get metrics summary for the specified period.

    Returns:
        Metrics summary with performance and quality data
    """
    try:
        summary = metrics_collector.get_metrics_summary(
            project_id=project_id, language=language, days=days
        )

        return {"summary": summary, "timestamp": datetime.now().isoformat()}

    except Exception as e:
        logger.error(f"Failed to get metrics summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trends", summary="Get Performance Trends")
async def get_performance_trends(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    days: int = Query(30, description="Number of days to include"),
) -> Dict[str, Any]:
    """
    Get performance trends over time.

    Returns:
        Performance trends data for charting
    """
    try:
        trends = metrics_collector.get_performance_trends(
            project_id=project_id, days=days
        )

        return {"trends": trends, "timestamp": datetime.now().isoformat()}

    except Exception as e:
        logger.error(f"Failed to get performance trends: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", summary="Get System Health")
async def get_system_health() -> Dict[str, Any]:
    """
    Get real-time system health status.

    Returns:
        System health information
    """
    try:
        dashboard_data = dashboard_service.get_dashboard_data(time_range="1d")
        health = dashboard_data.get("health", {})

        return {"health": health, "timestamp": datetime.now().isoformat()}

    except Exception as e:
        logger.error(f"Failed to get system health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/real-time", summary="Get Real-time Metrics")
async def get_real_time_metrics() -> Dict[str, Any]:
    """
    Get real-time metrics for live dashboard updates.

    Returns:
        Real-time metrics and system status
    """
    try:
        metrics = dashboard_service.get_real_time_metrics()

        if "error" in metrics:
            raise HTTPException(status_code=500, detail=metrics["error"])

        return metrics

    except Exception as e:
        logger.error(f"Failed to get real-time metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/report", summary="Generate Quality Report")
async def generate_report(request: ReportRequest) -> Dict[str, Any]:
    """
    Generate a comprehensive quality report.

    Returns:
        Quality report with analysis and recommendations
    """
    try:
        report = dashboard_service.generate_quality_report(
            project_id=request.project_id,
            time_range=request.time_range,
            format=request.format,
        )

        if "error" in report:
            raise HTTPException(status_code=500, detail=report["error"])

        return report

    except Exception as e:
        logger.error(f"Failed to generate report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report/html", summary="Generate HTML Report", response_class=HTMLResponse)
async def generate_html_report(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    time_range: str = Query("30d", description="Time range for the report"),
) -> HTMLResponse:
    """
    Generate an HTML quality report.

    Returns:
        HTML formatted quality report
    """
    try:
        report = dashboard_service.generate_quality_report(
            project_id=project_id, time_range=time_range, format="html"
        )

        if "error" in report:
            raise HTTPException(status_code=500, detail=report["error"])

        html_content = report.get(
            "html_content", "<html><body><h1>Error generating report</h1></body></html>"
        )

        return HTMLResponse(content=html_content)

    except Exception as e:
        logger.error(f"Failed to generate HTML report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/metrics", summary="Export Metrics")
async def export_metrics(
    format: str = Query("csv", description="Export format (csv, json)"),
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    language: Optional[str] = Query(None, description="Filter by language"),
    days: int = Query(30, description="Number of days to include"),
):
    """
    Export metrics data in the specified format.

    Returns:
        Metrics data in the requested format
    """
    try:
        if format.lower() == "csv":
            # Generate temporary file path
            import os
            import tempfile

            temp_file = tempfile.NamedTemporaryFile(
                mode="w", suffix=".csv", delete=False
            )
            temp_file.close()

            # Export metrics to CSV
            success = metrics_collector.export_metrics(
                output_file=temp_file.name,
                project_id=project_id,
                language=language,
                days=days,
            )

            if not success:
                raise HTTPException(status_code=500, detail="Failed to export metrics")

            # Read the file content
            with open(temp_file.name, "r", encoding="utf-8") as f:
                csv_content = f.read()

            # Clean up temporary file
            os.unlink(temp_file.name)

            return Response(
                content=csv_content,
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=quality_metrics_{datetime.now().strftime('%Y%m%d')}.csv"
                },
            )

        elif format.lower() == "json":
            summary = metrics_collector.get_metrics_summary(
                project_id=project_id, language=language, days=days
            )

            return JSONResponse(
                content=summary,
                headers={
                    "Content-Disposition": f"attachment; filename=quality_metrics_{datetime.now().strftime('%Y%m%d')}.json"
                },
            )

        else:
            raise HTTPException(
                status_code=400, detail="Unsupported format. Use 'csv' or 'json'"
            )

    except Exception as e:
        logger.error(f"Failed to export metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/insights", summary="Get Quality Insights")
async def get_quality_insights(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    time_range: str = Query("7d", description="Time range for analysis"),
) -> Dict[str, Any]:
    """
    Get quality insights and recommendations.

    Returns:
        Quality insights with recommendations
    """
    try:
        dashboard_data = dashboard_service.get_dashboard_data(
            project_id=project_id, time_range=time_range
        )

        insights = dashboard_data.get("insights", [])

        return {
            "insights": insights,
            "total_insights": len(insights),
            "critical_insights": len(
                [i for i in insights if i.get("level") == "warning"]
            ),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get quality insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/charts/quality-trend", summary="Get Quality Trend Chart Data")
async def get_quality_trend_chart(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    days: int = Query(30, description="Number of days to include"),
) -> Dict[str, Any]:
    """
    Get quality trend chart data.

    Returns:
        Chart data for quality score trend
    """
    try:
        trends = metrics_collector.get_performance_trends(
            project_id=project_id, days=days
        )

        chart_data = {
            "type": "line",
            "data": {
                "labels": trends.get("dates", []),
                "datasets": [
                    {
                        "label": "Quality Score",
                        "data": trends.get("average_quality_score", []),
                        "borderColor": "#4CAF50",
                        "backgroundColor": "rgba(76, 175, 80, 0.1)",
                        "tension": 0.4,
                    }
                ],
            },
            "options": {
                "responsive": True,
                "scales": {
                    "y": {
                        "beginAtZero": True,
                        "max": 100,
                        "title": {"display": True, "text": "Quality Score"},
                    },
                    "x": {"title": {"display": True, "text": "Date"}},
                },
            },
        }

        return chart_data

    except Exception as e:
        logger.error(f"Failed to get quality trend chart: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/charts/performance-trend", summary="Get Performance Trend Chart Data")
async def get_performance_trend_chart(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    days: int = Query(30, description="Number of days to include"),
) -> Dict[str, Any]:
    """
    Get performance trend chart data.

    Returns:
        Chart data for processing time trend
    """
    try:
        trends = metrics_collector.get_performance_trends(
            project_id=project_id, days=days
        )

        chart_data = {
            "type": "line",
            "data": {
                "labels": trends.get("dates", []),
                "datasets": [
                    {
                        "label": "Processing Time (seconds)",
                        "data": trends.get("average_duration", []),
                        "borderColor": "#2196F3",
                        "backgroundColor": "rgba(33, 150, 243, 0.1)",
                        "tension": 0.4,
                    }
                ],
            },
            "options": {
                "responsive": True,
                "scales": {
                    "y": {
                        "beginAtZero": True,
                        "title": {"display": True, "text": "Processing Time (seconds)"},
                    },
                    "x": {"title": {"display": True, "text": "Date"}},
                },
            },
        }

        return chart_data

    except Exception as e:
        logger.error(f"Failed to get performance trend chart: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/metrics/cleanup", summary="Cleanup Old Metrics")
async def cleanup_old_metrics(
    days_to_keep: int = Query(90, description="Number of days to keep")
) -> Dict[str, Any]:
    """
    Clean up old metrics files.

    Returns:
        Cleanup results
    """
    try:
        cleaned_count = metrics_collector.cleanup_old_metrics(days_to_keep)

        return {
            "success": True,
            "cleaned_files": cleaned_count,
            "days_kept": days_to_keep,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to cleanup old metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary", summary="Get Dashboard Summary")
async def get_dashboard_summary(
    project_id: Optional[str] = Query(None, description="Filter by project ID")
) -> Dict[str, Any]:
    """
    Get a quick dashboard summary with key metrics.

    Returns:
        Dashboard summary with key performance indicators
    """
    try:
        # Get recent data
        dashboard_data = dashboard_service.get_dashboard_data(
            project_id=project_id, time_range="7d"
        )

        summary = dashboard_data.get("summary", {})
        health = dashboard_data.get("health", {})
        insights = dashboard_data.get("insights", [])

        # Extract key metrics
        key_metrics = {
            "total_executions": summary.get("total_executions", 0),
            "average_quality_score": summary.get("quality", {}).get("average_score", 0),
            "average_processing_time": summary.get("performance", {}).get(
                "average_duration", 0
            ),
            "success_rate": summary.get("issues", {}).get("fix_rate", 100),
            "system_health": health.get("overall", "unknown"),
            "critical_insights": len(
                [i for i in insights if i.get("level") == "warning"]
            ),
            "last_updated": datetime.now().isoformat(),
        }

        return {
            "summary": key_metrics,
            "status": "healthy" if health.get("overall") == "healthy" else "warning",
            "alerts": health.get("alerts", []),
        }

    except Exception as e:
        logger.error(f"Failed to get dashboard summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))
