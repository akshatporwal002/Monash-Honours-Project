from pathlib import Path

import pytest
from dotenv import dotenv_values
from sqlalchemy.orm import Session

from app.core.config import BUILTIN_OFFLINE_WORKER_ADAPTER_FACTORY, Settings
from app.models.lms import SystemSetting
from app.services import llm
from app.worker import build_offline_worker_adapters


def test_local_template_builds_offline_worker_without_provider_credentials(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    template = Path(__file__).resolve().parents[1] / ".env.example"
    values = dotenv_values(template)
    configured = Settings(
        _env_file=None,
        **{key.lower(): value for key, value in values.items()},
    )
    monkeypatch.setattr(llm, "settings", configured)

    assert configured.worker_adapter_factory == BUILTIN_OFFLINE_WORKER_ADAPTER_FACTORY
    assert configured.research_enabled is False
    assert llm.runtime_model_selection(db_session).local
    assert not configured.llm_api_key or not configured.llm_api_key.get_secret_value()
    assert callable(build_offline_worker_adapters(configured).feedback_pipeline_factory)

    # Existing administrator choices remain authoritative after a launcher restart.
    db_session.add_all(
        [
            SystemSetting(
                key="llm_provider", value="configured-provider", description="Test provider"
            ),
            SystemSetting(key="llm_model", value="configured-model", description="Test model"),
        ]
    )
    db_session.commit()
    selection = llm.runtime_model_selection(db_session)
    assert selection.provider == "configured-provider"
    assert selection.model == "configured-model"
