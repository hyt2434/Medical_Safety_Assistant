"""Application FSM using the existing Core V4 state vocabulary and allowed edges."""
from enum import Enum


class State(str, Enum):
    COLLECTING = "COLLECTING"
    CLARIFYING = "CLARIFYING"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    SUSPENDED = "SUSPENDED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


def check_transition(current: str, target: str) -> None:
    old, new = State(current), State(target)
    if old in {State.COMPLETED, State.CANCELLED, State.FAILED}:
        raise ValueError("Terminal workflow cannot transition")
    permitted = {old, State.CANCELLED, State.FAILED, State.SUSPENDED}
    if old in {State.COLLECTING, State.CLARIFYING, State.SUSPENDED}:
        permitted |= {State.COLLECTING, State.CLARIFYING, State.AWAITING_CONFIRMATION}
    if old == State.AWAITING_CONFIRMATION:
        permitted |= {State.COLLECTING, State.CLARIFYING, State.COMPLETED}
    if new not in permitted:
        raise ValueError(f"Invalid workflow edge: {current} -> {target}")
