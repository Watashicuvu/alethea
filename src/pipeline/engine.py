# src/pipeline/engine.py
from qdrant_client.models import VectorParams, Distance
from src.config import PipelineOptions, config
from src.pipeline.context import PipelineContext
from src.pipeline.stages.ontology import OntologyLoader
from src.pipeline.stages.extraction import DocumentExtractor
from src.pipeline.stages.synthesis import WorldSynthesizer

class IngestionEngine:
    def __init__(self, options: PipelineOptions = PipelineOptions()):
        # 1. Единый контекст
        self.ctx = PipelineContext(options)
        
        # 2. Компоненты стадий
        self.ontology_loader = OntologyLoader(self.ctx)
        self.extractor = DocumentExtractor(self.ctx)
        self.synthesizer = WorldSynthesizer(self.ctx)

    def setup_infrastructure(self):
        """
        Создает необходимые коллекции в Qdrant и индексы в Neo4j перед стартом.
        """
        print("🛠️  Setting up DB Infrastructure...")
        
        # 1. Qdrant Dynamic Collections
        # (Static collection создается внутри OntologyLoader)
        dynamic_cols = [
            "molecules", "verbs", "vibes", 
            "chronicle", "narrative_instances",
            "skeleton_locations"
        ]
        
        for name in dynamic_cols:
            if not self.ctx.qdrant.collection_exists(name):
                self.ctx.qdrant.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(size=config.v_size, distance=Distance.COSINE),
                    shard_number=1
                )
                print(f"   + Qdrant Collection: {name}")

        # 2. Neo4j Constraints (вызывается скрыто внутри Neo4jClient.__init__)
        # Но можно дернуть явно, если нужно обновить
        # self.ctx.neo4j_client._init_constraints()
        print("✅ Infrastructure Ready.")

    def reset_context(self):
        self.ctx.reset_state()

    def index_registries(self, source_id: str = "core"):
        self.ontology_loader.run(source_id)

    def process_directory(self, input_dir: str, source_id: str):
        # Делегируем работу экстрактору
        self.extractor.process_directory(input_dir, source_id)

    def run_post_processing(self, source_id: str):
        # Делегируем работу синтезатору
        self.synthesizer.run(source_id)
