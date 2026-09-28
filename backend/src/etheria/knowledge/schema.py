"""Neo4j constraints and indexes (spec 6.1). Idempotent: IF NOT EXISTS.

Drug.key is the normalised name (knowledge.text.normalise_name) and is how
every lookup finds a drug. It is unique because curated extra drugs have no
DDInter id. Symptom.search_text is one string (name + lay terms) so a single
full-text index covers both without relying on list-property indexing."""

import neo4j

STATEMENTS = [
    "CREATE CONSTRAINT condition_icd10 IF NOT EXISTS FOR (c:Condition) REQUIRE c.icd10 IS UNIQUE",
    "CREATE CONSTRAINT symptom_code IF NOT EXISTS FOR (s:Symptom) REQUIRE s.code IS UNIQUE",
    "CREATE CONSTRAINT drug_ddinter_id IF NOT EXISTS FOR (d:Drug) REQUIRE d.ddinter_id IS UNIQUE",
    "CREATE CONSTRAINT drug_key IF NOT EXISTS FOR (d:Drug) REQUIRE d.key IS UNIQUE",
    "CREATE CONSTRAINT drug_class_name IF NOT EXISTS FOR (k:DrugClass) REQUIRE k.name IS UNIQUE",
    "CREATE CONSTRAINT body_system_name IF NOT EXISTS FOR (b:BodySystem) REQUIRE b.name IS UNIQUE",
    "CREATE FULLTEXT INDEX drug_name IF NOT EXISTS FOR (d:Drug) ON EACH [d.name]",
    "CREATE FULLTEXT INDEX symptom_text IF NOT EXISTS FOR (s:Symptom) ON EACH [s.search_text]",
]


async def apply_schema(driver: neo4j.AsyncDriver) -> None:
    for statement in STATEMENTS:  # schema changes cannot share a transaction
        await driver.execute_query(statement)
    await driver.execute_query("CALL db.awaitIndexes(60)")
