"""Compatibility import for :mod:`module1_intake.nlp.qa_pipeline.pipeline`."""
import sys as _sys
from .qa_pipeline import pipeline as _implementation

_sys.modules[__name__] = _implementation
