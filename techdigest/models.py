from dataclasses import asdict, dataclass
from datetime import datetime


@dataclass
class Article:
    title: str
    url: str
    source: str
    category: str
    published: datetime | None
    summary: str

    def to_dict(self):
        d = asdict(self)
        d["published"] = self.published.isoformat() if self.published else None
        return d
