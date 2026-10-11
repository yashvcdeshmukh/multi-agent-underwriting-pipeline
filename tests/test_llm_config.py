from underwriting.llm import DEFAULT_OLLAMA_MODEL, ScriptedModel, get_llm_client


def test_default_model_is_qwen3_8b():
    assert DEFAULT_OLLAMA_MODEL == "qwen3:8b"


def test_scripted_model_estimates_tokens_from_length():
    model = ScriptedModel('{"ok": true}')
    completion = model.complete("system", "user")
    assert (completion.text, completion.input_tokens, completion.output_tokens) == (
        '{"ok": true}',
        len("systemuser") // 4,
        len('{"ok": true}') // 4,
    )


def test_client_points_at_ollama_openai_compat(monkeypatch):
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    get_llm_client.cache_clear()
    client = get_llm_client()
    assert str(client.base_url).rstrip("/").endswith("/v1")
