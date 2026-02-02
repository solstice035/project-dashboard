"""APScheduler-based email automation scheduler."""

import logging
from datetime import datetime
from typing import Optional, Callable

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    BackgroundScheduler = None

from .jobs import JobRegistry, JobDefinition

logger = logging.getLogger(__name__)


class EmailScheduler:
    """APScheduler-based scheduler for email automation jobs.

    Integrates with Flask app lifecycle - starts when server starts,
    stops when server stops.
    """

    def __init__(
        self,
        config: dict,
        job_registry: Optional[JobRegistry] = None
    ):
        """Initialize scheduler with configuration.

        Args:
            config: The 'scheduling' section from config.yaml
            job_registry: Optional pre-configured JobRegistry
        """
        self.config = config
        self.enabled = config.get("enabled", False) and APSCHEDULER_AVAILABLE
        self.registry = job_registry or JobRegistry()
        self._scheduler: Optional[BackgroundScheduler] = None
        self._running = False

        if not APSCHEDULER_AVAILABLE:
            logger.warning(
                "APScheduler not installed. Install with: pip install apscheduler"
            )

    def register_job(self, job: JobDefinition) -> None:
        """Register a job definition."""
        self.registry.register(job)

    def start(self) -> bool:
        """Start the scheduler.

        Returns:
            True if scheduler started successfully
        """
        if not self.enabled:
            logger.info("Scheduler disabled in config")
            return False

        if self._running:
            logger.warning("Scheduler already running")
            return True

        if not APSCHEDULER_AVAILABLE:
            logger.error("Cannot start scheduler - APScheduler not installed")
            return False

        try:
            self._scheduler = BackgroundScheduler(
                job_defaults={
                    "coalesce": True,  # Combine missed runs into one
                    "max_instances": 1,  # Only one instance per job
                    "misfire_grace_time": 300,  # 5 min grace period
                }
            )

            self._configure_jobs()
            self._scheduler.start()
            self._running = True

            logger.info("Email scheduler started")
            return True

        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            return False

    def stop(self) -> None:
        """Stop the scheduler."""
        if self._scheduler and self._running:
            self._scheduler.shutdown(wait=False)
            self._running = False
            logger.info("Email scheduler stopped")

    def _configure_jobs(self) -> None:
        """Configure scheduled jobs from config."""
        jobs_config = self.config.get("jobs", {})

        for job_id, job_config in jobs_config.items():
            if not job_config.get("enabled", True):
                logger.info(f"Job {job_id} disabled in config")
                continue

            job = self.registry.get(job_id)
            if not job:
                logger.warning(f"No handler registered for job: {job_id}")
                continue

            trigger = self._create_trigger(job_config)
            if trigger:
                self._scheduler.add_job(
                    func=lambda jid=job_id: self.registry.run_job(jid, "scheduled"),
                    trigger=trigger,
                    id=job_id,
                    name=job.name,
                    replace_existing=True,
                )
                logger.info(f"Scheduled job: {job_id}")

    def _create_trigger(self, job_config: dict):
        """Create APScheduler trigger from job config."""
        if "cron" in job_config:
            # Parse cron expression: "0 7,18 * * 1-5"
            cron_parts = job_config["cron"].split()
            if len(cron_parts) == 5:
                return CronTrigger(
                    minute=cron_parts[0],
                    hour=cron_parts[1],
                    day=cron_parts[2],
                    month=cron_parts[3],
                    day_of_week=cron_parts[4],
                )
            else:
                logger.error(f"Invalid cron expression: {job_config['cron']}")
                return None

        elif "interval_hours" in job_config:
            return IntervalTrigger(hours=job_config["interval_hours"])

        elif "interval_minutes" in job_config:
            return IntervalTrigger(minutes=job_config["interval_minutes"])

        elif "time" in job_config:
            # Daily at specific time: "20:00"
            time_parts = job_config["time"].split(":")
            return CronTrigger(
                hour=int(time_parts[0]),
                minute=int(time_parts[1]) if len(time_parts) > 1 else 0,
            )

        logger.warning(f"No valid trigger in job config: {job_config}")
        return None

    def run_job_now(self, job_id: str) -> dict:
        """Manually trigger a job to run immediately.

        Args:
            job_id: ID of job to run

        Returns:
            Job execution results
        """
        return self.registry.run_job(job_id, "manual")

    def get_status(self) -> dict:
        """Get scheduler and job status.

        Returns:
            Status dictionary
        """
        status = {
            "scheduler_enabled": self.enabled,
            "scheduler_running": self._running,
            "apscheduler_available": APSCHEDULER_AVAILABLE,
            "registered_jobs": self.registry.list_jobs(),
            "scheduled_jobs": [],
        }

        if self._scheduler and self._running:
            for job in self._scheduler.get_jobs():
                next_run = job.next_run_time
                status["scheduled_jobs"].append({
                    "id": job.id,
                    "name": job.name,
                    "next_run": next_run.isoformat() if next_run else None,
                })

        return status

    def get_next_run_time(self, job_id: str) -> Optional[datetime]:
        """Get next scheduled run time for a job.

        Args:
            job_id: Job ID to check

        Returns:
            Next run datetime or None
        """
        if not self._scheduler or not self._running:
            return None

        job = self._scheduler.get_job(job_id)
        return job.next_run_time if job else None
