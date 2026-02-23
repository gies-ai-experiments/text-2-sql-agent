"""
Artifact Builder for Assessment Results.

Builds A2A artifacts with rankings and detailed scores from assessment results.
"""

from datetime import datetime
from typing import Any, Dict, List

from .config import (
    AssessmentConfig,
    ScoreSummary,
    TaskResult,
    ParticipantSummary,
    RankedParticipant,
    AssessmentArtifact,
)
from .error_metrics import (
    SQLErrorClassifier,
    ErrorMetricsSummary,
    create_error_classifier,
)


class ArtifactBuilder:
    """Builds assessment artifacts from evaluation results."""

    # Shared classifier instance
    _classifier: SQLErrorClassifier = None

    @classmethod
    def _get_classifier(cls) -> SQLErrorClassifier:
        """Get or create the error classifier."""
        if cls._classifier is None:
            cls._classifier = create_error_classifier()
        return cls._classifier

    @staticmethod
    def build(
        assessment_id: str,
        config: AssessmentConfig,
        participants: Dict[str, str],
        results: Dict[str, List[TaskResult]],
    ) -> AssessmentArtifact:
        """
        Build assessment artifact from results.

        Args:
            assessment_id: Unique assessment identifier
            config: Assessment configuration used
            participants: Mapping of participant_id to endpoint
            results: Mapping of participant_id to list of TaskResults

        Returns:
            AssessmentArtifact with rankings, detailed scores, and error metrics
        """
        participant_summaries: Dict[str, ParticipantSummary] = {}
        classifier = ArtifactBuilder._get_classifier()

        # Aggregate error metrics across all participants
        aggregate_metrics = ErrorMetricsSummary()

        for pid, task_results in results.items():
            # Classify errors for each task result
            participant_metrics = ErrorMetricsSummary()

            for task_result in task_results:
                classification = classifier.classify(
                    sql_submitted=task_result.sql_submitted,
                    gold_sql=task_result.gold_sql,
                    execution_success=task_result.execution_success,
                    validation_errors=task_result.validation_errors,
                    phantom_tables=task_result.phantom_tables,
                    phantom_columns=task_result.phantom_columns,
                    error_message=task_result.error_message,
                    match_score=task_result.scores.correctness,
                    correctness_score=task_result.scores.overall,
                )

                # Update task result with classification
                task_result.error_category = classification.category.value
                task_result.error_subcategory = classification.subcategory.value
                task_result.error_details = classification.details

                # Add to participant metrics
                participant_metrics.add_classification(
                    classification,
                    task_result.task_id,
                    task_result.sql_submitted,
                )

                # Add to aggregate metrics
                aggregate_metrics.add_classification(
                    classification,
                    f"{pid}:{task_result.task_id}",
                    task_result.sql_submitted,
                )

            summary = ArtifactBuilder._build_participant_summary(
                participant_id=pid,
                endpoint=participants.get(pid, ""),
                task_results=task_results,
                error_metrics=participant_metrics.to_dict(),
            )
            participant_summaries[pid] = summary

        # Build rankings
        rankings = ArtifactBuilder._build_rankings(participant_summaries)

        # Build task comparison
        task_comparison = ArtifactBuilder._build_task_comparison(results)

        # Build config dict
        config_dict = {
            "difficulty": config.difficulty,
            "task_count": config.task_count,
            "tags": config.tags,
            "schema_type": config.schema_type,
            "scorer_preset": config.scorer_preset,
            "dialect": config.dialect,
        }

        return AssessmentArtifact(
            assessment_id=assessment_id,
            completed_at=datetime.utcnow().isoformat(),
            config=config_dict,
            rankings=rankings,
            participants=participant_summaries,
            task_comparison=task_comparison,
            metadata={
                "total_tasks_evaluated": sum(len(tr) for tr in results.values()),
                "total_participants": len(participants),
            },
            error_metrics_summary=aggregate_metrics.to_dict(),
        )

    @staticmethod
    def _build_participant_summary(
        participant_id: str,
        endpoint: str,
        task_results: List[TaskResult],
        error_metrics: Dict[str, Any] = None,
    ) -> ParticipantSummary:
        """Build summary for a single participant."""
        if not task_results:
            return ParticipantSummary(
                participant_id=participant_id,
                endpoint=endpoint,
                total_tasks=0,
                successful=0,
                failed=0,
                scores=ScoreSummary(
                    overall=0.0,
                    correctness=0.0,
                    efficiency=0.0,
                    safety=0.0,
                    completeness=0.0,
                    semantic_accuracy=0.0,
                    best_practices=0.0,
                    plan_quality=0.0,
                ),
                task_results=[],
                error_metrics=error_metrics,
            )

        # Calculate aggregate scores
        successful = sum(1 for tr in task_results if tr.execution_success)
        failed = len(task_results) - successful

        # Average scores across all tasks
        avg_scores = ArtifactBuilder._average_scores(task_results)

        return ParticipantSummary(
            participant_id=participant_id,
            endpoint=endpoint,
            total_tasks=len(task_results),
            successful=successful,
            failed=failed,
            scores=avg_scores,
            task_results=task_results,
            error_metrics=error_metrics,
        )

    @staticmethod
    def _average_scores(task_results: List[TaskResult]) -> ScoreSummary:
        """Calculate average scores across task results."""
        if not task_results:
            return ScoreSummary(
                overall=0.0,
                correctness=0.0,
                efficiency=0.0,
                safety=0.0,
                completeness=0.0,
                semantic_accuracy=0.0,
                best_practices=0.0,
                plan_quality=0.0,
            )

        n = len(task_results)

        return ScoreSummary(
            overall=sum(tr.scores.overall for tr in task_results) / n,
            correctness=sum(tr.scores.correctness for tr in task_results) / n,
            efficiency=sum(tr.scores.efficiency for tr in task_results) / n,
            safety=sum(tr.scores.safety for tr in task_results) / n,
            completeness=sum(tr.scores.completeness for tr in task_results) / n,
            semantic_accuracy=sum(tr.scores.semantic_accuracy for tr in task_results) / n,
            best_practices=sum(tr.scores.best_practices for tr in task_results) / n,
            plan_quality=sum(tr.scores.plan_quality for tr in task_results) / n,
            hallucination_score=sum(tr.scores.hallucination_score for tr in task_results) / n,
            validation_score=sum(tr.scores.validation_score for tr in task_results) / n,
            performance_score=sum(tr.scores.performance_score for tr in task_results) / n,
        )

    @staticmethod
    def _build_rankings(
        participant_summaries: Dict[str, ParticipantSummary]
    ) -> List[RankedParticipant]:
        """Build rankings sorted by overall score."""
        # Sort by overall score descending
        sorted_participants = sorted(
            participant_summaries.items(),
            key=lambda x: x[1].scores.overall,
            reverse=True,
        )

        rankings = []
        for rank, (pid, summary) in enumerate(sorted_participants, start=1):
            rankings.append(RankedParticipant(
                rank=rank,
                participant_id=pid,
                overall_score=summary.scores.overall,
            ))

        return rankings

    @staticmethod
    def _build_task_comparison(
        results: Dict[str, List[TaskResult]]
    ) -> List[Dict[str, Any]]:
        """Build task-by-task comparison across participants."""
        if not results:
            return []

        # Get all task IDs from first participant
        first_participant = next(iter(results.values()))
        if not first_participant:
            return []

        task_ids = [tr.task_id for tr in first_participant]

        comparison = []
        for i, task_id in enumerate(task_ids):
            task_scores = {"task_id": task_id, "agent_scores": {}}

            for pid, task_results in results.items():
                if i < len(task_results):
                    tr = task_results[i]
                    task_scores["agent_scores"][pid] = {
                        "overall": round(tr.scores.overall, 4),
                        "sql": tr.sql_submitted[:200] if tr.sql_submitted else "",
                        "execution_success": tr.execution_success,
                    }

            comparison.append(task_scores)

        return comparison
