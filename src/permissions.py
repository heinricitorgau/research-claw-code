from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ToolPermissionContext:
    deny_names: frozenset[str] = field(default_factory=frozenset)
    deny_prefixes: tuple[str, ...] = ()

    @classmethod
    def from_iterables(cls, deny_names: list[str] | None = None, deny_prefixes: list[str] | None = None) -> 'ToolPermissionContext':
        return cls(
            deny_names=frozenset(name.lower() for name in (deny_names or [])),
            # Filter out empty/whitespace-only prefixes: an empty prefix would
            # inadvertently match every tool name (str.startswith("") is always
            # True), silently blocking all tools.
            deny_prefixes=tuple(
                p for p in (prefix.lower() for prefix in (deny_prefixes or []))
                if p.strip()
            ),
        )

    def blocks(self, tool_name: str) -> bool:
        lowered = tool_name.lower()
        return lowered in self.deny_names or any(lowered.startswith(prefix) for prefix in self.deny_prefixes)
