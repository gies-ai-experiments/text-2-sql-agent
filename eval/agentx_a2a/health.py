"""
Health check system for AgentX A2A agents.

Provides:
- HealthCheck: Individual health check result
- HealthStatus: Aggregated health status with multiple checks
- HealthChecker: Comprehensive health checking for Green/Purple agents
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional


@dataclass
class HealthCheck:
    """Result of a single health check."""
    name: str
    status: str  # "pass", "fail", "warn"
    duration_ms: float
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "name": self.name,
            "status": self.status,
            "duration_ms": round(self.duration_ms, 2),
        }
        if self.message:
            result["message"] = self.message
        if self.details:
            result["details"] = self.details
        return result


@dataclass
class HealthStatus:
    """Aggregated health status from multiple checks."""
    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: str
    checks: List[HealthCheck] = field(default_factory=list)
    version: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "status": self.status,
            "timestamp": self.timestamp,
            "checks": [c.to_dict() for c in self.checks],
        }
        if self.version:
            result["version"] = self.version
        return result

    @property
    def healthy(self) -> bool:
        """Check if status is healthy."""
        return self.status == "healthy"

    @property
    def ready(self) -> bool:
        """Check if service is ready (healthy or degraded)."""
        return self.status in ("healthy", "degraded")


class HealthChecker:
    """
    Comprehensive health checking for Green/Purple agents.

    Supports:
    - Liveness probes: Quick checks to verify process is alive
    - Readiness probes: Full checks to verify service can handle requests
    - Custom health checks: Register additional checks as needed

    Usage:
        checker = HealthChecker(agent=my_agent)
        checker.register_check("custom", my_check_function)

        # Liveness (quick)
        status = await checker.check_liveness()

        # Readiness (thorough)
        status = await checker.check_readiness()
    """

    def __init__(
        self,
        agent: Any = None,
        executor: Any = None,
        version: str = "1.0.0",
    ):
        """
        Initialize health checker.

        Args:
            agent: The agent instance (Green or Purple)
            executor: SQL executor instance (for Green Agent)
            version: Service version to include in health response
        """
        self.agent = agent
        self.executor = executor
        self.version = version
        self._custom_checks: Dict[str, Callable] = {}

    def register_check(self, name: str, check_fn: Callable) -> None:
        """
        Register a custom health check.

        Args:
            name: Unique name for the check
            check_fn: Async function that returns (status, message, details)
        """
        self._custom_checks[name] = check_fn

    async def check_liveness(self) -> HealthStatus:
        """
        Quick liveness check - is the process alive?

        This should be fast (<100ms) and only verify the process is running.
        Used by Kubernetes liveness probes.

        Returns:
            HealthStatus with basic process check
        """
        return HealthStatus(
            status="healthy",
            timestamp=datetime.utcnow().isoformat() + "Z",
            version=self.version,
            checks=[
                HealthCheck(
                    name="process",
                    status="pass",
                    duration_ms=0.1,
                    message="Process is running",
                )
            ],
        )

    async def check_readiness(self) -> HealthStatus:
        """
        Full readiness check - is the service ready to handle requests?

        Checks:
        - Tasks loaded (Green Agent)
        - Database accessible (Green Agent)
        - LLM client configured (Purple Agent)
        - Custom registered checks

        Returns:
            HealthStatus with all check results
        """
        checks = []
        all_pass = True
        has_warnings = False

        # Check 1: Tasks loaded (Green Agent)
        if self.agent and hasattr(self.agent, "tasks"):
            check = await self._check_tasks_loaded()
            checks.append(check)
            if check.status == "fail":
                all_pass = False
            elif check.status == "warn":
                has_warnings = True

        # Check 2: Database connection (Green Agent)
        if self.executor:
            check = await self._check_database()
            checks.append(check)
            if check.status == "fail":
                all_pass = False
            elif check.status == "warn":
                has_warnings = True

        # Check 3: LLM client (Purple Agent)
        if self.agent and hasattr(self.agent, "llm"):
            check = await self._check_llm_client()
            checks.append(check)
            if check.status == "fail":
                all_pass = False
            elif check.status == "warn":
                has_warnings = True

        # Run custom checks
        for name, check_fn in self._custom_checks.items():
            try:
                check = await self._run_custom_check(name, check_fn)
                checks.append(check)
                if check.status == "fail":
                    all_pass = False
                elif check.status == "warn":
                    has_warnings = True
            except Exception as e:
                checks.append(
                    HealthCheck(
                        name=name,
                        status="fail",
                        duration_ms=0,
                        message=f"Check failed: {str(e)}",
                    )
                )
                all_pass = False

        # Determine overall status
        if all_pass and not has_warnings:
            status = "healthy"
        elif all_pass and has_warnings:
            status = "degraded"
        else:
            status = "unhealthy"

        return HealthStatus(
            status=status,
            timestamp=datetime.utcnow().isoformat() + "Z",
            version=self.version,
            checks=checks,
        )

    async def _check_tasks_loaded(self) -> HealthCheck:
        """Check if tasks are loaded (Green Agent)."""
        start = time.monotonic()
        try:
            tasks = getattr(self.agent, "tasks", [])
            task_count = len(tasks)
            duration_ms = (time.monotonic() - start) * 1000

            if task_count > 0:
                return HealthCheck(
                    name="tasks_loaded",
                    status="pass",
                    duration_ms=duration_ms,
                    message=f"{task_count} tasks loaded",
                    details={"task_count": task_count},
                )
            else:
                return HealthCheck(
                    name="tasks_loaded",
                    status="warn",
                    duration_ms=duration_ms,
                    message="No tasks loaded",
                    details={"task_count": 0},
                )
        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000
            return HealthCheck(
                name="tasks_loaded",
                status="fail",
                duration_ms=duration_ms,
                message=f"Failed to check tasks: {str(e)}",
            )

    async def _check_database(self) -> HealthCheck:
        """Check database connection (Green Agent)."""
        start = time.monotonic()
        try:
            # Execute a simple query to verify connection
            if hasattr(self.executor, "adapter"):
                self.executor.adapter.execute("SELECT 1")
            elif hasattr(self.executor, "execute"):
                self.executor.execute("SELECT 1")
            else:
                raise AttributeError("No execute method found on executor")

            duration_ms = (time.monotonic() - start) * 1000
            return HealthCheck(
                name="database",
                status="pass",
                duration_ms=duration_ms,
                message="Database accessible",
            )
        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000
            return HealthCheck(
                name="database",
                status="fail",
                duration_ms=duration_ms,
                message=f"Database error: {str(e)}",
            )

    async def _check_llm_client(self) -> HealthCheck:
        """Check LLM client configuration (Purple Agent)."""
        start = time.monotonic()
        try:
            llm = getattr(self.agent, "llm", None)
            if llm is None:
                raise ValueError("LLM client not configured")

            # Check if API key is set (without exposing it)
            provider = getattr(llm, "provider", "unknown")
            api_key = getattr(llm, "api_key", None)

            duration_ms = (time.monotonic() - start) * 1000

            if api_key:
                return HealthCheck(
                    name="llm_client",
                    status="pass",
                    duration_ms=duration_ms,
                    message=f"LLM client configured ({provider})",
                    details={"provider": provider, "api_key_set": True},
                )
            else:
                return HealthCheck(
                    name="llm_client",
                    status="warn",
                    duration_ms=duration_ms,
                    message=f"LLM client configured but no API key ({provider})",
                    details={"provider": provider, "api_key_set": False},
                )
        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000
            return HealthCheck(
                name="llm_client",
                status="fail",
                duration_ms=duration_ms,
                message=f"LLM client error: {str(e)}",
            )

    async def _run_custom_check(
        self, name: str, check_fn: Callable
    ) -> HealthCheck:
        """Run a custom health check."""
        start = time.monotonic()
        try:
            result = await check_fn()
            duration_ms = (time.monotonic() - start) * 1000

            if isinstance(result, tuple):
                status, message = result[0], result[1]
                details = result[2] if len(result) > 2 else None
            elif isinstance(result, dict):
                status = result.get("status", "pass")
                message = result.get("message", "")
                details = result.get("details")
            else:
                status = "pass" if result else "fail"
                message = str(result)
                details = None

            return HealthCheck(
                name=name,
                status=status,
                duration_ms=duration_ms,
                message=message,
                details=details,
            )
        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000
            return HealthCheck(
                name=name,
                status="fail",
                duration_ms=duration_ms,
                message=f"Check failed: {str(e)}",
            )
