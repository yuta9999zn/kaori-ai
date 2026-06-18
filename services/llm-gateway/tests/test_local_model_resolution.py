"""_resolve_local_model — the deployment's OLLAMA_MODEL is the source of truth
for the concrete local model (pilot 7b vs routing's logical 14b), falling back
to the requested model_id when the env is unset. No model name is hardcoded."""
import importlib

from llm_gateway import providers


def test_env_overrides_routing_tag(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:7b")
    assert providers._resolve_local_model("qwen2.5:14b") == "qwen2.5:7b"


def test_falls_back_to_model_id_when_env_unset(monkeypatch):
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    assert providers._resolve_local_model("qwen2.5:14b") == "qwen2.5:14b"


def test_empty_env_falls_back(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "")
    assert providers._resolve_local_model("qwen2.5:14b") == "qwen2.5:14b"
