"""Vietnamese intake: language understanding, evidence validation and owner review."""
from .models import Module2Handoff
from .understanding.providers import MockProvider, OllamaProvider

__all__ = ["Chatbot", "Module2Handoff", "MockProvider", "OllamaProvider"]


def __getattr__(name):
    # Extraction-only use must not import the optional PostgreSQL workflow stack.
    if name == "Chatbot":
        from .dialogue_management.manager import Chatbot
        return Chatbot
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
