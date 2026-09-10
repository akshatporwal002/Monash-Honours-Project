"""Bounded operational policy, resolved at each new request or durable claim.

Missing rows use deployment defaults. Invalid persisted values stop dispatch;
they never widen a limit or change the fixed feedback-quality regeneration rule.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.models.lms import SystemSetting


class RuntimePolicyUnavailable(ValueError):
    """The persisted operational controls cannot safely be used."""


@dataclass(frozen=True, slots=True)
class RuntimePolicy:
    provider_timeout_seconds: int
    max_infrastructure_attempts: int

    def __post_init__(self):
        for value, maximum in (
            (self.provider_timeout_seconds, 60),
            (self.max_infrastructure_attempts, 3),
        ):
            if type(value) is not int or not 1 <= value <= maximum:
                raise RuntimePolicyUnavailable("Runtime timeout/retry settings are invalid.")


def read_runtime_policy(
    session: Session, configured_settings: Settings = settings
) -> RuntimePolicy:
    # Scalar columns avoid stale ORM objects in a reused session's identity map.
    values = dict(
        session.execute(
            select(SystemSetting.key, SystemSetting.value).where(
                SystemSetting.key.in_(("provider_timeout_seconds", "max_infrastructure_attempts"))
            )
        ).all()
    )
    return RuntimePolicy(
        provider_timeout_seconds=values.get(
            "provider_timeout_seconds", configured_settings.provider_timeout_seconds
        ),
        max_infrastructure_attempts=values.get(
            "max_infrastructure_attempts", configured_settings.max_infrastructure_attempts
        ),
    )
