"""Compatibility import for :mod:`module1_intake.nlp.integration.handoff`."""
import sys as _sys
from .integration import handoff as _implementation

_sys.modules[__name__] = _implementation
