import json
import uuid
import numpy as np
import os
from typing import List, Literal, Dict, Any

# КОД НИЖЕ УСТАРЕЛ, НО ЗДЕСЬ ПРАВИЛЬНОЕ ОБРАЩЕНИЕ
# К ЛОКАЛЬНЫМ МОДЕЛЯМ, ПОДДЕРЖИВАЮЩИМ JSON СХЕМЫ 

# === External Libs ===
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer

# === Config ===
from src.config import config, AppConfig

# ==============================================================================
# 1. MODELS (Schema)
# ==============================================================================
# Эти модели описывают структуру ответа LLM, они остаются здесь или в schema.py

class GenAtom(BaseModel):
    name: str = Field(description="Name of the component")
    sphere: Literal["material", "vitality", "social", "cognitive"]
    description: str = Field(description="Visual and semantic description")

class GenSlot(BaseModel):
    name: str = Field(description="Slot name (e.g. 'Core')")
    required_sphere: Literal["material", "vitality", "social", "cognitive"]
    search_query: str = Field(description="Description of qualities needed for this slot")

class GenMolecule(BaseModel):
    name: str = Field(description="Prototype name")
    description: str = Field(description="Prototype description")
    slots: List[GenSlot]

class OntologyBatch(BaseModel):
    atoms: List[GenAtom]
    molecules: List[GenMolecule]

# ==============================================================================
# 2. LOGIC
# ==============================================================================

class OntologyGenerator:
    def __init__(self, cfg: AppConfig = config):
        self.cfg = cfg
        
        print(f"🔌 Loading Embedder: {self.cfg.vector.model_name}...")
        self.embedder = SentenceTransformer(
            self.cfg.vector.model_name, 
            device=self.cfg.vector.device
        )
        
        print(f"🤖 Connecting to LLM at {self.cfg.llm.base_url}...")
        self.llm = ChatOpenAI(
            base_url=self.cfg.llm.base_url,
            api_key=self.cfg.llm.api_key,
            model=self.cfg.llm.model_name,
            temperature=self.cfg.llm.temperature,
            model_kwargs=self.cfg.llm.model_kwargs
        )
        self.structured_llm = self.llm.with_structured_output(OntologyBatch)

    def _get_vector(self, text: str) -> List[float]:
        # normalize_embeddings=True важно для работы vector_db
        return self.embedder.encode(text, normalize_embeddings=True).tolist()

    def generate(self, topic: str):
        # 1. Промпт упрощается
        # Нам больше не нужны {format_instructions}, так как схема передается на уровне API
        prompt = PromptTemplate(
            template="""
            You are an Architect for a simulation engine.
            Topic: "{topic}"
            
            Task:
            1. Create {atom_count} 'Component Atoms' (Fundamental building blocks).
            2. Create {molecule_count} 'Molecule Prototypes' (Complex items with slots).
            
            Constraints:
            - The 'search_query' in molecule slots must describe the *qualities* needed (e.g. "something sharp"), NOT the exact name of an atom.
            - Be creative.
            """,
            input_variables=["topic"],
            partial_variables={
                "atom_count": str(self.cfg.gen.atom_count),
                "molecule_count": str(self.cfg.gen.molecule_count)
            },
        )

        print(f"🧠 Generating ontology for '{topic}'...")

        # 2. Создаем цепочку: Промпт -> Структурированная LLM
        chain = prompt | self.structured_llm
        
        try:
            # 3. Запуск
            # Результат (raw_data) будет СРАЗУ объектом OntologyBatch!
            # Никаких json.loads или парсеров не нужно.
            raw_data: OntologyBatch = chain.invoke({"topic": topic})
            
        except Exception as e:
            print(f"❌ Structured Output Error: {e}")
            # Fallback: Если сервер не поддерживает native structured output,
            # можно попробовать старый метод (см. ниже)
            return

        # 4. Векторизация (без изменений)
        print("⚡️ Calculating vectors...")
        final_atoms = self._process_atoms(raw_data.atoms)
        final_molecules = self._process_molecules(raw_data.molecules)

        self._save_to_file(topic, final_atoms, final_molecules)

    def _process_atoms(self, atoms: List[GenAtom]) -> List[Dict[str, Any]]:
        result = []
        for a in atoms:
            result.append({
                "id": f"atom_{uuid.uuid4().hex[:6]}",
                "name": a.name,
                "sphere": a.sphere,
                "description": a.description,
                "vector": self._get_vector(a.description),
                "affordances": self.cfg.gen.default_affordances, # Из конфига
                "default_data": {}
            })
        return result

    def _process_molecules(self, molecules: List[GenMolecule]) -> List[Dict[str, Any]]:
        result = []
        for m in molecules:
            processed_slots = []
            for s in m.slots:
                processed_slots.append({
                    "name": s.name,
                    "required_sphere": s.required_sphere,
                    "search_query_text": s.search_query,
                    "search_query_vector": self._get_vector(s.search_query),
                    "threshold": self.cfg.gen.slot_threshold # Из конфига
                })
            
            result.append({
                "id": f"proto_{uuid.uuid4().hex[:6]}",
                "name": m.name,
                "description": m.description,
                "vector": self._get_vector(m.description),
                "slots": processed_slots
            })
        return result

    def _save_to_file(self, topic: str, atoms: List[GenAtom], molecules: List[GenMolecule]):
        safe_topic = topic.replace(" ", "_").lower()
        filename = self.cfg.gen.filename_template.format(topic=safe_topic)
        filepath = os.path.join(self.cfg.gen.output_dir, filename)
        
        output = {
            "metadata": {
                "topic": topic,
                "config_version": "1.0"
            },
            "atoms": atoms,
            "molecules": molecules
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            # Custom encoder handle numpy float types if needed
            json.dump(output, f, indent=2, default=lambda x: float(x) if isinstance(x, np.floating) else str(x))
            
        print(f"💾 Success! Saved to: {filepath}")

if __name__ == "__main__":
    # Можно переопределить конфиг на лету, если нужно
    # config.gen.atom_count = 10 
    
    gen = OntologyGenerator()
    gen.generate("Dark_Fantasy_Forest")
