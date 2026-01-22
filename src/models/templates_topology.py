# src/data/templates_topology.py

from typing import List
import uuid
from src.models.ecs.ontology_topology import (
    TopologyTemplate, NodeSlot, GraphEdge, EdgeType
)
from src.models.ecs.ontology_schemas import SemanticVector, Sphere

def get_standard_topology_templates() -> List[TopologyTemplate]:
    """
    Возвращает набор жестко заданных топологических шаблонов (Blueprints).
    Теперь вектора (query_vector и query_vector) задаются через SemanticVector,
    явно определяя профиль (Material, Social, Cognitive, Vitality) локации.
    """
    templates: List[TopologyTemplate] = []

    # =========================================================================
    # 1. THE LINEAR GAUNTLET (Линейное Испытание)
    # Vibe: Хардкорное физическое преодоление. Мало общения, много боли.
    # =========================================================================
    tmpl_linear = TopologyTemplate(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"topo_linear_gauntlet")),
        name="Linear Gauntlet",
        description="A strictly sequential layout. Progression requires moving from one node to the next. No backtracking incentives.",
        
        # Общий вектор данжа: Высокая материя (стены), высокая витальность (опасность)
        query_vector=SemanticVector(material=0.9, vitality=0.8, social=0.1, cognitive=0.2),
        layout_type="chain",
        
        slots=[
            # [Index 0] Вход / Безопасная зона
            NodeSlot(
                id="slot_entry",
                # Спокойное место, можно подготовиться (Cognitive)
                query_vector=SemanticVector(material=0.5, social=0.4, cognitive=0.5, vitality=0.0), 
                required_sphere=None, 
                min_instances=1, max_instances=1
            ),
            # [Index 1] Основной путь / Препятствие
            NodeSlot(
                id="slot_corridor",
                # Узко, грязно, опасно.
                query_vector=SemanticVector(material=0.8, vitality=0.6, social=0.0, cognitive=0.1),
                min_instances=2, max_instances=5
            ),
            # [Index 2] Финал / Босс / Сокровище
            NodeSlot(
                id="slot_climax",
                # Эпицентр напряжения.
                query_vector=SemanticVector(material=1.0, vitality=0.9, cognitive=0.5, social=0.0),
                required_sphere=Sphere.MATERIAL,
                min_instances=1, max_instances=1
            )
        ],
        
        edges=[
            # Вход -> Коридор
            GraphEdge(
                from_slot_index=0, to_slot_index=1,
                type=EdgeType.PHYSICAL_PATH,
                traversal_cost=SemanticVector(), # 0.0
                tags=["door", "open"]
            ),
            # Коридор -> Коридор
            GraphEdge(
                from_slot_index=1, to_slot_index=1,
                type=EdgeType.PHYSICAL_PATH,
                traversal_cost=SemanticVector(vitality=0.2, material=0.1),
                tags=["path", "corridor"]
            ),
            # Коридор -> Финал
            GraphEdge(
                from_slot_index=1, to_slot_index=2,
                type=EdgeType.PHYSICAL_PATH,
                # Сюда сложно попасть
                traversal_cost=SemanticVector(vitality=0.6, material=0.5),
                tags=["gate", "locked", "boss_door"]
            )
        ]
    )
    templates.append(tmpl_linear)

    # =========================================================================
    # 2. HUB AND SPOKE (Звезда / Убежище)
    # Vibe: Социальное взаимодействие, безопасность, торговля.
    # =========================================================================
    tmpl_hub = TopologyTemplate(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"topo_hub_spoke")),
        name="Hub and Spoke",
        description="A centralized layout featuring a large common area connecting to multiple peripheral, isolated dead-end zones.",
        
        # Общий вектор: Социум доминирует.
        query_vector=SemanticVector(material=0.5, social=0.9, cognitive=0.4, vitality=0.1),
        layout_type="star",
        
        slots=[
            # [Index 0] Хаб (Центр)
            NodeSlot(
                id="slot_hub",
                # Место встреч. Максимальный Social.
                query_vector=SemanticVector(social=1.0, cognitive=0.6, material=0.4, vitality=0.1),
                required_sphere=Sphere.SOCIAL, 
                min_instances=1, max_instances=1
            ),
            # [Index 1] Приватные комнаты / Ответвления
            NodeSlot(
                id="slot_satellite",
                # Личное пространство. Social низкий (изоляция), Material средний (комфорт).
                query_vector=SemanticVector(social=0.2, material=0.6, cognitive=0.3, vitality=0.0),
                min_instances=3, max_instances=8
            )
        ],
        
        edges=[
            # Хаб <-> Сателлит
            GraphEdge(
                from_slot_index=0, to_slot_index=1,
                type=EdgeType.PHYSICAL_PATH,
                # Барьер - социальные нормы (нельзя просто так войти)
                traversal_cost=SemanticVector(social=0.4), 
                tags=["doorway", "curtain"]
            )
        ]
    )
    templates.append(tmpl_hub)

    # =========================================================================
    # 3. VERTICAL STACK (Вертикальность / Башня)
    # Vibe: Иерархия. Чем выше - тем умнее/богаче. Внизу - грязь.
    # =========================================================================
    tmpl_vertical = TopologyTemplate(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"topo_vertical_stack")),
        name="Vertical Stack",
        description="A vertically stacked hierarchy of zones. Traversal upwards requires overcoming gravity/energy costs.",
        
        # Общий вектор: Структура (Material) и Иерархия (Social/Cognitive)
        query_vector=SemanticVector(material=0.8, cognitive=0.6, social=0.5, vitality=0.5),
        layout_type="tree_vertical",
        
        slots=[
            # [Index 0] Дно / Фундамент
            NodeSlot(
                id="slot_bottom",
                # Грязь, техника, крысы. Material/Vitality.
                query_vector=SemanticVector(material=0.9, vitality=0.4, social=0.0, cognitive=0.1),
                required_sphere=Sphere.MATERIAL, 
                min_instances=1, max_instances=1
            ),
            # [Index 1] Средние уровни
            NodeSlot(
                id="slot_mid",
                # Обычная жизнь.
                query_vector=SemanticVector(material=0.5, social=0.5, cognitive=0.3, vitality=0.1),
                min_instances=2, max_instances=5
            ),
            # [Index 2] Вершина
            NodeSlot(
                id="slot_top",
                # Власть, обзор, чистота. Cognitive/Social.
                query_vector=SemanticVector(cognitive=1.0, social=0.8, material=0.4, vitality=0.0),
                required_sphere=Sphere.COGNITIVE, 
                min_instances=1, max_instances=1
            )
        ],
        
        edges=[
            # Дно -> Середина
            GraphEdge(
                from_slot_index=0, to_slot_index=1,
                type=EdgeType.PHYSICAL_PATH,
                traversal_cost=SemanticVector(vitality=0.6), # Гравитация
                tags=["stairs", "climb_up"]
            ),
            # Середина -> Дно
            GraphEdge(
                from_slot_index=1, to_slot_index=0,
                type=EdgeType.PHYSICAL_PATH,
                traversal_cost=SemanticVector(vitality=0.1), # Легко упасть
                tags=["stairs", "jump_down"]
            ),
            # Середина -> Вершина
            GraphEdge(
                from_slot_index=1, to_slot_index=2,
                type=EdgeType.PHYSICAL_PATH,
                # Нужен ключ-карта (Cognitive) или выносливость (Vitality)
                traversal_cost=SemanticVector(vitality=0.4, cognitive=0.4), 
                tags=["elevator", "security_check"]
            ),
            # Вершина -> Середина
            GraphEdge(
                from_slot_index=2, to_slot_index=1,
                type=EdgeType.PHYSICAL_PATH,
                traversal_cost=SemanticVector(), 
                tags=["elevator", "slide"]
            )
        ]
    )
    templates.append(tmpl_vertical)

    # =========================================================================
    # 4. ORGANIC LABYRINTH (Сетка / Руины)
    # Vibe: Запутанность. Требует Cognitive для навигации.
    # =========================================================================
    tmpl_grid = TopologyTemplate(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"topo_organic_grid")),
        name="Organic Labyrinth",
        description="A complex mesh of interconnected nodes with high redundancy. Low hierarchy, high confusion.",
        
        # Общий вектор: Высокий Cognitive (сложно понять структуру), средний Material
        query_vector=SemanticVector(cognitive=0.8, material=0.7, social=0.1, vitality=0.3),
        layout_type="organic",
        
        slots=[
            # [Index 0] Узел / Заросли
            NodeSlot(
                id="slot_node",
                # Одинаковые, запутанные места.
                query_vector=SemanticVector(material=0.6, cognitive=0.5, vitality=0.2, social=0.0),
                min_instances=5, max_instances=12
            ),
            # [Index 1] Доминанта / Ориентир
            NodeSlot(
                id="slot_landmark",
                # Что-то, что выделяется смыслом (Cognitive)
                query_vector=SemanticVector(cognitive=0.9, material=0.5, social=0.2, vitality=0.0),
                required_sphere=Sphere.COGNITIVE,
                min_instances=1, max_instances=2
            )
        ],
        
        edges=[
            # Обычный проход
            GraphEdge(
                from_slot_index=0, to_slot_index=0,
                type=EdgeType.PHYSICAL_PATH,
                traversal_cost=SemanticVector(vitality=0.2),
                tags=["path", "gap"]
            ),
            # Визуальный контакт
            GraphEdge(
                from_slot_index=0, to_slot_index=1,
                type=EdgeType.VISUAL_LOS,
                traversal_cost=SemanticVector(), # Стоимость не применима
                tags=["view_of", "window"]
            ),
            # Секрет
            GraphEdge(
                from_slot_index=0, to_slot_index=0,
                type=EdgeType.HIDDEN_SECRET,
                # Чтобы найти, нужен интеллект/восприятие
                traversal_cost=SemanticVector(cognitive=0.8), 
                tags=["secret_tunnel", "hidden_path"]
            )
        ]
    )
    templates.append(tmpl_grid)

    return templates
