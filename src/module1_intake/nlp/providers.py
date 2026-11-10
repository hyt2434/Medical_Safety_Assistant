"""Compatibility import for :mod:`module1_intake.nlp.understanding.providers`."""
import sys as _sys
from .understanding import providers as _implementation

_sys.modules[__name__] = _implementation
