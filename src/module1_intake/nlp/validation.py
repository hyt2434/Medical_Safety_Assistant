"""Compatibility import for :mod:`module1_intake.nlp.understanding.validation`."""
import sys as _sys
from .understanding import validation as _implementation

_sys.modules[__name__] = _implementation
