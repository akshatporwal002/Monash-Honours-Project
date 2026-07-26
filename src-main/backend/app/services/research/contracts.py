from typing import Protocol

from app.schemas.feedback import FeedbackContext
from app.services.research.cases import ResearchCaseSeed


class ResearchEligibilityPolicy(Protocol):
    async def is_eligible(self, context: FeedbackContext) -> bool: ...


class ResearchJobDispatcher(Protocol):
    def schedule_baseline(self, case_id: str) -> None: ...


class ResearchCaseRepository(Protocol):
    def create_pair(self, seed: ResearchCaseSeed) -> None: ...


class ResearchPseudonymizer(Protocol):
    def pseudonymize(self, namespace: str, reference: str) -> str: ...


class DisabledResearchEligibilityPolicy:
    async def is_eligible(self, context: FeedbackContext) -> bool:
        del context
        return False
