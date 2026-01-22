# src/data/templates_verbs.py

from typing import List
import uuid
from src.models.ecs.ontology_verbs import (
    VerbAtom, VerbPrimitive, PrimitiveType, FlowPhase, Synergies
)
from src.models.ecs.ontology_schemas import SemanticVector, Sphere
from src.models.ecs.taxonomy import SemanticTag

def get_verb_definitions() -> List[VerbAtom]:
    """
    Реестр Семантических Глаголов.
    """
    verbs: List[VerbAtom] = []

    # =========================================================================
    # 1. PHYSICAL AGGRESSION (Бой / Насилие)
    # =========================================================================

    # --- ATTACK (Базовая атака) ---
    verbs.append(VerbAtom(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"act_phys_attack")),
        name="Physical Attack",
        description="A direct attempt to harm the target using physical force.",
        # Высокая материя (оружие/тело) и Витальность (ущерб жизни)
        vector=SemanticVector(material=0.9, vitality=0.9, social=0.1, cognitive=0.1),
        sphere=Sphere.VITALITY,
        required_affordances={SemanticTag.ACT_MAT_IMPACT},
        
        style_tags=[SemanticTag.STYLE_FORCE],
        
        combo_potential=Synergies(
            requires_prev_tags=[SemanticTag.STATE_KIN_STATIC], # Удар по оглушенному
            bonus_vector=SemanticVector(vitality=0.4),
            bonus_chance=0.3
        ),

        effects_on_success=[
            VerbPrimitive(
                type=PrimitiveType.MODIFY_VECTOR,
                target_alias="target",
                params={
                    "component": "bio_health",
                    "delta": -0.1,
                    "tag_on_zero": SemanticTag.STATE_BIO_DEAD
                }
            ),
            VerbPrimitive(
                type=PrimitiveType.MODIFY_VECTOR,
                target_alias="target",
                params={"vector_shift": {"social": -0.1}} 
            )
        ],
        flow_phase=FlowPhase.FINISHER
    ))

    # --- OVERPOWER (Захват) ---
    verbs.append(VerbAtom(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"act_phys_grapple")),
        name="Grapple / Restrain",
        description="Non-lethal force intended to immobilize the target.",
        # Чистая физика тел
        vector=SemanticVector(material=1.0, vitality=0.5, social=0.2, cognitive=0.2),
        sphere=Sphere.MATERIAL,
        required_affordances={SemanticTag.ACT_MAT_HOLD_SHAPE},
        
        style_tags=[SemanticTag.STYLE_CONTROL, SemanticTag.STYLE_FORCE],
        
        combo_potential=Synergies(
            requires_prev_tags=[SemanticTag.STATE_BIO_LETHARGIC], # Легче схватить уставшего
            bonus_chance=0.5
        ),

        effects_on_success=[
            VerbPrimitive(
                type=PrimitiveType.APPLY_TAG,
                target_alias="target",
                params={"tag": SemanticTag.STATE_KIN_STATIC}
            )
        ],
        flow_phase=FlowPhase.OPENER
    ))

    # =========================================================================
    # 2. TRAVERSAL & INTERACTION (Перемещение)
    # =========================================================================

    # --- MOVE (Перемещение) ---
    verbs.append(VerbAtom(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"act_trav_move")),
        name="Move / Travel",
        description="Changing location within the topology.",
        vector=SemanticVector(material=1.0, vitality=0.3, social=0.0, cognitive=0.1),
        sphere=Sphere.MATERIAL,
        required_affordances={SemanticTag.PROP_MOBILE},
        
        style_tags=[SemanticTag.STYLE_QUICK],

        effects_on_success=[
            VerbPrimitive(
                type=PrimitiveType.MOVE_TO,
                target_alias="target_location",
                params={} 
            ),
            VerbPrimitive(
                type=PrimitiveType.MODIFY_VECTOR,
                target_alias="source",
                params={"component": "bio_stamina", "delta": -0.1}
            )
        ]
    ))

    # --- BREAK (Разрушение) ---
    verbs.append(VerbAtom(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"act_mat_break")),
        name="Break / Destroy",
        description="Forceful destruction of an inanimate object.",
        vector=SemanticVector(material=1.0, vitality=0.1, social=0.0, cognitive=0.1),
        sphere=Sphere.MATERIAL,
        required_affordances={SemanticTag.ACT_MAT_IMPACT},
        
        style_tags=[SemanticTag.STYLE_FORCE],

        combo_potential=Synergies(
            requires_prev_tags=[SemanticTag.STATE_STRUCTURAL_WEAKNESS],
            bonus_chance=0.8
        ),

        effects_on_success=[
            VerbPrimitive(
                type=PrimitiveType.APPLY_TAG,
                target_alias="target",
                params={"tag": SemanticTag.STATE_STRUCTURAL_FAILURE}
            ),
            VerbPrimitive(
                type=PrimitiveType.TRANSFORM,
                target_alias="target",
                params={"new_edge_type": "path"}
            )
        ]
    ))

    # =========================================================================
    # 3. ADVANCED TRAVERSAL (Вернувшиеся глаголы)
    # =========================================================================

    # --- OPEN (Открытие) ---
    verbs.append(VerbAtom(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"act_trav_open")),
        name="Open / Unlock",
        description="Removing a barrier to access a path or container.",
        # Требует взаимодействия (Material) и понимания механизма (Cognitive)
        vector=SemanticVector(material=0.8, cognitive=0.4, social=0.0, vitality=0.0),
        sphere=Sphere.MATERIAL,
        required_affordances={SemanticTag.ACT_TRAV_OPEN},
        
        style_tags=[SemanticTag.STYLE_QUICK, SemanticTag.STYLE_ANALYTIC],

        effects_on_success=[
            VerbPrimitive(
                type=PrimitiveType.TRANSFORM,
                target_alias="target",
                params={"remove_tag": "state_locked", "add_tag": "state_open"}
            )
        ]
    ))

    # --- CLIMB (Карабканье) ---
    verbs.append(VerbAtom(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"act_trav_climb")),
        name="Climb / Scale",
        description="Vertical movement requiring physical exertion.",
        # Высокие затраты по физике и выносливости
        vector=SemanticVector(material=1.0, vitality=0.7, social=0.0, cognitive=0.2),
        sphere=Sphere.MATERIAL,
        required_affordances={SemanticTag.ACT_TRAV_CLIMB},
        
        style_tags=[SemanticTag.STYLE_FORCE],

        effects_on_success=[
            VerbPrimitive(
                type=PrimitiveType.MOVE_TO,
                target_alias="target_location",
                params={"method": "vertical"}
            ),
            VerbPrimitive(
                type=PrimitiveType.MODIFY_VECTOR,
                target_alias="source",
                params={"component": "bio_stamina", "delta": -0.15} 
            )
        ]
    ))

    # =========================================================================
    # 4. ECONOMIC / RESOURCE
    # =========================================================================

    # --- TAKE (Подбор) ---
    verbs.append(VerbAtom(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"act_mat_take")),
        name="Take Item",
        description="Acquiring a portable object.",
        vector=SemanticVector(material=0.9, cognitive=0.1, social=0.0, vitality=0.0),
        sphere=Sphere.MATERIAL,
        required_affordances={SemanticTag.ACT_MAT_CARRY},
        
        style_tags=[SemanticTag.STYLE_QUICK],

        effects_on_success=[
            VerbPrimitive(
                type=PrimitiveType.TRANSFER_ITEM,
                target_alias="target",
                params={"destination": "source_inventory"}
            )
        ]
    ))

    # --- STEAL (Кража) ---
    verbs.append(VerbAtom(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"act_mat_steal")),
        name="Steal / Pickpocket",
        description="Taking an item without consent.",
        # Высокий когнитив (хитрость) и социальный риск
        vector=SemanticVector(material=0.6, cognitive=0.8, social=0.7, vitality=0.0),
        sphere=Sphere.COGNITIVE,
        required_affordances={SemanticTag.ACT_MAT_CARRY},
        
        style_tags=[SemanticTag.STYLE_STEALTH, SemanticTag.STYLE_DECEPTION],
        
        combo_potential=Synergies(
            requires_prev_tags=[SemanticTag.STATE_INFO_MISLED, SemanticTag.STATE_COG_STUPOR],
            bonus_chance=0.4
        ),

        effects_on_success=[
            VerbPrimitive(
                type=PrimitiveType.TRANSFER_ITEM,
                target_alias="target_item",
                params={"destination": "source_inventory"}
            )
        ],
        effects_on_failure=[
            VerbPrimitive(
                type=PrimitiveType.CREATE_RELATION,
                target_alias="target_owner",
                params={"relation": "enemy", "value": -0.8}
            )
        ]
    ))

    # =========================================================================
    # 5. SOCIAL INTERACTION
    # =========================================================================

    # --- PERSUADE (Убеждение) ---
    verbs.append(VerbAtom(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"act_soc_persuade")),
        name="Persuade / Negotiate",
        description="Using logic or charm to improve relations.",
        vector=SemanticVector(social=1.0, cognitive=0.8, material=0.0, vitality=0.1),
        sphere=Sphere.SOCIAL,
        required_affordances={SemanticTag.ACT_SOC_EXCHANGE},
        
        style_tags=[SemanticTag.STYLE_DIPLOMACY],
        
        combo_potential=Synergies(
            requires_prev_tags=[SemanticTag.ACT_SOC_EXCHANGE], # Если уже был обмен/подарок
            bonus_chance=0.2
        ),

        effects_on_success=[
            VerbPrimitive(
                type=PrimitiveType.MODIFY_VECTOR,
                target_alias="target",
                params={"vector_shift": {"social": 0.2}}
            ),
            VerbPrimitive(
                type=PrimitiveType.CREATE_RELATION,
                target_alias="target",
                params={"relation": "neutral", "value": 0.1}
            )
        ],
        flow_phase=FlowPhase.LINK
    ))

    # --- INTIMIDATE (Запугивание) ---
    verbs.append(VerbAtom(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"act_soc_intimidate")),
        name="Intimidate / Threaten",
        description="Forcing compliance through fear.",
        # Социальное действие, опирающееся на угрозу насилием (Vitality/Phys)
        vector=SemanticVector(social=0.9, vitality=0.4, material=0.3, cognitive=0.5),
        sphere=Sphere.SOCIAL,
        required_affordances={SemanticTag.ACT_SOC_OPPRESS},
        
        style_tags=[SemanticTag.STYLE_DOMINANCE, SemanticTag.STYLE_FORCE],
        
        combo_potential=Synergies(
            requires_prev_tags=[SemanticTag.STATE_BIO_CRITICAL, SemanticTag.STATE_STRUCTURAL_FAILURE],
            bonus_chance=0.5,
            bonus_vector=SemanticVector(social=0.3)
        ),

        effects_on_success=[
            VerbPrimitive(
                type=PrimitiveType.APPLY_TAG,
                target_alias="target",
                params={"tag": SemanticTag.STATE_COG_STUPOR}
            ),
            VerbPrimitive(
                type=PrimitiveType.MODIFY_VECTOR,
                target_alias="target",
                params={"vector_shift": {"social": -0.3}}
            )
        ]
    ))

    # --- COMMAND (Приказ - вернулся) ---
    verbs.append(VerbAtom(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"act_soc_command")),
        name="Command / Order",
        description="Using established authority to direct actions.",
        # Чистая социальная власть
        vector=SemanticVector(social=1.0, cognitive=0.5, material=0.0, vitality=0.0),
        sphere=Sphere.SOCIAL,
        required_affordances={SemanticTag.ACT_SOC_COMMAND},
        
        style_tags=[SemanticTag.STYLE_DOMINANCE],

        effects_on_success=[
            VerbPrimitive(
                type=PrimitiveType.APPLY_TAG,
                target_alias="target",
                params={"tag": SemanticTag.STATE_SOC_OBEDIENT}
            )
        ],
        effects_on_failure=[
            VerbPrimitive(
                type=PrimitiveType.MODIFY_VECTOR,
                target_alias="source",
                params={"vector_shift": {"social": -0.5}} # Потеря лица
            )
        ]
    ))

    # --- BRIBE (Взятка - вернулась) ---
    verbs.append(VerbAtom(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"act_soc_bribe")),
        name="Bribe / Gift",
        description="Offering material goods to influence attitude.",
        # Материальный ресурс конвертируется в социальный капитал
        vector=SemanticVector(material=0.8, social=0.9, cognitive=0.4, vitality=0.0),
        sphere=Sphere.SOCIAL,
        required_affordances={SemanticTag.ACT_MAT_TRADE},
        
        style_tags=[SemanticTag.STYLE_DIPLOMACY],

        effects_on_success=[
            VerbPrimitive(
                type=PrimitiveType.TRANSFER_ITEM,
                target_alias="target",
                params={"item_filter": "currency"}
            ),
            VerbPrimitive(
                type=PrimitiveType.CREATE_RELATION,
                target_alias="target",
                params={"relation": "neutral", "value": 0.5}
            )
        ]
    ))

    # =========================================================================
    # 6. COGNITIVE / INFORMATION
    # =========================================================================

    # --- INSPECT (Осмотр) ---
    verbs.append(VerbAtom(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"act_cog_inspect")),
        name="Inspect / Analyze",
        description="Examining an object to reveal hidden details.",
        vector=SemanticVector(cognitive=1.0, material=0.2, social=0.0, vitality=0.0),
        sphere=Sphere.COGNITIVE,
        required_affordances={SemanticTag.ACT_VIT_SENSE},
        
        style_tags=[SemanticTag.STYLE_ANALYTIC],

        effects_on_success=[
            VerbPrimitive(
                type=PrimitiveType.APPLY_TAG,
                target_alias="target",
                params={"tag": "state_info_revealed"}
            ),
            VerbPrimitive(
                type=PrimitiveType.TRANSFORM, 
                target_alias="target",
                params={"reveal_secret": True} 
            )
        ]
    ))

    # --- HIDE (Скрытность) ---
    verbs.append(VerbAtom(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"act_cog_hide")),
        name="Hide / Stealth",
        description="Attempting to become undetectable.",
        vector=SemanticVector(cognitive=0.8, material=0.4, vitality=0.2, social=0.1),
        sphere=Sphere.COGNITIVE,
        
        style_tags=[SemanticTag.STYLE_STEALTH],
        
        combo_potential=Synergies(
            requires_prev_tags=[SemanticTag.CTX_ENTROPY_HIGH],
            bonus_chance=0.3
        ),

        effects_on_success=[
            VerbPrimitive(
                type=PrimitiveType.APPLY_TAG,
                target_alias="source",
                params={"tag": "state_stealth_active"}
            ),
            VerbPrimitive(
                type=PrimitiveType.MODIFY_VECTOR,
                target_alias="source",
                params={"vector_shift": {"social": -1.0}}
            )
        ]
    ))

    # --- LIE (Обман) ---
    verbs.append(VerbAtom(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"act_info_lie")),
        name="Lie / Deceive",
        description="Providing false information.",
        vector=SemanticVector(cognitive=0.9, social=0.8, material=0.0, vitality=0.0),
        sphere=Sphere.COGNITIVE,
        required_affordances={SemanticTag.ACT_INFO_LIE},
        
        style_tags=[SemanticTag.STYLE_DECEPTION],

        effects_on_success=[
            VerbPrimitive(
                type=PrimitiveType.APPLY_TAG,
                target_alias="target",
                params={"tag": SemanticTag.STATE_INFO_MISLED}
            )
        ],
        flow_phase=FlowPhase.OPENER
    ))

    # =========================================================================
    # 7. VITALITY SUPPORT
    # =========================================================================

    # --- HEAL (Лечение) ---
    verbs.append(VerbAtom(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"act_vit_heal")),
        name="Heal / Mend",
        description="Restoring biological integrity.",
        vector=SemanticVector(vitality=1.0, cognitive=0.5, material=0.3, social=0.2),
        sphere=Sphere.VITALITY,
        required_affordances={SemanticTag.ACT_VIT_HEAL},
        
        style_tags=[SemanticTag.STYLE_MYSTIC, SemanticTag.STYLE_ANALYTIC],

        combo_potential=Synergies(
            requires_prev_tags=[SemanticTag.STATE_BIO_CRITICAL],
            bonus_vector=SemanticVector(vitality=0.2)
        ),

        effects_on_success=[
            VerbPrimitive(
                type=PrimitiveType.MODIFY_VECTOR,
                target_alias="target",
                params={"component": "bio_health", "delta": 0.15}
            ),
            VerbPrimitive(
                type=PrimitiveType.MODIFY_VECTOR,
                target_alias="source",
                params={"component": "mat_supplies", "delta": -1.0}
            )
        ],
        flow_phase=FlowPhase.RECOVERY
    ))

    # --- CONSUME (Еда - вернулась) ---
    verbs.append(VerbAtom(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"act_vit_consume")),
        name="Consume / Eat",
        description="Ingesting an object to gain energy.",
        vector=SemanticVector(vitality=1.0, material=0.7, social=0.0, cognitive=0.0),
        sphere=Sphere.VITALITY,
        required_affordances={SemanticTag.ACT_VIT_EAT},
        
        style_tags=[SemanticTag.STYLE_QUICK],

        effects_on_success=[
            VerbPrimitive(
                type=PrimitiveType.MODIFY_VECTOR,
                target_alias="source",
                params={"component": "bio_stamina", "delta": 0.2}
            ),
            VerbPrimitive(
                type=PrimitiveType.TRANSFORM,
                target_alias="target",
                params={"delete_entity": True}
            )
        ]
    ))

    # =========================================================================
    # 8. CREATION & MODIFICATION (Вернувшиеся глаголы)
    # =========================================================================

    # --- REPAIR (Починка) ---
    verbs.append(VerbAtom(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"act_mat_repair")),
        name="Repair / Reinforce",
        description="Restoring structural integrity.",
        vector=SemanticVector(material=1.0, cognitive=0.6, vitality=0.0, social=0.0),
        sphere=Sphere.MATERIAL,
        required_affordances={SemanticTag.ACT_MAT_CRAFT},
        
        style_tags=[SemanticTag.STYLE_ANALYTIC],

        effects_on_success=[
            VerbPrimitive(
                type=PrimitiveType.MODIFY_VECTOR,
                target_alias="target",
                params={"component": "mat_integrity", "delta": 1.0}
            ),
            VerbPrimitive(
                type=PrimitiveType.TRANSFORM,
                target_alias="target",
                params={"remove_tag": SemanticTag.STATE_STRUCTURAL_FAILURE}
            )
        ]
    ))

    # --- CRAFT (Создание) ---
    verbs.append(VerbAtom(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"act_mat_craft")),
        name="Craft / Build",
        description="Combining resources to create a new entity.",
        vector=SemanticVector(material=1.0, cognitive=0.7, vitality=0.0, social=0.0),
        sphere=Sphere.MATERIAL,
        required_affordances={SemanticTag.ACT_MAT_CRAFT},
        
        style_tags=[SemanticTag.STYLE_ANALYTIC],

        combo_potential=Synergies(
             # Если находимся в мастерской (контекст индустрии)
            requires_prev_tags=[SemanticTag.CTX_INT_INDUSTRIAL],
            bonus_chance=0.2
        ),

        effects_on_success=[
            VerbPrimitive(
                type=PrimitiveType.SPAWN_ENTITY,
                target_alias="environment",
                params={"template_id": "result_item_id"}
            )
        ]
    ))

    # =========================================================================
    # 9. SUPERNATURAL
    # =========================================================================

    # --- CHANNEL (Каст) ---
    verbs.append(VerbAtom(
        id=str(uuid.uuid3(uuid.NAMESPACE_DNS,"act_cog_channel")),
        name="Channel Power",
        description="Focusing magical energy.",
        vector=SemanticVector(cognitive=1.0, vitality=0.6, material=0.1, social=0.0),
        sphere=Sphere.COGNITIVE,
        required_affordances={SemanticTag.ACT_COG_CAST},
        
        style_tags=[SemanticTag.STYLE_MYSTIC],
        
        combo_potential=Synergies(
            requires_prev_tags=[SemanticTag.CTX_HIGH_AWARENESS],
            bonus_vector=SemanticVector(cognitive=0.5, vitality=0.5)
        ),

        effects_on_success=[
            VerbPrimitive(
                type=PrimitiveType.MODIFY_VECTOR,
                target_alias="source",
                params={"component": "cog_mana", "delta": -0.10}
            ),
            VerbPrimitive(
                type=PrimitiveType.APPLY_TAG,
                target_alias="target",
                params={"tag": SemanticTag.CTX_HIGH_AWARENESS}
            )
        ]
    ))

    return verbs
