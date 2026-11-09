"""Pure, dependency-free logic for text hygiene, conditional requirements and ISO date order."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Sequence


def check_text_values(values: Sequence[str | None], *, sensitive: bool = False) -> dict[str, Any]:
    present = [str(value) for value in values if value is not None]
    counts = Counter(present)
    groups = defaultdict(list)
    for value in counts:
        normalized = value.strip().casefold()
        if normalized:
            groups[normalized].append(value)
    collisions = [variants for variants in groups.values() if len(variants) > 1]
    samples = [] if sensitive else [
        {'variants': variants[:4], 'rows': sum(counts[value] for value in variants)}
        for variants in collisions[:5]]
    return {
        'rows': len(values), 'missing_values': len(values) - len(present),
        'blank_text_values': sum(not value.strip() for value in present),
        'outer_whitespace_values': sum(value != value.strip() for value in present),
        'normalized_collision_groups': len(collisions),
        'collision_rows': sum(sum(counts[value] for value in variants) for variants in collisions),
        'example_groups': samples,
        'note': 'Whitespace-only strings are separate from missing values. Collisions group distinct raw strings by strip + Unicode casefold. They may be intentional; no values are modified.',
    }


def check_conditional_values(condition: Sequence[Any], required: dict[str, Sequence[Any]],
                             equals: str) -> dict[str, Any]:
    if any(len(values) != len(condition) for values in required.values()):
        raise ValueError('Columns must have equal lengths.')
    matched = [index for index, value in enumerate(condition) if value is not None and str(value) == equals]
    missing_counts = {}
    affected = set()
    for column, values in required.items():
        missing = {index for index in matched if values[index] is None or
                   isinstance(values[index], str) and not values[index].strip()}
        missing_counts[column] = len(missing)
        affected.update(missing)
    return {'rows': len(condition), 'matched_rows': len(matched),
            'affected_rows': len(affected), 'missing_by_column': missing_counts,
            'missing_condition_rows': sum(value is None for value in condition),
            'note': 'Condition equality is exact and case-sensitive. Required values are missing when null, empty or whitespace-only. A row missing several required fields is counted once in affected_rows. No source values are exposed.'}


def _iso_date(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def check_date_pairs(starts: Sequence[Any], ends: Sequence[Any], *, allow_equal: bool = True) -> dict[str, Any]:
    if len(starts) != len(ends):
        raise ValueError('Columns must have equal lengths.')
    missing = invalid = earlier = equal = later = 0
    for start, end in zip(starts, ends):
        if start is None or end is None or isinstance(start, str) and not start.strip() or isinstance(end, str) and not end.strip():
            missing += 1
            continue
        left, right = _iso_date(start), _iso_date(end)
        if left is None or right is None:
            invalid += 1
        elif left < right:
            earlier += 1
        elif left == right:
            equal += 1
        else:
            later += 1
    compared = earlier + equal + later
    return {'rows': len(starts), 'compared_rows': compared, 'missing_date_pair_rows': missing,
            'invalid_date_pair_rows': invalid, 'start_before_end_rows': earlier,
            'equal_date_rows': equal, 'start_after_end_rows': later,
            'allow_equal': allow_equal, 'violation_rows': later + (0 if allow_equal else equal),
            'note': 'ISO-8601 dates/timestamps only. Naive timestamps are treated as UTC; offset timestamps are normalized to UTC. Missing and invalid pairs are excluded from ordering. No date values are returned.'}
