from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Protocol, Sequence


class SlotSelection(tuple):
    """Immutable ``(day_offset, slot_index)`` pair returned by allocation policies."""
    __slots__ = ()

    def __new__(cls, day_offset: int, slot_index: int) -> "SlotSelection":
        """Create a slot reference from a future day offset and in-day slot index."""
        return tuple.__new__(cls, (day_offset, slot_index))

    @property
    def day_offset(self) -> int:
        """Return the day offset of the selected future slot."""
        return self[0]

    @property
    def slot_index(self) -> int:
        """Return the within-day slot index of the selected future slot."""
        return self[1]


CalendarView = Sequence[Sequence[object | None]]


def _slot_start(day_offset: int, current_slot: int) -> int:
    """Return the first eligible slot index for a given day offset."""
    return current_slot + 1 if day_offset == 0 else 0


def _open_slots_after_current(day_slots: Sequence[object | None], day_offset: int, current_slot: int) -> int:
    """Count open slots that remain bookable from the current decision point."""
    slot_start = _slot_start(day_offset, current_slot)
    return sum(slot is None for slot in day_slots[slot_start:])


class AllocationPolicy(Protocol):
    """Interface for booking rules that choose an eligible future slot."""

    def select_slot(
        self,
        calendar: CalendarView,
        class_id: int,
        current_day: int,
        current_slot: int,
    ) -> Optional[SlotSelection]:
        """Return the slot to book, or None if no eligible slot is available."""


@dataclass(frozen=True)
class FCFSPolicy:
    """Books the earliest available slot strictly after the active slot."""

    def select_slot(
        self,
        calendar: CalendarView,
        class_id: int,
        current_day: int,
        current_slot: int,
    ) -> Optional[SlotSelection]:
        """Pick the earliest open slot strictly after the current slot."""
        for day_offset, day_slots in enumerate(calendar):
            slot_start = current_slot + 1 if day_offset == 0 else 0
            for slot_index in range(slot_start, len(day_slots)):
                if day_slots[slot_index] is None:
                    return SlotSelection(day_offset, slot_index)
        return None


@dataclass(frozen=True)
class LatestAvailablePolicy:
    """Books the latest available slot within the rolling horizon."""

    def select_slot(
        self,
        calendar: CalendarView,
        class_id: int,
        current_day: int,
        current_slot: int,
    ) -> Optional[SlotSelection]:
        """Pick the latest open slot that is still eligible for booking."""
        for day_offset in range(len(calendar) - 1, -1, -1):
            day_slots = calendar[day_offset]
            slot_stop = current_slot + 1 if day_offset == 0 else len(day_slots)
            for slot_index in range(slot_stop - 1, -1, -1):
                if day_offset == 0 and slot_index <= current_slot:
                    continue
                if day_slots[slot_index] is None:
                    return SlotSelection(day_offset, slot_index)
        return None


@dataclass(frozen=True)
class ReservedCapacityPolicy:
    """
    Strictly reserves a per-day number of future slots for each class.

    A class-i patient can book a day only if, after the booking, at least the
    sum of the other classes' reserved counts would remain open on that day.
    This implements a simple reservation-capacity rule without hard-coding
    particular slot indices as "owned" by a class.
    """

    reserved_slots_by_class: Mapping[int, int]

    def __post_init__(self) -> None:
        if any(reserved_slots < 0 for reserved_slots in self.reserved_slots_by_class.values()):
            raise ValueError("reserved slot counts must be non-negative")

    @classmethod
    def from_shares(
        cls,
        *,
        slots_per_day: int,
        reserved_share_by_class: Mapping[int, float],
    ) -> "ReservedCapacityPolicy":
        """Build a reservation rule from per-class daily slot shares."""
        if slots_per_day <= 0:
            raise ValueError("slots_per_day must be positive")
        reserved_slots_by_class = {}
        for class_id, share in reserved_share_by_class.items():
            if not 0.0 <= share <= 1.0:
                raise ValueError("reserved shares must lie in [0, 1]")
            reserved_slots_by_class[class_id] = int(round(slots_per_day * share))
        return cls(reserved_slots_by_class=reserved_slots_by_class)

    def select_slot(
        self,
        calendar: CalendarView,
        class_id: int,
        current_day: int,
        current_slot: int,
    ) -> Optional[SlotSelection]:
        """Pick the earliest slot that preserves other classes' daily reservations."""
        for day_offset, day_slots in enumerate(calendar):
            open_slots = _open_slots_after_current(day_slots, day_offset, current_slot)
            reserved_for_other_classes = sum(
                reserved_slots
                for other_class_id, reserved_slots in self.reserved_slots_by_class.items()
                if other_class_id != class_id
            )
            if open_slots <= reserved_for_other_classes:
                continue

            slot_start = _slot_start(day_offset, current_slot)
            for slot_index in range(slot_start, len(day_slots)):
                if day_slots[slot_index] is None:
                    return SlotSelection(day_offset, slot_index)
        return None


@dataclass(frozen=True)
class ClassWindowPolicy:
    """Books the earliest open slot subject to a class-specific maximum day offset."""

    max_delay_by_class: Mapping[int, int]

    def __post_init__(self) -> None:
        if any(max_delay < 0 for max_delay in self.max_delay_by_class.values()):
            raise ValueError("maximum booking delays must be non-negative")

    def select_slot(
        self,
        calendar: CalendarView,
        class_id: int,
        current_day: int,
        current_slot: int,
    ) -> Optional[SlotSelection]:
        """Pick the earliest open slot that respects the class-specific delay cap."""
        max_delay = self.max_delay_by_class.get(class_id, len(calendar) - 1)
        capped_max_delay = min(max_delay, len(calendar) - 1)
        for day_offset, day_slots in enumerate(calendar):
            if day_offset > capped_max_delay:
                break
            slot_start = _slot_start(day_offset, current_slot)
            for slot_index in range(slot_start, len(day_slots)):
                if day_slots[slot_index] is None:
                    return SlotSelection(day_offset, slot_index)
        return None
