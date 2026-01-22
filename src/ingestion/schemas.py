from typing import List, Optional, Literal
from pydantic import BaseModel, Field, model_validator
from src.ingestion.graph_schemas import AssetSubtype, MoleculeType

# --- LEVEL 1: ENTITIES (MOLECULES) ---
class ExtractedMolecule(BaseModel):
    """Physical entities, objects, or NPCs found in the text."""
    name: str = Field(description="Canonical name (e.g. 'Vorpal Sword', not 'it')")
    category: Literal[MoleculeType.LORE, MoleculeType.AGENT, 
                      MoleculeType.GROUP, MoleculeType.ASSET, 
                      MoleculeType.LOCATION, MoleculeType.CONSTRUCT
                      ]
    # Добавляем subtype для реализации логики Commodities [cite: 10]
    subtype: Optional[Literal[AssetSubtype.ARTIFACT, AssetSubtype.COMMODITY]] = Field(
        default=None, 
        description="For ASSET only: 'ARTIFACT' (unique, named) or 'COMMODITY' (fungible resources like gold, ammo)."
    )
    description: str = Field(description="Visual description focused on physical properties.")
    # Просим LLM выделять Атомы в теги явно
    atom_tags: List[str] = Field(
        default_factory=list, 
        description="Key properties from ontology: 'agency', 'scarcity', 'integrity', 'heat', 'magic_potential'."
    )

    @model_validator(mode='after')
    def validate_subtype(self):
        # Если это не ASSET, подтип всегда None
        if self.category != MoleculeType.ASSET:
            self.subtype = None
        return self

# --- LEVEL 2: ACTIONS (VERBS) ---
class ExtractedVerb(BaseModel):
    """
    SYSTEM INTERACTIONS only. Ignore generic actions like 'walk', 'say', 'look'.
    Extract only if it implies: Damage, Skill Check, Resource Usage, or Magic.
    """
    name: str = Field(description="The mechanic name, e.g., 'Attack', 'Pick Lock', 'Persuade'")
    context_usage: str = Field(description="The specific snippet triggering this mechanic.")
    label: Literal["MECHANIC", "FLAVOR"]
    # Помогаем классификатору понять суть действия
    implied_system: Literal["COMBAT", "SOCIAL", "EXPLORATION", "MAGIC"] = Field(description="Which game system is involved?")
    force_desc: str = Field(description="Intensity/Difficulty description.")
    required_affordances: List[str] = Field(default_factory=list, description="Implied requirements e.g. 'sharpness', 'magic'")

# --- LEVEL 3: ATMOSPHERE (VIBES) ---
class ExtractedVibe(BaseModel):
    """Pure narrative flavor text."""
    snippet: str = Field(description="A flavorful text segment suitable for logs")
    tags: List[str] = Field(description="Mood tags e.g. 'dark', 'hopeful'")

# --- LEVEL 4: TOPOLOGY (LOCATIONS) ---
class ExtractedExit(BaseModel):
    direction: str = Field(description="Direction/Method e.g. 'North', 'Portal'")
    target_name: str = Field(description="Name of the destination")
    barrier: Optional[str] = Field(None, description="Barrier description if any (locked door, chasm)")

class ExtractedLocation(BaseModel):
    """Spatial nodes."""
    name: str = Field(description="Unique location name")
    type_tags: List[str] = Field(description="'indoor', 'forest', 'dungeon'")
    description: str = Field(description="Visual description of the space")
    exits: List[ExtractedExit] = Field(default_factory=list)

# --- LEVEL 5: CHRONICLE (EVENTS) ---
class ExtractedDelta(BaseModel):
    target: str = Field(description="Entity affected")
    change: str = Field(description="What changed? (died, broken, lost)")

class ExtractedEvent(BaseModel):
    """Narrative beats and state changes."""
    name: str = Field(description="Event title characterised description")
    description: str = Field(description="Summary of what happened")
    world_changes: List[ExtractedDelta] = Field(default_factory=list, description="List of state changes")

class ExtractedRelationship(BaseModel):
    """
    Semantic connection between two entities detected in the text.
    """
    subject_name: str = Field(description="Who is the active agent? (e.g. 'Goblin')")
    target_name: str = Field(description="Who/What is the target? (e.g. 'Dagger', 'Hero')")
    category: Literal["social", "possession", "knowledge", "spatial"] = Field(
        description="Type of bond: 'social' (hate/love), 'possession' (has item), 'knowledge' (knows secret), 'spatial' (is on/under)"
    )
    description: str = Field(description="Context of the relationship (e.g. 'clutching tightly', 'secretly despises')")

# === MASTER CONTAINER ===
class ExtractionBatch(BaseModel):
    """Container for LlamaIndex structured output."""
    molecules: List[ExtractedMolecule] = Field(default_factory=list)
    verbs: List[ExtractedVerb] = Field(default_factory=list)
    vibes: List[ExtractedVibe] = Field(default_factory=list)
    
    # Добавляем поле для связей
    relationships: List[ExtractedRelationship] = Field(default_factory=list)
    