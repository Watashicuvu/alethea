import os
from typing import Any, Dict, List
from pydantic import BaseModel, Field, SecretStr


LOCALHOST = "http://192.168.1.73"

class LLMSettings(BaseModel):
    base_url: str = f"{LOCALHOST}:1235/v1"
    api_key: str = ""
    #api_key: SecretStr = SecretStr(secret_value="lm-studio")
    model_name: str = "nvidia_NVIDIA-Nemotron-Nano-9B-v2-GGUF" #"ministral-3-14b-reasoning"
    temperature: float = 0.7
    model_kwargs: Dict[str, Any] = Field(default_factory=dict)

class PipelineOptions(BaseModel):
    """Флаги для включения/выключения этапов проекции."""
    # Micro-Pass (Сущности)
    micro: bool = True
    project_atoms: bool = True      # Разлагать ли предметы на компоненты (Density, Sharpness)?
    project_roles: bool = True      # Классифицировать ли NPC по ролям (Aggressor, Mentor)?
    project_verbs: bool = True      # Мапить ли действия на механики (Attack, Move)?
    
    # Macro-Pass (Мир)
    macro: bool = True
    project_topology: bool = True   # Искать ли архетипы локаций (Hub, Corridor)?
    project_events: bool = True     # Классифицировать ли события (Battle, Negotiation)?
    
    # Post-Processing
    post_proc: bool = True
    detect_arcs: bool = True       # Пытаться ли найти сюжетные арки после загрузки?

class QgdrantSettings(BaseModel):
    url: str = f"{LOCALHOST}:6333"

class Neo4jSettings(BaseModel):
    uri: str = f"bolt://localhost:7687"
    user: str = "neo4j"
    password: str = "password"

class VectorSettings(BaseModel):
    model_name: str = "text-embedding-embed_gemma"
    base_url: str = f"{LOCALHOST}:1235/v1"
    #api_key: SecretStr = SecretStr(secret_value="lm-studio")
    api_key: str = ""
    device: str = "cpu" # или "cuda"

class GenerationSettings(BaseModel):
    atom_count: int = 6
    molecule_count: int = 3
    default_affordances: List[str] = Field(default_factory=lambda: ["exist"])
    slot_threshold: float = 0.45
    
    # Пути
    output_dir: str = "assets"
    filename_template: str = "ontology_{topic}.json"

class PromptSettings(BaseModel):
    # Шаблон промпта вынесен сюда. Обратите внимание на {atom_count} и {molecule_count}
    template: str = (
                "You are the World Architect. Analyze the following narrative segment.\n"
                "Extract the **SKELETON** of the world:\n"
                "1. LOCATIONS: Distinct places. Merge synonyms.\n"
                "2. CONNECTIONS: Physical paths.\n"
                "3. CHRONICLE: Major events list. Maintain causal flow. "
                "For every causal link, determine strict type: DIRECT (physics), "
                "MOTIVATION (psychology), ENABLE (pre-condition).\n\n"
                "CONTEXT FROM PREVIOUS SEGMENT: {prev_context}\n"
                "TEXT SEGMENT:\n{text}\n\n"
                "Output strictly JSON."
            )

class AppConfig(BaseModel):
    llm: LLMSettings = Field(default_factory=LLMSettings)
    vector: VectorSettings = Field(default_factory=VectorSettings)
    gen: GenerationSettings = Field(default_factory=GenerationSettings)
    prompts: PromptSettings = Field(default_factory=PromptSettings)
    neo4j: Neo4jSettings = Field(default_factory=Neo4jSettings)
    qdrant: QgdrantSettings = Field(default_factory=QgdrantSettings)
    v_size: int = 768

# Создаем глобальный экземпляр конфига (можно загружать из .env или yaml)
config = AppConfig()

# Автосоздание папки assets, если нет
os.makedirs(config.gen.output_dir, exist_ok=True)
