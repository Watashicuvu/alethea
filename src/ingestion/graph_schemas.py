from enum import Enum
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


# === 0. SEMANTIC SPLITTER ===

# class SceneBoundary(BaseModel):
#     """Маркер начала новой сцены внутри текста."""
#     start_snippet: str = Field(description="The exact first 5-10 words of the new scene/section.")
#     reason: str = Field(description="Why is this a new scene? (e.g. 'Location change', 'Flashback', 'Topic shift').")
#     scene_type: str = Field(description="PHYSICAL, MEMORY, DREAM, or DOCUMENT_SECTION.")
#     context_summary: str = Field(description="Short label for this section (e.g. 'Alice remembers the Nile').")

# class SegmentationBatch(BaseModel):
#     boundaries: List[SceneBoundary]

# === 1. TAXONOMY ENUMS ===

class MoleculeType(str, Enum):
    """
    Фундаментальные типы молекул согласно новой онтологии.
    """
    AGENT = "AGENT"         # [cite: 4] Active entity, will, drive
    GROUP = "GROUP"         # [cite: 7] Social structure, hierarchy
    ASSET = "ASSET"         # [cite: 9] Material objects
    LOCATION = "LOCATION"   # [cite: 12] Spatial container
    CONSTRUCT = "CONSTRUCT" # [cite: 14] Skills, magic, tech
    LORE = "LORE"           # [cite: 16] Pure information

class AssetSubtype(str, Enum):
    ARTIFACT = "ARTIFACT"   # [cite: 10] Unique, history (Excalibur)
    COMMODITY = "COMMODITY" #  Fungible, resource (Gold)
    NONE = "NONE"

# === 2. EXTRACTION MODELS (Output for LLM) ===

class SceneItem(BaseModel):
    location_name: str = Field(description="Name of the physical location.")
    summary: str = Field(description="What happens in this scene.")
    # === НОВОЕ ПОЛЕ ===
    cast: List[str] = Field(
        default_factory=list,
        description="List of active characters present in this scene (e.g. ['Alice', 'Hatter']). Exclude mentions of absent people."
    )

class SceneBatch(BaseModel):
    scenes: List[SceneItem]

class DetectedEntity(BaseModel):
    """Модель для Global Entity Extraction (Macro-Pass)."""
    name: str = Field(description="Canonical, singular name (e.g., 'The Red Queen', not 'She').")
    category: MoleculeType = Field(description="Functional archetype of the entity.")
    subtype: Optional[AssetSubtype] = Field(
        default=None, 
        description="Only for ASSET: 'ARTIFACT' (unique) or 'COMMODITY' (fungible)."
    )
    description: str = Field(description="Brief summary of its role and key attributes.")

class EntityBatch(BaseModel):
    """Контейнер для списка сущностей."""
    entities: List[DetectedEntity]

class EventBeat(BaseModel):
    """Единичное событие внутри сцены (Beat)."""
    name: str = Field(description="Short name of the action.")
    description: str = Field(description="Detailed description.")
    
    participants: List[str] = Field(
        default_factory=list,
        description="List of specific character names actively involved in this beat (e.g. ['Alice', 'White Rabbit'])."
    )
    
    is_flashback: bool = Field(
        default=False, 
        description="True if this is a character recalling a past event, not happening 'now'."
    )
    is_continuation: bool = Field(
        default=False, 
        description="True if this is just more detail for the EXACT SAME previous action."
    )
    # causal_tag оставляем
    causal_tag: Literal["DIRECT", "MOTIVATION", "ENABLE", "NONE"] = "DIRECT"

class SceneEventBatch(BaseModel):
    """Контейнер для сцены и её событий."""
    scene_title: str = Field(description="High-level title of the episode (e.g. 'The Tea Party').")
    scene_summary: str = Field(description="Abstract summary of the whole scene (2-3 sentences).")
    
    # == МИКРО-УРОВЕНЬ ==
    events: List[EventBeat]

class SceneSegment(BaseModel):
    """Модель для Segmentation Pass (вместо Entity Resolver)."""
    location_name: str = Field(description="Name of the physical location where this segment takes place.")
    time_of_day: Optional[str] = Field(description="Time context if mentioned (e.g., 'Night', 'Tea Time').")
    summary: str = Field(description="High-level summary of what happens in this scene.")
    # Мы не просим start_index/end_index, так как будем матчить по чанкам
    
# class SceneBatch(BaseModel):
#     scenes: List[SceneSegment]

# --- NODES (Узлы) ---

class GraphLocation(BaseModel):
    """A distinct physical place mentioned in the narrative."""
    name: str = Field(description="Canonical name, e.g. 'The Grand Hall'")
    type: str = Field(description="Type: 'room', 'building', 'region', 'city'")
    summary: str = Field(description="High-level description of geography and atmosphere")
    # LLM сама должна придумать ID, но мы можем переопределить это в коде
    suggested_id: str = Field(description="Short unique slug, e.g. 'grand_hall'")
    # suggested_template_id: Optional[str] = Field(None, description="Best matching topology template ID")
    # template_confidence: float = 0.0

class GraphEvent(BaseModel):
    name: str
    description: str
    order_index: int
    location_slug: Optional[str] = Field(None, description="Slug of the location where this happened")
    
    # === ВОТ ЭТОГО ПОЛЯ НЕ ХВАТАЛО ===
    participants: List[str] = Field(
        default_factory=list,
        description="List of specific character names actively involved in this beat (e.g. ['Alice', 'White Rabbit'])."
    )
    
    # Флаг для обработки флешбеков
    is_recollection: bool = Field(
        default=False, 
        description="True if this event happened in the past and is only being remembered/discussed now."
    )
    # Если это повторение уже известного события (POV)
    is_continuation: bool = Field(
        default=False,
        description="True if this describes the same event as the previous scene, just from a different perspective."
    )

# --- EDGES (Связи) ---

class LocationConnection(BaseModel):
    """Spatial connection between locations."""
    from_slug: str
    to_slug: str
    type: Literal["path", "door", "gate", "hidden", "portal"]
    description: str = Field(description="Description of the path, e.g. 'A winding stone staircase'")

class CausalLink(BaseModel):
    """Causal relationship between events."""
    cause_event_index: int
    effect_event_index: int
    reason: str = Field(description="Why A caused B")

# --- BATCH (Контейнер) ---

class SkeletonBatch(BaseModel):
    """Output schema for the Macro-Pass."""
    locations: List[GraphLocation]
    connections: List[LocationConnection]
    events: List[GraphEvent]
    causal_links: List[CausalLink]
    