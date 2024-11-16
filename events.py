from dataclasses import dataclass
from typing import Optional

@dataclass
class AssistantEvent:
    type: str
    data: Optional[str] = None
