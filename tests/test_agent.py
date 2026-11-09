from types import SimpleNamespace as NS

from app.agent import run_review


def text(t):
    return NS(type="text", text=t)


def tool_use(id, name, **inp):
    return NS(type="tool_use", id=id, name=name, input=inp)


def resp(stop, *blocks):
    return NS(stop_reason=stop, content=list(blocks))


class FakeLLM:
    """Devuelve respuestas guionizadas, así el test no necesita API ni red."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        # copia de la lista: el bucle sigue añadiendo mensajes después de la llamada
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.script.pop(0)


class FakeGitHub:
    def __init__(self, fail_search=False):
        self.fail_search = fail_search

    def get_pr_diff(self, repo, n):
        return "+def f(): pass"

    def get_pr_head_sha(self, repo, n):
        return "abc123"

    def search_code(self, repo, query):
        if self.fail_search:
            raise RuntimeError("rate limit")
        return "checkout.py"

    def read_file(self, repo, path, ref):
        return "contenido"


def test_usa_tool_y_devuelve_revision():
    llm = FakeLLM(
        [
            resp("tool_use", tool_use("t1", "search_code", query="f")),
            resp("end_turn", text("Sin problemas.")),
        ]
    )
    out = run_review(llm, FakeGitHub(), "org/repo", 1)
    assert out == "Sin problemas."
    assert len(llm.calls) == 2


def test_error_de_tool_vuelve_al_modelo():
    llm = FakeLLM(
        [
            resp("tool_use", tool_use("t1", "search_code", query="f")),
            resp("end_turn", text("Hecho.")),
        ]
    )
    out = run_review(llm, FakeGitHub(fail_search=True), "org/repo", 1)
    assert out == "Hecho."
    resultado = llm.calls[1]["messages"][-1]["content"][0]
    assert resultado["is_error"] is True
    assert "rate limit" in resultado["content"]


def test_limite_de_pasos():
    bucle = [resp("tool_use", tool_use(f"t{i}", "read_file", path="a.py")) for i in range(5)]
    llm = FakeLLM(bucle)
    out = run_review(llm, FakeGitHub(), "org/repo", 1, max_steps=3)
    assert "límite de pasos" in out
    assert len(llm.calls) == 3
