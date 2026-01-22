# src/pipeline/context.py
from dataclasses import dataclass
from typing import Optional

# Инфраструктура
from src.database.neo4j_client import Neo4jClient
from qdrant_client import QdrantClient
from llama_index.llms.openai_like import OpenAILike
from llama_index.embeddings.openai_like import OpenAILikeEmbedding
from transformers import AutoTokenizer

# Репозитории
from src.database.repositories.location_repo import LocationRepository
from src.database.repositories.entity_repo import EntityRepository
from src.database.repositories.chronicle_repo import ChronicleRepository

# Компоненты (предполагаем, что они пока в ingestion, но graph_builder уже в pipeline)
from src.ingestion.semantic_projector import SemanticProjector
from src.ingestion.synthesizer import EntitySynthesizer
from src.ingestion.classifier import HybridClassifier
from src.ingestion.resolver import EntityResolver

# ВАЖНО: Импортируем GraphBuilder. 
# Убедитесь, что файл graph_builder.py лежит в src/pipeline/graph_builder.py
from src.pipeline.graph_builder import GraphBuilder
from src.config import config

@dataclass
class Repositories:
    locations: LocationRepository
    entities: EntityRepository
    chronicle: ChronicleRepository

class PipelineContext:
    def __init__(self, options):
        self.options = options
        
        # 1. Инициализация моделей
        self.llm = OpenAILike(
            model=config.llm.model_name,
            api_key=config.llm.api_key,
            api_base=config.llm.base_url,
            temperature=0.1
        )
        self.embedder = OpenAILikeEmbedding(
            model_name=config.vector.model_name,
            api_base=config.vector.base_url,
            api_key=config.vector.api_key
        )
        # Токенизатор
        self.tokenizer = AutoTokenizer.from_pretrained("google/gemma-3-1b-it").encode 
        
        # 2. Инфраструктура БД
        self.qdrant = QdrantClient(url=config.qdrant.url)
        self.neo4j_client = Neo4jClient(
            uri=config.neo4j.uri, 
            user=config.neo4j.user, 
            password=config.neo4j.password
        )

        self.repos = Repositories(
            locations=LocationRepository(self.neo4j_client),
            entities=EntityRepository(self.neo4j_client),
            chronicle=ChronicleRepository(self.neo4j_client)
        )
        
        # 3. Базовые компоненты (Stateless или Long-lived)
        self.classifier = HybridClassifier(self.llm)
        self.projector = SemanticProjector(self.embedder)
        
        # 4. Компоненты с состоянием (будут созданы в reset_state)
        self.synthesizer: Optional[EntitySynthesizer] = None
        self.graph_builder: Optional[GraphBuilder] = None 
        self.resolver: Optional[EntityResolver] = None
        
        # Кэши
        self.verb_cache = {}

        # Первичная инициализация состояния
        self.reset_state()

    def reset_state(self):
        """
        Полная очистка оперативной памяти перед обработкой новой книги/источника.
        """
        print("🧹 Context Reset: Clearing in-memory state...")
        
        self.synthesizer = EntitySynthesizer(self.llm)
        
        # GraphBuilder зависит от всего вышеперечисленного, создаем последним.
        # ВАЖНО: Передаем self (контекст), а не synthesizer напрямую
        self.graph_builder = GraphBuilder(self)
        # 2. Пересоздаем компоненты, которые копят данные
        
        # 1. Очищаем кэши
        self.verb_cache = {}
        
        # Резолверу нужен доступ к контексту (чтобы видеть repos)
        self.resolver = EntityResolver(self)
        
        