from neo4j import GraphDatabase
import logging

class Neo4jClient:
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self._init_constraints()

    def close(self):
        self.driver.close()

    def execute_query(self, query: str, **parameters):
        """Универсальная обертка для выполнения запросов."""
        with self.driver.session() as session:
            return session.run(query, **parameters)

    def execute_write(self, query: str, **parameters):
        """Для операций записи (можно добавить логику ретраев)."""
        with self.driver.session() as session:
            return session.run(query, **parameters)

    def _init_constraints(self):
        queries = [
            # Basic constraints
            "CREATE CONSTRAINT IF NOT EXISTS FOR (l:Location) REQUIRE l.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Event) REQUIRE e.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (m:Molecule) REQUIRE m.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (f:Faction) REQUIRE f.id IS UNIQUE", 
            "CREATE CONSTRAINT IF NOT EXISTS FOR (ep:Episode) REQUIRE ep.id IS UNIQUE",
            
            # Indexes for search
            "CREATE INDEX IF NOT EXISTS FOR (l:Location) ON (l.name)",
            "CREATE INDEX IF NOT EXISTS FOR (m:Molecule) ON (m.name)",
            "CREATE INDEX IF NOT EXISTS FOR (ep:Episode) ON (ep.start_tick)",
            
            # Fulltext indexes (Fuzzy Search)
            "CREATE FULLTEXT INDEX location_name_index IF NOT EXISTS FOR (n:Location) ON EACH [n.name]",
            "CREATE FULLTEXT INDEX faction_name_index IF NOT EXISTS FOR (n:Faction) ON EACH [n.name]",
            "CREATE FULLTEXT INDEX molecule_name_index IF NOT EXISTS FOR (n:Molecule) ON EACH [n.name]",
        ]
        with self.driver.session() as session:
            for q in queries:
                session.run(q)
                