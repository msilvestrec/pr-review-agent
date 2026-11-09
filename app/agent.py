import os

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")
MAX_STEPS = int(os.environ.get("AGENT_MAX_STEPS", "8"))
MAX_DIFF_CHARS = 30000

SYSTEM = (
    "Eres un revisor de código senior. Recibes el diff de una pull request. "
    "Usa las tools para entender el contexto (dónde se usa lo que cambia, "
    "archivos relacionados) antes de opinar. Solo señala problemas concretos "
    "y verificables: bugs, casos límite, falta de tests, riesgos de seguridad. "
    "No hagas comentarios de estilo. Si no encuentras problemas, dilo claramente. "
    "Responde en markdown, breve, citando archivo y línea cuando puedas."
)

TOOLS = [
    {
        "name": "search_code",
        "description": "Busca un texto (función, variable, clase) en el repositorio y devuelve las rutas de los archivos donde aparece.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Texto a buscar"}},
            "required": ["query"],
        },
    },
    {
        "name": "read_file",
        "description": "Lee el contenido de un archivo del repositorio en la versión de la PR.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Ruta del archivo"}},
            "required": ["path"],
        },
    },
]


def _run_tool(github, repo: str, sha: str, name: str, args: dict) -> str:
    if name == "search_code":
        return github.search_code(repo, args["query"])
    if name == "read_file":
        return github.read_file(repo, args["path"], sha)
    raise ValueError(f"Tool desconocida: {name}")


def run_review(llm, github, repo: str, pr_number: int, max_steps: int = MAX_STEPS) -> str:
    """Bucle del agente: Claude decide qué tool llamar hasta tener la revisión.

    Controles de seguridad: tope de pasos, errores de tools devueltos al modelo
    (no rompen el bucle) y diff recortado.
    """
    diff = github.get_pr_diff(repo, pr_number)[:MAX_DIFF_CHARS]
    sha = github.get_pr_head_sha(repo, pr_number)
    messages = [{"role": "user", "content": f"Revisa esta PR de {repo}:\n\n```diff\n{diff}\n```"}]

    for _ in range(max_steps):
        resp = llm.messages.create(
            model=MODEL, max_tokens=1500, system=SYSTEM, tools=TOOLS, messages=messages
        )
        messages.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason != "tool_use":
            return "".join(b.text for b in resp.content if b.type == "text")

        results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            try:
                out = _run_tool(github, repo, sha, block.name, block.input)
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": out})
            except Exception as e:  # el error vuelve al modelo para que se adapte
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"Error: {e}",
                        "is_error": True,
                    }
                )
        messages.append({"role": "user", "content": results})

    return "La revisión se cortó por llegar al límite de pasos. Revisa esta PR a mano."
