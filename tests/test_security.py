import hashlib
import hmac

from app.security import verify_signature


def sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_firma_valida():
    body = b'{"a": 1}'
    assert verify_signature("s3cret", body, sign("s3cret", body))


def test_firma_con_secreto_incorrecto():
    body = b'{"a": 1}'
    assert not verify_signature("s3cret", body, sign("otro", body))


def test_sin_cabecera():
    assert not verify_signature("s3cret", b"x", None)


def test_formato_raro():
    assert not verify_signature("s3cret", b"x", "md5=abc")
