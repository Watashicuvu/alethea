from pydantic import BaseModel, Field

# В начале synthesizer.py (где остальные модели)
class IdentityVerdict(BaseModel):
    is_same: bool = Field(description="True ONLY if Entity A and Entity B are undoubtedly the same thing/person.")
    confidence: float = Field(description="0.0 to 1.0 confidence score.")
    reason: str = Field(description="Concise explanation citing conflicting or matching traits.")

