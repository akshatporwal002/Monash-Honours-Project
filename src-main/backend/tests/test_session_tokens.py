from datetime import timedelta

from app.core.session import create_session_token, decode_session_token


def test_session_token_round_trip() -> None:
    token = create_session_token(42)

    assert decode_session_token(token) == 42


def test_expired_session_token_is_rejected() -> None:
    token = create_session_token(42, expires_in=timedelta(seconds=-1))

    assert decode_session_token(token) is None


def test_tampered_and_malformed_session_tokens_are_rejected() -> None:
    token = create_session_token(42)
    tampered_token = f"{token[:-1]}{'a' if token[-1] != 'a' else 'b'}"

    assert decode_session_token(tampered_token) is None
    assert decode_session_token("not-a-token") is None
