# src/ingestion/mappers.py
from typing import Type, List, Dict, Optional
from enum import Enum
import numpy as np
from openai import OpenAI
from rapidfuzz import process, fuzz

# Импортируем конфиг
from src.config import config

# Импортируем твои Enums 
from src.models.ecs.ontology_topology import EdgeType
from src.models.ecs.ontology_chronicle import CausalType
from src.models.ecs.ontology_edges import SocialRelType, ContainerRelType

class RelationshipSanitizer:
    """
    Фильтр, который запрещает физически невозможные связи
    на основе типов сущностей (Agent, Location, Asset).
    """
    
    @staticmethod
    def validate_and_fix(subj_type: str, obj_type: str, rel_type: str, rel_desc: str) -> str:
        s = subj_type.upper() if subj_type else "UNKNOWN"
        o = obj_type.upper() if obj_type else "UNKNOWN"
        r = rel_type.upper()
        
        # 1. ЗАПРЕТ: Агент внутри Агента
        # "Alice LOCATED_AT King" -> "Alice NEAR King"
        if r in ["LOCATED_AT", "IS_INSIDE", "CONTAINED_BY"]:
            if s == "AGENT" and o == "AGENT":
                return "NEAR" # Исправляем на пространственную близость
            
            # Агент внутри Предмета (если это не Транспорт)
            # Алиса в Бутылке? Возможно (магия). Алиса в Мече? Нет.
            if s == "AGENT" and o == "ASSET":
                # Тут можно проверять subtype предмета (Container/Vehicle), но пока оставим
                pass

        # 2. ЗАПРЕТ: Локация внутри чего-либо (кроме региона)
        if s == "LOCATION" and r in ["LOCATED_AT"]:
            if o == "AGENT": 
                return "MENTIONED_BY" # Лес не может быть в Алисе

        # 3. МЕНТАЛЬНЫЕ ПРОЕКЦИИ (Решение "Додо на Ниле")
        # Если описание связи содержит "thought", "remembered", "dreamt"
        keywords = ["thought", "remember", "dream", "imagine", "story"]
        if any(k in rel_desc.lower() for k in keywords):
            if r == "LOCATED_AT":
                return "THINKS_OF" # Отменяем телепортацию

        return r

class EnumMapper:
    """
    Гибридный классификатор: Hard Match -> Fuzzy Match -> OpenAILike Vector Match.
    """
    def __init__(self, enum_cls: Type[Enum], synonyms: Dict[str, List[str]]):
        print(f"🧠 Initializing Hybrid Mapper for {enum_cls.__name__} via API...")
        self.enum_cls = enum_cls
        
        # Настройка клиента OpenAILike
        self.client = OpenAI(
            base_url=config.vector.base_url,
            api_key=config.vector.api_key
        )
        self.model_name = config.vector.model_name
        
        # 1. Hard/Fuzzy Map
        self.keyword_map = {}
        for enum_member in enum_cls:
            val = enum_member.value
            self.keyword_map[val.lower()] = val
            if val in synonyms:
                for syn in synonyms[val]:
                    self.keyword_map[syn.lower()] = val
        
        # 2. Vector Map (Soft Search)
        self.keys = [e.value for e in enum_cls]
        self.descriptions = []
        for e in enum_cls:
            # Формируем богатое описание для векторизации
            desc = f"{e.value} {' '.join(synonyms.get(e.value, []))}"
            self.descriptions.append(desc)
            
        # Кэшируем векторы описаний при старте
        self.vectors = self._get_embeddings_batch(self.descriptions)

    def _get_embeddings_batch(self, texts: List[str]) -> np.ndarray:
        """Получение и нормализация батча векторов."""
        if not texts: return np.array([])
        resp = self.client.embeddings.create(input=texts, model=self.model_name)
        vecs = np.array([d.embedding for d in resp.data])
        # Нормализация
        norm = np.linalg.norm(vecs, axis=1, keepdims=True)
        return vecs / (norm + 1e-9)

    def _get_single_embedding(self, text: str) -> np.ndarray:
        """Получение одного вектора."""
        resp = self.client.embeddings.create(input=[text], model=self.model_name)
        vec = np.array(resp.data[0].embedding)
        norm = np.linalg.norm(vec)
        return vec / (norm + 1e-9)

    def classify(self, text: str, fuzzy_threshold: int = 85, vector_threshold: float = 0.35) -> Optional[str]:
        text_lower = text.lower()
        
        # --- STEP 1: KEYWORD SEARCH ---
        for kw, enum_val in self.keyword_map.items():
            if f" {kw} " in f" {text_lower} ": 
                return enum_val

        # --- STEP 2: FUZZY SEARCH ---
        best_match = process.extractOne(text_lower, self.keyword_map.keys(), scorer=fuzz.WRatio)
        if best_match:
            match_word, score, _ = best_match
            if score >= fuzzy_threshold:
                return self.keyword_map[match_word]

        # --- STEP 3: VECTOR SEARCH (OpenAILike API) ---
        query_vec = self._get_single_embedding(text) # (D,)
        
        # Dot product для косинусного сходства
        scores = np.dot(self.vectors, query_vec)
        
        best_idx = int(np.argmax(scores))
        best_score = scores[best_idx]
        
        if best_score >= vector_threshold:
            return self.keys[best_idx]

        return None

# --- КОНФИГУРАЦИЯ СИНОНИМОВ (Без изменений) ---
SOCIAL_SYNONYMS = {
    "ally": ["friend", "partner", "supporter", "aiding", "loyal"],
    "hostile": ["enemy", "rival", "opponent", "hates", "attacking", "aggressor"],
    "neutral": ["stranger", "passerby", "ignoring", "unknown"],
    "master_of": ["leader", "boss", "commander", "owner", "domineering"],
    "parent_of": ["father", "mother", "creator", "ancestor"],
    "romantic": ["lover", "spouse", "wife", "husband", "intimate", "dating"]
}

CONTAINER_SYNONYMS = {
    "equipped_by": ["holding", "wielding", "wearing", "gripping", "brandishing"],
    "stored_by": ["in pocket", "in bag", "inventory", "carrying", "hidden in"],
    "located_at": ["standing in", "sitting on", "placed at", "lying on"],
    "implanted_in": ["inside body", "parasite", "chip", "cyberware"]
}

EDGE_SYNONYMS = {
    "path": ["road", "corridor", "hallway", "door", "walkway"],
    "secret": ["hidden passage", "concealed door", "crawlspace", "illusion"],
    "line_of_sight": ["window", "balcony", "overlooking", "visible from"],
    "portal": ["teleport", "gate", "rift", "wormhole"]
}

# --- FACADE ---
class RelationMapper:
    def __init__(self):
        # Передаем только Enum и Синонимы, клиент создается внутри на основе config
        self.social = EnumMapper(SocialRelType, SOCIAL_SYNONYMS)
        self.container = EnumMapper(ContainerRelType, CONTAINER_SYNONYMS)
        self.topology = EnumMapper(EdgeType, EDGE_SYNONYMS)
        self.causal = EnumMapper(CausalType, {}) 

    def map_social(self, text: str) -> str: return self.social.classify(text)
    def map_container(self, text: str) -> str: return self.container.classify(text)
    def map_edge(self, text: str) -> str: return self.topology.classify(text)
    def map_causal(self, text: str) -> str: return self.causal.classify(text)

RELATIONS = RelationMapper()
