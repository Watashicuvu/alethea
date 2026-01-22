import time
import random

from src.services.knowledge_service import WorldKnowledgeService

def run_ant_farm_tick(location_uuid: str):
    service = WorldKnowledgeService()
    
    # 1. THE LOADER: Load "Petri Dish"
    print(f"🧪 Loading entities from Location {location_uuid}...")
    entities = service.load_scene_snapshot(location_uuid)
    
    if len(entities) < 2:
        print("Not enough atoms to collide.")
        return

    # 2. THE SIMULATION LOOP (Brownian Motion)
    # Pick two random entities
    entity_a = random.choice(entities)
    entity_b = random.choice(entities)
    
    if entity_a['id'] == entity_b['id']:
        return

    print(f"\n⚡ Interaction: {entity_a['name']} + {entity_b['name']}")

    # 3. THE RESOLVER: Vector Physics
    distance = service.calculate_interaction_outcome(entity_a['vector'], entity_b['vector'])
    
    print(f"   Similarity Score: {distance:.3f}")

    new_stats_a = entity_a['stats'].copy()

    # LOGIC from Plan 
    if distance > 0.75:
        print("   ✅ ATTRACTION (Synergy/Trade)")
        # Example: Increase Social, Decrease Material (Trading cost)
        new_stats_a['social'] += 0.1
        new_stats_a['material'] -= 0.05
        
    elif distance < 0.3:
        print("   ⚔️ REPULSION (Conflict/Damage)")
        # Example: Find a weapon (Verb)
        verbs = service.find_compatible_mechanics(entity_a['vector'], top_k=1)
        verb_name = verbs[0]['verb_name'] if verbs else "Struggle"
        print(f"      -> {entity_a['name']} uses {verb_name}!")
        
        # Damage Calculation (Tier 1 Math)
        new_stats_a['vitality'] -= 0.1

    else:
        print("   💤 NEUTRAL (Ignore)")

    # 4. PERSISTENCE: Save changes
    if new_stats_a != entity_a['stats']:
        service.update_entity_state(entity_a['id'], new_stats_a)
        print("   💾 State Saved.")

    service.close()

# Example Call (Requires a valid Location UUID from your Graph)
run_ant_farm_tick("some-location-uuid")
