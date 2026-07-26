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
    header, payload, signature = token.split(".")
    tampered_signature = f"{'a' if signature[0] != 'a' else 'b'}{signature[1:]}"
    tampered_token = ".".join((header, payload, tampered_signature))

    assert decode_session_token(tampered_token) is None
    assert decode_session_token("not-a-token") is None
