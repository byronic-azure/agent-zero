"""
Persona Manager - First-class execution primitive for Agent Zero

PersonaMode determines:
- Access control and permissions
- Metrics visibility and aggregation level
- Resource allocation and scaling behavior
- UI presentation and narrative context
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional, TypedDict
from functools import wraps
import threading
import logging

logger = logging.getLogger(__name__)


class PersonaMode(str, Enum):
    """Persona execution modes"""
    STEALTH = "STEALTH"
    AUTHORITY = "AUTHORITY"
    INTERFACE = "INTERFACE"
    LAB = "LAB"


class AccessLevel(str, Enum):
    """Access levels for persona configurations"""
    ADMIN = "admin"
    OPERATOR = "operator"
    USER = "user"
    READONLY = "readonly"


@dataclass
class MetricsAccess:
    """Defines which metrics are accessible for a persona"""
    aggregate_metrics: bool = False
    sla_metrics: bool = False
    narrative_metrics: bool = False
    raw_metrics: bool = False


@dataclass
class ResourceQuota:
    """Resource limits for a persona"""
    max_concurrent_requests: int = 10
    requests_per_minute: int = 120
    max_memory_mb: int = 1024
    max_cpu_percent: int = 50


@dataclass
class PersonaConfig:
    """Complete configuration for a persona mode"""
    mode: PersonaMode
    display_name: str
    description: str
    access_level: AccessLevel
    metrics_access: MetricsAccess
    resource_quota: ResourceQuota
    allowed_endpoints: list[str] = field(default_factory=list)
    denied_endpoints: list[str] = field(default_factory=list)


@dataclass
class PersonaContext:
    """Runtime context for the current persona"""
    mode: PersonaMode
    user_id: Optional[str] = None
    session_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


# Default persona configurations
PERSONA_CONFIGS: dict[PersonaMode, PersonaConfig] = {
    PersonaMode.STEALTH: PersonaConfig(
        mode=PersonaMode.STEALTH,
        display_name="Stealth Mode",
        description="Minimal footprint, aggregate-only metrics, covert operation context",
        access_level=AccessLevel.ADMIN,
        metrics_access=MetricsAccess(
            aggregate_metrics=True,
            sla_metrics=False,
            narrative_metrics=False,
            raw_metrics=False,
        ),
        resource_quota=ResourceQuota(
            max_concurrent_requests=5,
            requests_per_minute=60,
            max_memory_mb=512,
            max_cpu_percent=25,
        ),
        allowed_endpoints=["*"],
        denied_endpoints=[],
    ),
    PersonaMode.AUTHORITY: PersonaConfig(
        mode=PersonaMode.AUTHORITY,
        display_name="Authority Mode",
        description="Full administrative access, SLA-focused metrics, operational command context",
        access_level=AccessLevel.ADMIN,
        metrics_access=MetricsAccess(
            aggregate_metrics=True,
            sla_metrics=True,
            narrative_metrics=True,
            raw_metrics=True,
        ),
        resource_quota=ResourceQuota(
            max_concurrent_requests=20,
            requests_per_minute=300,
            max_memory_mb=2048,
            max_cpu_percent=80,
        ),
        allowed_endpoints=["*"],
        denied_endpoints=[],
    ),
    PersonaMode.INTERFACE: PersonaConfig(
        mode=PersonaMode.INTERFACE,
        display_name="Interface Mode",
        description="User-facing presentation, narrative metrics, interactive context",
        access_level=AccessLevel.USER,
        metrics_access=MetricsAccess(
            aggregate_metrics=False,
            sla_metrics=False,
            narrative_metrics=True,
            raw_metrics=False,
        ),
        resource_quota=ResourceQuota(
            max_concurrent_requests=10,
            requests_per_minute=120,
            max_memory_mb=1024,
            max_cpu_percent=50,
        ),
        allowed_endpoints=["/api/message", "/api/chat", "/api/status", "/health", "/ready"],
        denied_endpoints=["/api/settings", "/api/backup", "/api/scheduler"],
    ),
    PersonaMode.LAB: PersonaConfig(
        mode=PersonaMode.LAB,
        display_name="Lab Mode",
        description="Experimental access, raw metrics, development and testing context",
        access_level=AccessLevel.OPERATOR,
        metrics_access=MetricsAccess(
            aggregate_metrics=True,
            sla_metrics=True,
            narrative_metrics=True,
            raw_metrics=True,
        ),
        resource_quota=ResourceQuota(
            max_concurrent_requests=50,
            requests_per_minute=1000,
            max_memory_mb=4096,
            max_cpu_percent=100,
        ),
        allowed_endpoints=["*"],
        denied_endpoints=[],
    ),
}


class PersonaModeEmitter:
    """Event emitter for persona mode changes"""

    def __init__(self):
        self._handlers: list[Callable[[PersonaMode, Optional[PersonaMode], PersonaContext], None]] = []
        self._current_mode: Optional[PersonaMode] = None
        self._lock = threading.Lock()

    def on_mode_change(
        self, handler: Callable[[PersonaMode, Optional[PersonaMode], PersonaContext], None]
    ) -> Callable[[], None]:
        """Register a handler for mode change events. Returns unsubscribe function."""
        with self._lock:
            self._handlers.append(handler)

        def unsubscribe():
            with self._lock:
                if handler in self._handlers:
                    self._handlers.remove(handler)

        return unsubscribe

    def set_mode(self, mode: PersonaMode, context: PersonaContext) -> None:
        """Set the current persona mode and notify handlers"""
        with self._lock:
            previous_mode = self._current_mode
            self._current_mode = mode
            handlers = self._handlers.copy()

        for handler in handlers:
            try:
                handler(mode, previous_mode, context)
            except Exception as e:
                logger.error(f"Error in persona mode change handler: {e}")

    def get_mode(self) -> Optional[PersonaMode]:
        """Get the current persona mode"""
        return self._current_mode


# Global emitter instance
persona_mode_emitter = PersonaModeEmitter()


def is_valid_persona_mode(value: Any) -> bool:
    """Check if a value is a valid PersonaMode"""
    if isinstance(value, PersonaMode):
        return True
    if isinstance(value, str):
        return value in [m.value for m in PersonaMode]
    return False


def parse_persona_mode(value: Any, default: PersonaMode = PersonaMode.AUTHORITY) -> PersonaMode:
    """Parse a value into a PersonaMode, returning default if invalid"""
    if isinstance(value, PersonaMode):
        return value
    if isinstance(value, str):
        try:
            return PersonaMode(value.upper())
        except ValueError:
            return default
    return default


def match_endpoint(path: str, pattern: str) -> bool:
    """Simple endpoint pattern matching with wildcard support"""
    if pattern == "*":
        return True
    if pattern.endswith("*"):
        return path.startswith(pattern[:-1])
    return path == pattern


def check_endpoint_access(path: str, config: PersonaConfig) -> tuple[bool, str]:
    """
    Check if an endpoint is accessible for a persona config.
    Returns (allowed, reason) tuple.
    """
    # Check denied endpoints first
    for pattern in config.denied_endpoints:
        if match_endpoint(path, pattern):
            return False, f"Endpoint denied for persona {config.mode.value}"

    # Check allowed endpoints
    for pattern in config.allowed_endpoints:
        if match_endpoint(path, pattern):
            return True, ""

    return False, f"Endpoint not allowed for persona {config.mode.value}"


def get_persona_config(mode: PersonaMode) -> PersonaConfig:
    """Get the configuration for a persona mode"""
    return PERSONA_CONFIGS.get(mode, PERSONA_CONFIGS[PersonaMode.AUTHORITY])


def create_persona_context(
    mode: PersonaMode,
    user_id: Optional[str] = None,
    session_id: str = "",
    **metadata: Any,
) -> PersonaContext:
    """Create a new PersonaContext instance"""
    return PersonaContext(
        mode=mode,
        user_id=user_id,
        session_id=session_id or f"sess_{int(datetime.now().timestamp())}",
        timestamp=datetime.now(),
        metadata=metadata,
    )


# Flask integration
def persona_gate_middleware():
    """
    Flask middleware for persona gating.
    Call this to get a middleware function that extracts persona from headers.
    """
    from flask import request, g

    def before_request():
        header_value = request.headers.get("X-Persona-Mode", "AUTHORITY")
        persona = parse_persona_mode(header_value)

        g.persona = persona
        g.persona_config = get_persona_config(persona)
        g.persona_context = create_persona_context(
            mode=persona,
            user_id=getattr(g, "user_id", None),
            session_id=request.cookies.get("session_id", ""),
        )

        # Emit mode change event
        persona_mode_emitter.set_mode(persona, g.persona_context)

    return before_request


def require_persona(*allowed_modes: PersonaMode):
    """
    Decorator factory for endpoint-level persona access control.

    Usage:
        @app.route('/admin')
        @require_persona(PersonaMode.AUTHORITY, PersonaMode.STEALTH)
        def admin_endpoint():
            ...
    """

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            from flask import g, jsonify

            current_mode = getattr(g, "persona", PersonaMode.AUTHORITY)

            if current_mode not in allowed_modes:
                return jsonify({
                    "error": "Persona access denied",
                    "message": f"Endpoint requires persona: {' | '.join(m.value for m in allowed_modes)}",
                    "current_persona": current_mode.value,
                }), 403

            return f(*args, **kwargs)

        return wrapper

    return decorator


def enforce_persona_access():
    """
    Decorator for enforcing endpoint access based on persona config.
    Uses the endpoint path and persona config to determine access.
    """

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            from flask import request, g, jsonify

            config = getattr(g, "persona_config", get_persona_config(PersonaMode.AUTHORITY))
            path = request.path

            allowed, reason = check_endpoint_access(path, config)
            if not allowed:
                return jsonify({
                    "error": reason,
                    "persona": config.mode.value,
                    "endpoint": path,
                }), 403

            return f(*args, **kwargs)

        return wrapper

    return decorator


# Metrics types
class AggregateMetrics(TypedDict):
    type: str  # "aggregate"
    total_requests: int
    average_latency_ms: float
    error_rate: float
    timestamp: str


class SLAMetrics(TypedDict):
    type: str  # "sla"
    uptime: float
    p99_latency_ms: float
    p95_latency_ms: float
    sla_compliance: float
    alerts_active: int
    timestamp: str


class NarrativeMetrics(TypedDict):
    type: str  # "narrative"
    summary: str
    health_status: str  # "healthy" | "degraded" | "critical"
    user_impact: str
    recommendations: list[str]
    timestamp: str


class RawMetrics(TypedDict):
    type: str  # "raw"
    requests: list[dict]
    system_metrics: list[dict]
    timestamp: str


def get_metrics_for_persona(persona: PersonaMode) -> dict:
    """
    Get the appropriate metrics for a persona mode.
    This is a placeholder - implement actual metrics collection.
    """
    from datetime import datetime

    timestamp = datetime.now().isoformat()

    if persona == PersonaMode.STEALTH:
        return {
            "type": "aggregate",
            "total_requests": 0,
            "average_latency_ms": 0.0,
            "error_rate": 0.0,
            "timestamp": timestamp,
        }
    elif persona == PersonaMode.AUTHORITY:
        return {
            "type": "sla",
            "uptime": 99.9,
            "p99_latency_ms": 100.0,
            "p95_latency_ms": 50.0,
            "sla_compliance": 99.5,
            "alerts_active": 0,
            "timestamp": timestamp,
        }
    elif persona == PersonaMode.INTERFACE:
        return {
            "type": "narrative",
            "summary": "System operating normally",
            "health_status": "healthy",
            "user_impact": "No impact",
            "recommendations": [],
            "timestamp": timestamp,
        }
    elif persona == PersonaMode.LAB:
        return {
            "type": "raw",
            "requests": [],
            "system_metrics": [],
            "timestamp": timestamp,
        }

    return {"type": "unknown", "timestamp": timestamp}
