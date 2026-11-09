import hashlib
import hmac


def verify_signature(secret: str, body: bytes, signature_header: str | None) -> bool:
    """Comprueba que el webhook viene de GitHub.

    GitHub firma el cuerpo de cada aviso con HMAC-SHA256 usando el secreto que
    configuras en el webhook y lo manda en la cabecera X-Hub-Signature-256
    con el formato "sha256=<hex>".
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    # compare_digest evita ataques de temporización
    return hmac.compare_digest(expected, signature_header)
