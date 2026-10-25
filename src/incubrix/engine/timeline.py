import json
import hashlib
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator

class Caption(BaseModel):
    id: str
    text: str
    start_time: float
    end_time: float
    color: str = "#ffffff"
    font_size: int = 24
    position: str = "bottom"  # bottom, top, center

class AudioEffect(BaseModel):
    effect_type: str  # mute, bleep, volume
    start_time: float
    end_time: float
    params: Dict[str, Any] = Field(default_factory=dict)

class Segment(BaseModel):
    id: str
    asset_id: str
    source_start: float
    source_end: float
    speed: float = 1.0
    captions: List[Caption] = Field(default_factory=list)
    audio_effects: List[AudioEffect] = Field(default_factory=list)
    label: Optional[str] = None

    @property
    def duration(self) -> float:
        return (self.source_end - self.source_start) / self.speed

class Timeline(BaseModel):
    asset_id: str
    segments: List[Segment] = Field(default_factory=list)
    total_duration: float = 0.0

    @model_validator(mode="after")
    def compute_total_duration(self) -> "Timeline":
        self.total_duration = round(sum(s.duration for s in self.segments), 4)
        return self

    def canonical_dict(self) -> Dict[str, Any]:
        """Produce a canonical, deterministically sorted dictionary representation."""
        return {
            "asset_id": self.asset_id,
            "total_duration": round(self.total_duration, 4),
            "segments": [
                {
                    "id": s.id,
                    "asset_id": s.asset_id,
                    "source_start": round(s.source_start, 4),
                    "source_end": round(s.source_end, 4),
                    "speed": round(s.speed, 4),
                    "duration": round(s.duration, 4),
                    "label": s.label,
                    "captions": [
                        {
                            "id": c.id,
                            "text": c.text,
                            "start_time": round(c.start_time, 4),
                            "end_time": round(c.end_time, 4),
                            "color": c.color,
                            "font_size": c.font_size,
                            "position": c.position,
                        }
                        for c in sorted(s.captions, key=lambda x: (x.start_time, x.id))
                    ],
                    "audio_effects": [
                        {
                            "effect_type": a.effect_type,
                            "start_time": round(a.start_time, 4),
                            "end_time": round(a.end_time, 4),
                            "params": a.params,
                        }
                        for a in sorted(s.audio_effects, key=lambda x: (x.start_time, x.effect_type))
                    ],
                }
                for s in self.segments
            ]
        }

    def canonical_json(self) -> str:
        return json.dumps(self.canonical_dict(), sort_keys=True)

    def canonical_hash(self) -> str:
        canonical_bytes = self.canonical_json().encode("utf-8")
        return hashlib.sha256(canonical_bytes).hexdigest()
