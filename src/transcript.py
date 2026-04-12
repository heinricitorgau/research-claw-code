from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TranscriptStore:
    entries: list[str] = field(default_factory=list)
    flushed: bool = False

    def append(self, entry: str) -> None:
        self.entries.append(entry)
        self.flushed = False

    def compact(self, keep_last: int = 10) -> None:
        if len(self.entries) > keep_last:
            # Guard against the Python "-0 == 0" trap: `entries[-0:]` is
            # identical to `entries[0:]` and would retain *all* entries
            # instead of clearing them when keep_last is 0.
            if keep_last == 0:
                self.entries.clear()
            else:
                self.entries[:] = self.entries[-keep_last:]

    def replay(self) -> tuple[str, ...]:
        return tuple(self.entries)

    def flush(self) -> None:
        self.flushed = True
