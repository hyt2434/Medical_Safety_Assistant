"""Expected domain-state conflicts, distinct from programming/configuration errors."""


class DomainConflict(ValueError):
    """The requested domain action conflicts with the current record state."""
