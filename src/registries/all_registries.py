# src/registries/all_registries.py

from src.models.ecs.ontology_chronicle import NarrativeArcTemplate, NarrativeRole
from src.models.ecs.ontology_schemas import ComponentDefinition
from src.models.ecs.ontology_topology import TopologyTemplate
from src.models.ecs.ontology_verbs import VerbAtom
from src.registries.base import OntologyRegistry

# Импорты фабрик
from src.models.templates_arcs import get_standard_arc_templates
from src.models.templates_verbs import get_verb_definitions
from src.models.templates_roles import get_common_roles
from src.models.templates_topology import get_standard_topology_templates
from src.models.templates_atoms import get_standard_atoms
from src.models.templates_events import EventArchetype, get_standard_event_archetypes


# --- 1. СОБЫТИЯ (EVENTS) ---
# Для событий важно описание и теги последствий ("War", "Death")
def _extract_event(e: EventArchetype):
    tags = " ".join(e.primary_consequence_tags)
    return f"{e.name}. {e.description}. Consequences: {tags}"

EVENTS = OntologyRegistry(
    data_factory=get_standard_event_archetypes,
    text_extractor=_extract_event
)

# --- 2. АТОМЫ (ATOMS) ---
# Для атомов важны аффордансы ("sharp", "flammable")
def _extract_atom(a: ComponentDefinition):
    affs = " ".join(a.affordances)
    return f"{a.name}. {a.description}. Properties: {affs}"

ATOMS = OntologyRegistry(
    data_factory=get_standard_atoms,
    text_extractor=_extract_atom
)

# --- 3. ГЛАГОЛЫ (VERBS) ---
# Для глаголов — описание действия
def _extract_verb(v: VerbAtom):
    return f"{v.name}. {v.description}"

VERBS = OntologyRegistry(
    data_factory=get_verb_definitions,
    text_extractor=_extract_verb
)

# --- 4. РОЛИ (ROLES) ---
# Для ролей — описание функции ("Leader", "Victim") + требуемые теги
def _extract_role(r: NarrativeRole):
    reqs = " ".join(r.required_tags)
    return f"{r.description}. Requirements: {reqs}"

ROLES = OntologyRegistry(
    data_factory=get_common_roles,
    text_extractor=_extract_role
)

# --- 5. ТОПОЛОГИЯ (TOPOLOGIES) ---
# Для шаблонов — описание места и слоты
def _extract_topo(t: TopologyTemplate):
    # Можно добавить информацию о слотах, если она есть в модели
    return f"{t.name}. {t.description}"

TOPOLOGIES = OntologyRegistry(
    data_factory=get_standard_topology_templates,
    text_extractor=_extract_topo
)

# --- 6. СЮЖЕТЫ (ARCS) ---
# Для арок — общее описание драмы
def _extract_arc(a: NarrativeArcTemplate):
    return f"{a.name}. {a.description}"

ARCS = OntologyRegistry(
    data_factory=get_standard_arc_templates,
    text_extractor=_extract_arc
)
