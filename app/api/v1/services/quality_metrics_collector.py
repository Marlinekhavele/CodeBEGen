"""
Quality Metrics Collector

This module collects and analyzes quality metrics from the pipeline execution,
providing insights for performance optimization and quality improvement.
"""

import json
import logging
import statistics
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class QualityMetrics:
    """Quality metrics for a single pipeline execution"""

    timestamp: datetime
    project_id: str
    language: str
    quality_level: str

    # Execution metrics
    total_duration: float
    tier1_duration: float
    tier2_duration: float
    tier3_duration: float
    tier4_duration: float

    # Quality scores
    overall_score: float
    prompt_enhancement_score: float
    validation_score: float
    code_quality_score: float
    semantic_score: float

    # Issue counts
    total_issues: int
    critical_issues: int
    high_issues: int
    medium_issues: int
    low_issues: int
    issues_fixed: int

    # Code statistics
    lines_of_code: int
    functions_count: int
    classes_count: int
    complexity_score: float

    # Performance metrics
    memory_usage_mb: float
    cpu_usage_percent: float
    parallel_workers: int

    def __post_init__(self):
        if isinstance(self.timestamp, str):
            self.timestamp = datetime.fromisoformat(self.timestamp)


class QualityMetricsCollector:
    """
    Collector for quality pipeline metrics with features:
    - Real-time metrics collection
    - Historical data analysis
    - Performance trending
    - Quality insights generation
    """

    def __init__(self, metrics_dir: str = "quality_metrics"):
        self.metrics_dir = Path(metrics_dir)
        self.metrics_dir.mkdir(exist_ok=True)
        self.current_session_metrics: List[QualityMetrics] = []

    def collect_metrics(
        self,
        project_id: str,
        language: str,
        quality_level: str,
        pipeline_result: Dict[str, Any],
        execution_stats: Dict[str, Any],
    ) -> QualityMetrics:
        """
        Collect metrics from a pipeline execution.

        Args:
            project_id: Project identifier
            language: Programming language
            quality_level: Quality configuration level
            pipeline_result: Results from pipeline execution
            execution_stats: Execution statistics

        Returns:
            QualityMetrics: Collected metrics
        """
        try:
            # Extract timing information
            tiers = pipeline_result.get("tiers", {})

            metrics = QualityMetrics(
                timestamp=datetime.now(),
                project_id=project_id,
                language=language,
                quality_level=quality_level,
                # Execution metrics
                total_duration=execution_stats.get("total_duration", 0.0),
                tier1_duration=tiers.get("tier1", {}).get("duration", 0.0),
                tier2_duration=tiers.get("tier2", {}).get("duration", 0.0),
                tier3_duration=tiers.get("tier3", {}).get("duration", 0.0),
                tier4_duration=tiers.get("tier4", {}).get("duration", 0.0),
                # Quality scores
                overall_score=pipeline_result.get("quality_score", 0.0),
                prompt_enhancement_score=tiers.get("tier1", {}).get("score", 0.0),
                validation_score=tiers.get("tier2", {}).get("score", 0.0),
                code_quality_score=tiers.get("tier3", {}).get("score", 0.0),
                semantic_score=tiers.get("tier4", {}).get("score", 0.0),
                # Issue counts
                total_issues=pipeline_result.get("total_issues", 0),
                critical_issues=pipeline_result.get("critical_issues", 0),
                high_issues=pipeline_result.get("high_issues", 0),
                medium_issues=pipeline_result.get("medium_issues", 0),
                low_issues=pipeline_result.get("low_issues", 0),
                issues_fixed=pipeline_result.get("issues_fixed", 0),
                # Code statistics
                lines_of_code=execution_stats.get("lines_of_code", 0),
                functions_count=execution_stats.get("functions_count", 0),
                classes_count=execution_stats.get("classes_count", 0),
                complexity_score=execution_stats.get("complexity_score", 0.0),
                # Performance metrics
                memory_usage_mb=execution_stats.get("memory_usage_mb", 0.0),
                cpu_usage_percent=execution_stats.get("cpu_usage_percent", 0.0),
                parallel_workers=execution_stats.get("parallel_workers", 1),
            )

            # Store metrics
            self.current_session_metrics.append(metrics)
            self._save_metrics(metrics)

            return metrics

        except Exception as e:
            logger.error(f"Failed to collect metrics: {e}")
            # Return default metrics
            return QualityMetrics(
                timestamp=datetime.now(),
                project_id=project_id,
                language=language,
                quality_level=quality_level,
                total_duration=0.0,
                tier1_duration=0.0,
                tier2_duration=0.0,
                tier3_duration=0.0,
                tier4_duration=0.0,
                overall_score=0.0,
                prompt_enhancement_score=0.0,
                validation_score=0.0,
                code_quality_score=0.0,
                semantic_score=0.0,
                total_issues=0,
                critical_issues=0,
                high_issues=0,
                medium_issues=0,
                low_issues=0,
                issues_fixed=0,
                lines_of_code=0,
                functions_count=0,
                classes_count=0,
                complexity_score=0.0,
                memory_usage_mb=0.0,
                cpu_usage_percent=0.0,
                parallel_workers=1,
            )

    def _save_metrics(self, metrics: QualityMetrics):
        """Save metrics to file"""
        try:
            # Create daily metrics file
            date_str = metrics.timestamp.strftime("%Y-%m-%d")
            metrics_file = self.metrics_dir / f"metrics_{date_str}.jsonl"

            # Convert metrics to dict and handle datetime serialization
            metrics_dict = asdict(metrics)
            metrics_dict["timestamp"] = metrics.timestamp.isoformat()

            # Append to file
            with open(metrics_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(metrics_dict) + "\n")

        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")

    def get_metrics_summary(
        self,
        project_id: Optional[str] = None,
        language: Optional[str] = None,
        days: int = 7,
    ) -> Dict[str, Any]:
        """
        Get metrics summary for the specified period.

        Args:
            project_id: Filter by project ID
            language: Filter by language
            days: Number of days to include

        Returns:
            Dict containing metrics summary
        """
        try:
            metrics = self._load_metrics(project_id, language, days)

            if not metrics:
                return {
                    "total_executions": 0,
                    "average_duration": 0.0,
                    "average_quality_score": 0.0,
                    "total_issues_found": 0,
                    "total_issues_fixed": 0,
                }

            # Calculate summary statistics
            durations = [m.total_duration for m in metrics]
            quality_scores = [m.overall_score for m in metrics]
            total_issues = sum(m.total_issues for m in metrics)
            total_fixed = sum(m.issues_fixed for m in metrics)

            # Performance trending
            recent_metrics = metrics[-10:] if len(metrics) > 10 else metrics
            recent_avg_duration = statistics.mean(
                [m.total_duration for m in recent_metrics]
            )
            recent_avg_score = statistics.mean(
                [m.overall_score for m in recent_metrics]
            )

            # Language distribution
            language_counts = Counter(m.language for m in metrics)

            # Quality level distribution
            level_counts = Counter(m.quality_level for m in metrics)

            return {
                "total_executions": len(metrics),
                "date_range": {
                    "start": min(m.timestamp for m in metrics).isoformat(),
                    "end": max(m.timestamp for m in metrics).isoformat(),
                },
                "performance": {
                    "average_duration": statistics.mean(durations),
                    "median_duration": statistics.median(durations),
                    "min_duration": min(durations),
                    "max_duration": max(durations),
                    "recent_average_duration": recent_avg_duration,
                },
                "quality": {
                    "average_score": statistics.mean(quality_scores),
                    "median_score": statistics.median(quality_scores),
                    "min_score": min(quality_scores),
                    "max_score": max(quality_scores),
                    "recent_average_score": recent_avg_score,
                },
                "issues": {
                    "total_found": total_issues,
                    "total_fixed": total_fixed,
                    "fix_rate": (
                        (total_fixed / total_issues * 100) if total_issues > 0 else 0
                    ),
                    "average_per_execution": total_issues / len(metrics),
                },
                "distribution": {
                    "languages": dict(language_counts),
                    "quality_levels": dict(level_counts),
                },
                "tier_performance": self._calculate_tier_performance(metrics),
            }

        except Exception as e:
            logger.error(f"Failed to generate metrics summary: {e}")
            return {"error": str(e)}

    def _calculate_tier_performance(
        self, metrics: List[QualityMetrics]
    ) -> Dict[str, Any]:
        """Calculate performance statistics for each tier"""
        tier_stats = {}

        for tier_name, attr in [
            ("tier1_prompt_enhancement", "tier1_duration"),
            ("tier2_real_time_validation", "tier2_duration"),
            ("tier3_code_quality", "tier3_duration"),
            ("tier4_semantic_validation", "tier4_duration"),
        ]:
            durations = [getattr(m, attr) for m in metrics if getattr(m, attr) > 0]

            if durations:
                tier_stats[tier_name] = {
                    "average_duration": statistics.mean(durations),
                    "median_duration": statistics.median(durations),
                    "min_duration": min(durations),
                    "max_duration": max(durations),
                    "executions": len(durations),
                }
            else:
                tier_stats[tier_name] = {
                    "average_duration": 0.0,
                    "median_duration": 0.0,
                    "min_duration": 0.0,
                    "max_duration": 0.0,
                    "executions": 0,
                }

        return tier_stats

    def _load_metrics(
        self, project_id: Optional[str], language: Optional[str], days: int
    ) -> List[QualityMetrics]:
        """Load metrics from files with filtering"""
        metrics = []
        cutoff_date = datetime.now() - timedelta(days=days)

        try:
            # Load metrics from daily files
            for metrics_file in self.metrics_dir.glob("metrics_*.jsonl"):
                try:
                    with open(metrics_file, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.strip():
                                metric_data = json.loads(line)
                                metric = QualityMetrics(**metric_data)

                                # Apply filters
                                if metric.timestamp < cutoff_date:
                                    continue
                                if project_id and metric.project_id != project_id:
                                    continue
                                if language and metric.language != language:
                                    continue

                                metrics.append(metric)

                except Exception as e:
                    logger.warning(f"Error loading metrics file {metrics_file}: {e}")

            # Sort by timestamp
            metrics.sort(key=lambda m: m.timestamp)

        except Exception as e:
            logger.error(f"Failed to load metrics: {e}")

        return metrics

    def get_performance_trends(
        self, project_id: Optional[str] = None, days: int = 30
    ) -> Dict[str, Any]:
        """Get performance trends over time"""
        try:
            metrics = self._load_metrics(project_id, None, days)

            if not metrics:
                return {"error": "No metrics found"}

            # Group by date
            daily_metrics = defaultdict(list)
            for metric in metrics:
                date_key = metric.timestamp.strftime("%Y-%m-%d")
                daily_metrics[date_key].append(metric)

            # Calculate daily averages
            trends = {
                "dates": [],
                "average_duration": [],
                "average_quality_score": [],
                "total_executions": [],
                "issues_per_execution": [],
            }

            for date in sorted(daily_metrics.keys()):
                day_metrics = daily_metrics[date]

                trends["dates"].append(date)
                trends["average_duration"].append(
                    statistics.mean(m.total_duration for m in day_metrics)
                )
                trends["average_quality_score"].append(
                    statistics.mean(m.overall_score for m in day_metrics)
                )
                trends["total_executions"].append(len(day_metrics))
                trends["issues_per_execution"].append(
                    statistics.mean(m.total_issues for m in day_metrics)
                )

            return trends

        except Exception as e:
            logger.error(f"Failed to calculate performance trends: {e}")
            return {"error": str(e)}

    def export_metrics(
        self,
        output_file: str,
        project_id: Optional[str] = None,
        language: Optional[str] = None,
        days: int = 30,
    ) -> bool:
        """Export metrics to CSV file"""
        try:
            import csv

            metrics = self._load_metrics(project_id, language, days)

            if not metrics:
                logger.warning("No metrics to export")
                return False

            with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
                fieldnames = [
                    "timestamp",
                    "project_id",
                    "language",
                    "quality_level",
                    "total_duration",
                    "overall_score",
                    "total_issues",
                    "issues_fixed",
                    "lines_of_code",
                    "complexity_score",
                ]

                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                for metric in metrics:
                    row = {
                        "timestamp": metric.timestamp.isoformat(),
                        "project_id": metric.project_id,
                        "language": metric.language,
                        "quality_level": metric.quality_level,
                        "total_duration": metric.total_duration,
                        "overall_score": metric.overall_score,
                        "total_issues": metric.total_issues,
                        "issues_fixed": metric.issues_fixed,
                        "lines_of_code": metric.lines_of_code,
                        "complexity_score": metric.complexity_score,
                    }
                    writer.writerow(row)

            logger.info(f"Exported {len(metrics)} metrics to {output_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to export metrics: {e}")
            return False

    def cleanup_old_metrics(self, days_to_keep: int = 90) -> int:
        """Clean up old metrics files"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            cleaned_count = 0

            for metrics_file in self.metrics_dir.glob("metrics_*.jsonl"):
                try:
                    # Extract date from filename
                    date_part = metrics_file.stem.replace("metrics_", "")
                    file_date = datetime.strptime(date_part, "%Y-%m-%d")

                    if file_date < cutoff_date:
                        metrics_file.unlink()
                        cleaned_count += 1
                        logger.info(f"Deleted old metrics file: {metrics_file}")

                except Exception as e:
                    logger.warning(f"Error processing metrics file {metrics_file}: {e}")

            return cleaned_count

        except Exception as e:
            logger.error(f"Failed to cleanup old metrics: {e}")
            return 0
