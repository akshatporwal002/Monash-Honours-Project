"""Shared controlled errors for the instrument and study route families."""

from fastapi import HTTPException

from app.services.research.governance import GovernanceConflict, GovernanceDenied


def invoke(action):
    try:
        return action()
    except GovernanceDenied as error:
        raise HTTPException(403, str(error)) from None
    except GovernanceConflict as error:
        raise HTTPException(409, str(error)) from None
    except ValueError:
        raise HTTPException(422, "instrument_validation_failed") from None
