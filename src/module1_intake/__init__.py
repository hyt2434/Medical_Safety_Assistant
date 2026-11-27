"""Module 1 intake; public Voice/Manual API is loaded only when requested."""

__all__ = ['suggest_medication_names', 'transcribe_voice']


def __getattr__(name):
    if name in __all__:
        from . import api
        return getattr(api, name)
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
