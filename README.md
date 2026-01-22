
# Narrative Graph ETL Engine

## 📖 Project Overview

This engine automates the conversion of unstructured narrative text (design docs, scripts, novels) into a structured, queryable **Game World Graph**. It utilizes a "Data-as-Code" approach to ingest narrative content, transforming it into a dual-layer database: **Neo4j** (Topological/Causal relationships) and **Qdrant** (Semantic/Vector search).

The system is designed to power **Context-Aware NPCs** and **Procedural Storytelling** by maintaining a strict separation between the "Skeleton" (Macro-structure) and the "Flesh" (Micro-details).

---

## 🏗️ Architecture

The pipeline operates in a three-stage waterfall process: **Macro-Pass**, **Micro-Pass**, and **Post-Processing**.

```mermaid
graph TD
    A[Raw Text Input] --> B{Macro Pass: Skeleton}
    B --> C[Scene Mapping & Chronology]
    B --> D[Global Entity Registry]
    C --> E{Micro Pass: Flesh}
    D --> E
    E --> F[Mechanic Extraction (Verbs)]
    E --> G[Vibe & Atmosphere Injection]
    E --> H[Semantic Projection (Stats)]
    H --> I[Graph Construction (Neo4j + Qdrant)]
    I --> J{Post-Processing}
    J --> K[Narrative Arc Detection]
    J --> L[Global Stat Normalization]

```

---

## ⚙️ Core Pipeline Stages

### 1. Macro-Pass: World Skeleton

*Located in `graph_builder.py*`

Before analyzing details, the engine builds the architectural "bones" of the narrative.

* **Scene Segmentation:** Splits text into hierarchical `Episodes` based on location changes and narrative breaks using Hybrid Search (Vector + LLM).
* **Canonical Molecule Registry:** Extracts and deduplicates persistent entities (Agents, Factions, Artifacts) to ensure "The Cheshire Cat" and "The Cat" share a single UUID.
* **Chronicle Construction:** Establishes a strict timeline (`Event` -> `NEXT` -> `Event`) and handles non-linear narratives (flashbacks linked via `RECALLS` edges).

### 2. Micro-Pass: System Flesh

*Located in `pipeline.py*`

The engine iterates through the skeleton to extract gameplay data at the sentence level.

* **Mechanic Extraction (Verbs):** Identifies actions requiring dice rolls (e.g., "Attack," "Persuade"). Uses a runtime cache to filter narrative fluff from actual game systems.
* **Vibe Injection:** Vectorizes environmental descriptions to paint "Atmosphere" onto Locations in the graph (e.g., a room becoming "scarier" over time).
* **Semantic Projection:** A proprietary mathematical layer that projects text embeddings onto 4 Game Axes:
* **Material** (Physics/Assets)
* **Vitality** (Health/Combat)
* **Social** (Factions/Dialogue)
* **Cognitive** (Lore/Magic)
These stats are biased by entity type (e.g., *Lore* is high Cognitive/low Material).



### 3. Post-Processing & Normalization

*Located in `pipeline.py*`

Runs after the initial build to refine the dataset.

* **Narrative Arc Detection:** Scans the event chronicle against a registry of known tropes (e.g., "Hero's Journey," "Heist Setup") using vector similarity to tag narrative instances.
* **Global Stat Normalization:** Analyzes the distribution of all entity stats and applies Min-Max scaling to ensure game balance (e.g., ensuring the strongest monster is 1.0, not 0.8).

---

## 🧬 Data Ontology

The engine categorizes all data into a strict Game Ontology:

| Type | Description | Storage |
| --- | --- | --- |
| **Molecule** | Entities (Agents, Groups, Assets, Locations). Distinguishes `Artifact` (Unique) vs `Commodity` (Fungible). | Neo4j Node + Qdrant Point |
| **Verb** | System interactions. Maps narrative actions to specific Game Primitives (e.g., "Slash" -> `Melee_Attack_ID`). | Qdrant Point |
| **Event** | Chronological beats (`Tick`). Contains causality tags (`Enable`, `Motivate`). | Neo4j Node + Qdrant Point |
| **Vibe** | Atmospheric data snippets linked to Locations. | Qdrant Point (Aggregated in Neo4j) |

---

## 🛠️ Technical Stack & Dependencies

* **Orchestration:** Python 3.10+
* **LLM Framework:** LlamaIndex (Custom `LLMTextCompletionProgram` with Pydantic output).
* **Vector DB:** Qdrant (Handling `ontology_static`, `molecules`, `chronicle`, `vibes`).
* **Graph DB:** Neo4j (Handling Topology, Causality chains, and Spatial relationships).
* **Models:** OpenAI-compatible API (supports local LLMs like Gemma-2/Mistral via `OpenAILike`).

---

## 🚀 Key Features

* **Hybrid Classification:** Uses a mix of Vector Similarity (Fast) and LLM Reasoning (Accurate) to classify entities and events.
* **Dynamic Topology:** Locations can be "Stubs" (created on the fly) or mapped to pre-existing "Topology Templates" (e.g., *Prison Cell*) to inherit static game properties.
* **Flashback Handling:** Intelligently detects if a narrative beat references a past event. If the event exists, it links them; if not, it creates a "Detached Memory" node.

---
