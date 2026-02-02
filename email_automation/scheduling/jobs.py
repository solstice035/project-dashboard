"""Job definitions and registry for email automation tasks."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Callable, Any

logger = logging.getLogger(__name__)


@dataclass
class JobDefinition:
    """Definition of a scheduled job."""
    job_id: str
    name: str
    description: str
    func: Callable[[], dict]
    default_enabled: bool = True


class JobRegistry:
    """Registry of available email automation jobs."""

    def __init__(self):
        self._jobs: dict[str, JobDefinition] = {}
        self._db_start_callback: Optional[Callable[[str, str], int]] = None
        self._db_complete_callback: Optional[Callable[[int, str, dict, str], bool]] = None

    def set_db_callbacks(
        self,
        start_callback: Callable[[str, str], Optional[int]],
        complete_callback: Callable[[int, str, Optional[dict], Optional[str]], bool]
    ):
        """Set database callbacks for job tracking.

        Args:
            start_callback: Signature (job_id, trigger_type) -> run_id
            complete_callback: Signature (run_id, status, result, error) -> success
        """
        self._db_start_callback = start_callback
        self._db_complete_callback = complete_callback

    def register(self, job: JobDefinition) -> None:
        """Register a job definition."""
        self._jobs[job.job_id] = job
        logger.info(f"Registered job: {job.job_id}")

    def get(self, job_id: str) -> Optional[JobDefinition]:
        """Get a job definition by ID."""
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[dict]:
        """List all registered jobs."""
        return [
            {
                "job_id": job.job_id,
                "name": job.name,
                "description": job.description,
                "default_enabled": job.default_enabled,
            }
            for job in self._jobs.values()
        ]

    def run_job(self, job_id: str, trigger_type: str = "manual") -> dict:
        """Execute a job and track its run.

        Args:
            job_id: ID of job to run
            trigger_type: How the job was triggered ('scheduled', 'manual', 'http')

        Returns:
            Job execution results
        """
        job = self._jobs.get(job_id)
        if not job:
            return {"success": False, "error": f"Unknown job: {job_id}"}

        run_id = None
        if self._db_start_callback:
            try:
                run_id = self._db_start_callback(job_id, trigger_type)
            except Exception as e:
                logger.warning(f"Failed to record job start: {e}")

        logger.info(f"Running job: {job_id} (trigger: {trigger_type})")
        start_time = datetime.now()

        try:
            result = job.func()
            status = "success" if result.get("success", True) else "failed"
            error = result.get("error")

            duration = (datetime.now() - start_time).total_seconds()
            result["duration_seconds"] = duration

            logger.info(f"Job {job_id} completed: {status} in {duration:.2f}s")

        except Exception as e:
            logger.error(f"Job {job_id} failed with exception: {e}")
            result = {"success": False, "error": str(e)}
            status = "failed"
            error = str(e)

        if run_id and self._db_complete_callback:
            try:
                self._db_complete_callback(run_id, status, result, error)
            except Exception as e:
                logger.warning(f"Failed to record job completion: {e}")

        return result


def create_job_wrapper(
    job_func: Callable[[], dict],
    notify_callback: Optional[Callable[[str, str, str], None]] = None,
    source: str = "unknown"
) -> Callable[[], dict]:
    """Create a wrapped job function with notification support.

    Args:
        job_func: The actual job function to wrap
        notify_callback: Optional notification callback (title, body, priority)
        source: Source identifier for notifications

    Returns:
        Wrapped function
    """
    def wrapped() -> dict:
        result = job_func()

        # Send digest notification on success if callback provided
        if notify_callback and result.get("success", True):
            try:
                title = f"{source.title()} Job Complete"
                body = _format_result_body(result)
                notify_callback(title, body, "info")
            except Exception as e:
                logger.warning(f"Failed to send job notification: {e}")

        return result

    return wrapped


def _format_result_body(result: dict) -> str:
    """Format job result as notification body."""
    lines = []
    for key, value in result.items():
        if key in ("success", "error", "duration_seconds"):
            continue
        if isinstance(value, (int, str, bool)):
            lines.append(f"*{key.replace('_', ' ').title()}*: {value}")
    return "\n".join(lines) if lines else "Job completed successfully."
