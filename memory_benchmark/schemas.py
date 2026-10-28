from dataclasses import dataclass, field, asdict
@dataclass(frozen=True)
class Evidence:
    id: str
    text: str
    source_ids: tuple[str, ...] = ()
    timestamp: str | None = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id or not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("Evidence requires a nonempty ID and text")

    def to_wire(self):
        return asdict(self)

    @classmethod
    def from_wire(cls, row):
        return cls(row["id"], row["text"], tuple(row.get("source_ids", [])),
                   row.get("timestamp"), row.get("metadata", {}))
