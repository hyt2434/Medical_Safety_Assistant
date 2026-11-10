"""Compatibility import for :mod:`module1_intake.nlp.qa_pipeline.structured`."""
import sys as _sys
from .qa_pipeline import structured as _implementation

_sys.modules[__name__] = _implementation
