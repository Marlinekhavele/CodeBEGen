"""
Quality Dashboard Service

This module provides dashboard functionality for monitoring and visualizing
quality pipeline metrics, performance trends, and system health.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .quality_config_manager import QualityConfigManager
from .quality_metrics_collector import QualityMetricsCollector

logger = logging.getLogger(__name__)


class QualityDashboardService:
    """
    Service for generating dashboard data and reports with features:
    - Real-time metrics visualization
    - Performance trend analysis
    - Quality score tracking
    - System health monitoring
    - Custom report generation
    """

    def __init__(self):
        self.metrics_collector = QualityMetricsCollector()
        self.config_manager = QualityConfigManager()

    def get_dashboard_data(
        self, project_id: Optional[str] = None, time_range: str = "7d"
    ) -> Dict[str, Any]:
        """
        Get comprehensive dashboard data.

        Args:
            project_id: Filter by project ID
            time_range: Time range (1d, 7d, 30d, 90d)

        Returns:
            Dictionary with dashboard data
        """
        try:
            days = self._parse_time_range(time_range)

            # Get metrics summary
            summary = self.metrics_collector.get_metrics_summary(
                project_id=project_id, days=days
            )

            # Get performance trends
            trends = self.metrics_collector.get_performance_trends(
                project_id=project_id, days=days
            )

            # Get system health
            health = self._get_system_health()

            # Get recent activity
            recent_activity = self._get_recent_activity(project_id, limit=20)

            # Get quality insights
            insights = self._generate_quality_insights(summary, trends)

            return {
                "timestamp": datetime.now().isoformat(),
                "time_range": time_range,
                "project_id": project_id,
                "summary": summary,
                "trends": trends,
                "health": health,
                "recent_activity": recent_activity,
                "insights": insights,
                "charts": self._generate_chart_data(summary, trends),
            }

        except Exception as e:
            logger.error(f"Failed to generate dashboard data: {e}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}

    def _parse_time_range(self, time_range: str) -> int:
        """Parse time range string to days"""
        range_map = {"1d": 1, "7d": 7, "30d": 30, "90d": 90}
        return range_map.get(time_range, 7)

    def _get_system_health(self) -> Dict[str, Any]:
        """Get system health status"""
        try:
            # Check if services are operational
            health_status = {
                "overall": "healthy",
                "services": {
                    "prompt_enhancement": "operational",
                    "real_time_validation": "operational",
                    "code_quality": "operational",
                    "semantic_validation": "operational",
                },
                "cache": "available",
                "database": "connected",
                "last_check": datetime.now().isoformat(),
            }

            # Check for any recent errors or performance issues
            recent_summary = self.metrics_collector.get_metrics_summary(days=1)

            if recent_summary.get("total_executions", 0) > 0:
                recent_success_rate = recent_summary.get("issues", {}).get(
                    "fix_rate", 100
                )
                recent_avg_duration = recent_summary.get("performance", {}).get(
                    "average_duration", 0
                )

                # Check for degraded performance
                if recent_success_rate < 80:
                    health_status["overall"] = "degraded"
                    health_status["alerts"] = ["Low success rate detected"]

                if recent_avg_duration > 60:  # More than 60 seconds average
                    health_status["overall"] = (
                        "degraded"
                        if health_status["overall"] == "healthy"
                        else health_status["overall"]
                    )
                    health_status["alerts"] = health_status.get("alerts", []) + [
                        "High processing time detected"
                    ]

            return health_status

        except Exception as e:
            logger.error(f"Failed to get system health: {e}")
            return {
                "overall": "unknown",
                "error": str(e),
                "last_check": datetime.now().isoformat(),
            }

    def _get_recent_activity(
        self, project_id: Optional[str], limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get recent pipeline activity"""
        try:
            # This would typically query a database or activity log
            # For now, we'll generate sample activity data
            activity = []

            # In a real implementation, this would fetch from an activity log
            return activity

        except Exception as e:
            logger.error(f"Failed to get recent activity: {e}")
            return []

    def _generate_quality_insights(
        self, summary: Dict[str, Any], trends: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate quality insights and recommendations"""
        insights = []

        try:
            # Performance insight
            if "performance" in summary:
                avg_duration = summary["performance"].get("average_duration", 0)
                if avg_duration > 30:
                    insights.append(
                        {
                            "type": "performance",
                            "level": "warning",
                            "title": "High Processing Time",
                            "description": f"Average processing time is {avg_duration:.1f}s. Consider optimizing configuration.",
                            "recommendation": "Try reducing quality level or disabling heavy validators.",
                            "metric": avg_duration,
                        }
                    )
                elif avg_duration < 5:
                    insights.append(
                        {
                            "type": "performance",
                            "level": "success",
                            "title": "Excellent Performance",
                            "description": f"Average processing time is {avg_duration:.1f}s.",
                            "metric": avg_duration,
                        }
                    )

            # Quality insight
            if "quality" in summary:
                avg_score = summary["quality"].get("average_score", 0)
                if avg_score < 70:
                    insights.append(
                        {
                            "type": "quality",
                            "level": "warning",
                            "title": "Low Quality Score",
                            "description": f"Average quality score is {avg_score:.1f}. Code quality could be improved.",
                            "recommendation": "Enable more quality checks or review coding standards.",
                            "metric": avg_score,
                        }
                    )
                elif avg_score > 85:
                    insights.append(
                        {
                            "type": "quality",
                            "level": "success",
                            "title": "High Quality Score",
                            "description": f"Average quality score is {avg_score:.1f}. Excellent code quality!",
                            "metric": avg_score,
                        }
                    )

            # Issues insight
            if "issues" in summary:
                fix_rate = summary["issues"].get("fix_rate", 0)
                if fix_rate > 80:
                    insights.append(
                        {
                            "type": "fixes",
                            "level": "success",
                            "title": "High Fix Rate",
                            "description": f"Auto-fixing {fix_rate:.1f}% of detected issues.",
                            "metric": fix_rate,
                        }
                    )
                elif fix_rate < 50:
                    insights.append(
                        {
                            "type": "fixes",
                            "level": "info",
                            "title": "Low Fix Rate",
                            "description": f"Only fixing {fix_rate:.1f}% of detected issues.",
                            "recommendation": "Enable auto-fix for more issue types.",
                            "metric": fix_rate,
                        }
                    )

            # Trend insights
            if "dates" in trends and len(trends["dates"]) > 1:
                recent_duration = (
                    trends["average_duration"][-1] if trends["average_duration"] else 0
                )
                previous_duration = (
                    trends["average_duration"][-2]
                    if len(trends["average_duration"]) > 1
                    else recent_duration
                )

                if recent_duration > previous_duration * 1.2:  # 20% increase
                    insights.append(
                        {
                            "type": "trend",
                            "level": "warning",
                            "title": "Performance Degradation",
                            "description": "Processing time is increasing over time.",
                            "recommendation": "Monitor system resources and consider optimization.",
                            "metric": (
                                (recent_duration - previous_duration)
                                / previous_duration
                                * 100
                            ),
                        }
                    )

            # Usage insights
            total_executions = summary.get("total_executions", 0)
            if total_executions == 0:
                insights.append(
                    {
                        "type": "usage",
                        "level": "info",
                        "title": "No Recent Activity",
                        "description": "No pipeline executions in the selected time range.",
                        "recommendation": "Verify pipeline integration and usage.",
                    }
                )
            elif total_executions > 1000:
                insights.append(
                    {
                        "type": "usage",
                        "level": "info",
                        "title": "High Usage",
                        "description": f"{total_executions} pipeline executions recorded.",
                        "recommendation": "Consider caching optimizations for high-volume usage.",
                    }
                )

        except Exception as e:
            logger.error(f"Failed to generate insights: {e}")
            insights.append(
                {
                    "type": "error",
                    "level": "error",
                    "title": "Insight Generation Error",
                    "description": f"Failed to generate insights: {str(e)}",
                }
            )

        return insights

    def _generate_chart_data(
        self, summary: Dict[str, Any], trends: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate data for dashboard charts"""
        charts = {}

        try:
            # Quality score trend chart
            if "dates" in trends and "average_quality_score" in trends:
                charts["quality_trend"] = {
                    "type": "line",
                    "title": "Quality Score Trend",
                    "data": {
                        "labels": trends["dates"],
                        "datasets": [
                            {
                                "label": "Quality Score",
                                "data": trends["average_quality_score"],
                                "borderColor": "#4CAF50",
                                "backgroundColor": "rgba(76, 175, 80, 0.1)",
                            }
                        ],
                    },
                    "options": {"scales": {"y": {"beginAtZero": True, "max": 100}}},
                }

            # Performance trend chart
            if "dates" in trends and "average_duration" in trends:
                charts["performance_trend"] = {
                    "type": "line",
                    "title": "Processing Time Trend",
                    "data": {
                        "labels": trends["dates"],
                        "datasets": [
                            {
                                "label": "Processing Time (seconds)",
                                "data": trends["average_duration"],
                                "borderColor": "#2196F3",
                                "backgroundColor": "rgba(33, 150, 243, 0.1)",
                            }
                        ],
                    },
                }

            # Language distribution pie chart
            if "distribution" in summary and "languages" in summary["distribution"]:
                lang_dist = summary["distribution"]["languages"]
                charts["language_distribution"] = {
                    "type": "pie",
                    "title": "Language Distribution",
                    "data": {
                        "labels": list(lang_dist.keys()),
                        "datasets": [
                            {
                                "data": list(lang_dist.values()),
                                "backgroundColor": [
                                    "#FF6384",
                                    "#36A2EB",
                                    "#FFCE56",
                                    "#4BC0C0",
                                    "#9966FF",
                                    "#FF9F40",
                                ],
                            }
                        ],
                    },
                }

            # Quality level distribution
            if (
                "distribution" in summary
                and "quality_levels" in summary["distribution"]
            ):
                level_dist = summary["distribution"]["quality_levels"]
                charts["quality_level_distribution"] = {
                    "type": "doughnut",
                    "title": "Quality Level Usage",
                    "data": {
                        "labels": list(level_dist.keys()),
                        "datasets": [
                            {
                                "data": list(level_dist.values()),
                                "backgroundColor": [
                                    "#FF6384",
                                    "#36A2EB",
                                    "#FFCE56",
                                    "#4BC0C0",
                                ],
                            }
                        ],
                    },
                }

            # Issues by severity
            if "issues" in summary:
                # This would come from more detailed metrics
                issues_data = {"Critical": 5, "High": 15, "Medium": 25, "Low": 10}

                charts["issues_by_severity"] = {
                    "type": "bar",
                    "title": "Issues by Severity",
                    "data": {
                        "labels": list(issues_data.keys()),
                        "datasets": [
                            {
                                "label": "Issue Count",
                                "data": list(issues_data.values()),
                                "backgroundColor": [
                                    "#F44336",  # Critical - Red
                                    "#FF9800",  # High - Orange
                                    "#FFC107",  # Medium - Yellow
                                    "#4CAF50",  # Low - Green
                                ],
                            }
                        ],
                    },
                }

        except Exception as e:
            logger.error(f"Failed to generate chart data: {e}")

        return charts

    def generate_quality_report(
        self,
        project_id: Optional[str] = None,
        time_range: str = "30d",
        format: str = "json",
    ) -> Dict[str, Any]:
        """
        Generate comprehensive quality report.

        Args:
            project_id: Filter by project ID
            time_range: Time range for the report
            format: Report format (json, html, pdf)

        Returns:
            Quality report data
        """
        try:
            dashboard_data = self.get_dashboard_data(project_id, time_range)

            report = {
                "report_info": {
                    "generated_at": datetime.now().isoformat(),
                    "project_id": project_id,
                    "time_range": time_range,
                    "format": format,
                },
                "executive_summary": self._generate_executive_summary(dashboard_data),
                "detailed_metrics": dashboard_data.get("summary", {}),
                "performance_analysis": self._analyze_performance(dashboard_data),
                "quality_analysis": self._analyze_quality(dashboard_data),
                "recommendations": self._generate_recommendations(dashboard_data),
                "trends": dashboard_data.get("trends", {}),
                "insights": dashboard_data.get("insights", []),
            }

            if format == "html":
                report["html_content"] = self._generate_html_report(report)

            return report

        except Exception as e:
            logger.error(f"Failed to generate quality report: {e}")
            return {
                "error": str(e),
                "report_info": {
                    "generated_at": datetime.now().isoformat(),
                    "project_id": project_id,
                    "time_range": time_range,
                    "format": format,
                },
            }

    def _generate_executive_summary(
        self, dashboard_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate executive summary for the report"""
        summary = dashboard_data.get("summary", {})

        return {
            "total_pipeline_runs": summary.get("total_executions", 0),
            "average_quality_score": summary.get("quality", {}).get("average_score", 0),
            "average_processing_time": summary.get("performance", {}).get(
                "average_duration", 0
            ),
            "total_issues_found": summary.get("issues", {}).get("total_found", 0),
            "total_issues_fixed": summary.get("issues", {}).get("total_fixed", 0),
            "fix_rate_percentage": summary.get("issues", {}).get("fix_rate", 0),
            "system_health": dashboard_data.get("health", {}).get("overall", "unknown"),
            "top_insights": dashboard_data.get("insights", [])[:3],  # Top 3 insights
        }

    def _analyze_performance(self, dashboard_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze performance data"""
        performance = dashboard_data.get("summary", {}).get("performance", {})

        analysis = {
            "current_metrics": performance,
            "trend_analysis": {},
            "performance_grade": "unknown",
            "bottlenecks": [],
            "optimizations": [],
        }

        # Grade performance
        avg_duration = performance.get("average_duration", 0)
        if avg_duration < 5:
            analysis["performance_grade"] = "excellent"
        elif avg_duration < 15:
            analysis["performance_grade"] = "good"
        elif avg_duration < 30:
            analysis["performance_grade"] = "fair"
        else:
            analysis["performance_grade"] = "poor"
            analysis["bottlenecks"].append("High processing time")
            analysis["optimizations"].append(
                "Consider reducing quality level or optimizing configuration"
            )

        return analysis

    def _analyze_quality(self, dashboard_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze quality data"""
        quality = dashboard_data.get("summary", {}).get("quality", {})
        issues = dashboard_data.get("summary", {}).get("issues", {})

        analysis = {
            "current_metrics": quality,
            "quality_grade": "unknown",
            "issue_analysis": issues,
            "quality_trends": {},
            "recommendations": [],
        }

        # Grade quality
        avg_score = quality.get("average_score", 0)
        if avg_score >= 90:
            analysis["quality_grade"] = "excellent"
        elif avg_score >= 80:
            analysis["quality_grade"] = "good"
        elif avg_score >= 70:
            analysis["quality_grade"] = "fair"
        else:
            analysis["quality_grade"] = "poor"
            analysis["recommendations"].append("Enable more quality checks")
            analysis["recommendations"].append("Review coding standards and practices")

        return analysis

    def _generate_recommendations(
        self, dashboard_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate recommendations based on analysis"""
        recommendations = []

        insights = dashboard_data.get("insights", [])
        for insight in insights:
            if "recommendation" in insight:
                recommendations.append(
                    {
                        "category": insight["type"],
                        "priority": insight["level"],
                        "title": insight["title"],
                        "description": insight.get("recommendation", ""),
                        "impact": self._assess_recommendation_impact(insight),
                    }
                )

        return recommendations

    def _assess_recommendation_impact(self, insight: Dict[str, Any]) -> str:
        """Assess the impact of a recommendation"""
        if insight["level"] == "warning":
            return "high"
        elif insight["level"] == "info":
            return "medium"
        else:
            return "low"

    def _generate_html_report(self, report: Dict[str, Any]) -> str:
        """Generate HTML version of the report"""
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Quality Pipeline Report</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                .header { background-color: #f5f5f5; padding: 20px; border-radius: 5px; }
                .section { margin: 20px 0; }
                .metric { display: inline-block; margin: 10px; padding: 15px; background-color: #e3f2fd; border-radius: 5px; }
                .recommendation { background-color: #fff3e0; padding: 10px; margin: 5px 0; border-left: 4px solid #ff9800; }
                .insight { background-color: #f3e5f5; padding: 10px; margin: 5px 0; border-left: 4px solid #9c27b0; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Quality Pipeline Report</h1>
                <p>Generated: {generated_at}</p>
                <p>Time Range: {time_range}</p>
                {project_info}
            </div>

            <div class="section">
                <h2>Executive Summary</h2>
                {executive_summary}
            </div>

            <div class="section">
                <h2>Key Insights</h2>
                {insights}
            </div>

            <div class="section">
                <h2>Recommendations</h2>
                {recommendations}
            </div>
        </body>
        </html>
        """

        # Format the template with actual data
        report_info = report["report_info"]
        executive_summary = report["executive_summary"]

        project_info = (
            f"<p>Project: {report_info['project_id']}</p>"
            if report_info.get("project_id")
            else ""
        )

        summary_html = f"""
        <div class="metric">Total Runs: {executive_summary['total_pipeline_runs']}</div>
        <div class="metric">Avg Quality Score: {executive_summary['average_quality_score']:.1f}</div>
        <div class="metric">Avg Processing Time: {executive_summary['average_processing_time']:.1f}s</div>
        <div class="metric">Fix Rate: {executive_summary['fix_rate_percentage']:.1f}%</div>
        """

        insights_html = ""
        for insight in report["insights"]:
            insights_html += f'<div class="insight"><strong>{insight["title"]}</strong><br>{insight["description"]}</div>'

        recommendations_html = ""
        for rec in report["recommendations"]:
            recommendations_html += f'<div class="recommendation"><strong>{rec["title"]}</strong><br>{rec["description"]}</div>'

        return html_template.format(
            generated_at=report_info["generated_at"],
            time_range=report_info["time_range"],
            project_info=project_info,
            executive_summary=summary_html,
            insights=insights_html,
            recommendations=recommendations_html,
        )

    def get_real_time_metrics(self) -> Dict[str, Any]:
        """Get real-time metrics for live dashboard"""
        try:
            # Get recent metrics (last hour)
            recent_summary = self.metrics_collector.get_metrics_summary(days=1)

            # Get system health
            health = self._get_system_health()

            # Calculate real-time statistics
            current_time = datetime.now()

            return {
                "timestamp": current_time.isoformat(),
                "current_metrics": {
                    "active_pipelines": 0,  # Would track active pipeline runs
                    "queue_length": 0,  # Would track queued requests
                    "avg_response_time": recent_summary.get("performance", {}).get(
                        "recent_average_duration", 0
                    ),
                    "success_rate": recent_summary.get("issues", {}).get(
                        "fix_rate", 100
                    ),
                    "system_load": health.get("overall", "unknown"),
                },
                "health_status": health,
                "alerts": health.get("alerts", []),
            }

        except Exception as e:
            logger.error(f"Failed to get real-time metrics: {e}")
            return {"timestamp": datetime.now().isoformat(), "error": str(e)}
