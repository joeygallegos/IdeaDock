from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.models import ItemType, Priority


ITEM_TYPE_LOOKUP = {item_type.value: item_type for item_type in ItemType}
PRIORITY_LOOKUP = {priority.value: priority for priority in Priority}


@dataclass
class QuickEntryResult:
    raw_input: str
    title: str
    epic_name: str | None = None
    epic_names: list[str] = field(default_factory=list)
    item_type: ItemType | None = None
    priority: Priority | None = None
    due_date: date | None = None
    entity_names: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def parse_quick_entry(raw_input: str) -> QuickEntryResult:
    tokens = raw_input.split()
    title_tokens: list[str] = []
    epic_names: list[str] = []
    item_type: ItemType | None = None
    priority: Priority | None = None
    due_date: date | None = None
    entity_names: list[str] = []
    warnings: list[str] = []

    for token in tokens:
        if token.startswith("#") and len(token) > 1:
            epic_name = clean_token_value(token[1:])
            if epic_name:
                epic_names.append(epic_name)
            continue

        if token.startswith("-") and len(token) > 1:
            parsed_type = ITEM_TYPE_LOOKUP.get(token[1:].lower())
            if parsed_type is not None:
                item_type = parsed_type
                continue

        if token.startswith("@") and len(token) > 1:
            entity_name = clean_token_value(token[1:])
            if entity_name:
                entity_names.append(entity_name)
                continue

        if token.startswith("!") and len(token) > 1:
            parsed_priority = PRIORITY_LOOKUP.get(token[1:].lower())
            if parsed_priority is not None:
                priority = parsed_priority
                continue

        if token.lower().startswith("due:"):
            raw_date = token[4:]
            try:
                due_date = date.fromisoformat(raw_date)
                continue
            except ValueError:
                warnings.append(f"Ignored invalid due date token: {token}")

        title_tokens.append(token)

    title = " ".join(title_tokens).strip()
    epic_names = dedupe(epic_names)

    return QuickEntryResult(
        raw_input=raw_input,
        title=title,
        epic_name=epic_names[0] if epic_names else None,
        epic_names=epic_names,
        item_type=item_type,
        priority=priority,
        due_date=due_date,
        entity_names=dedupe(entity_names),
        warnings=warnings,
    )


def clean_token_value(value: str) -> str:
    return " ".join(part for part in value.replace("_", " ").split()).strip()


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(value)
    return ordered
