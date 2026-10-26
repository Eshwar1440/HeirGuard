import pytest

from hg import store
from hg.config import get_settings


@pytest.fixture
def fresh_clients():
    store.get_supabase.cache_clear()
    store.close_driver()
    yield
    store.get_supabase.cache_clear()
    store.close_driver()


def test_supabase_requires_config(monkeypatch, fresh_clients):
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(store.StoreConfigError):
        store.get_supabase()


def test_neo4j_requires_password(monkeypatch, fresh_clients):
    monkeypatch.setenv("NEO4J_PASSWORD", "")
    get_settings.cache_clear()
    with pytest.raises(store.StoreConfigError):
        store.get_driver()


@pytest.mark.neo4j
def test_neo4j_run_round_trip(fresh_clients):
    try:
        store.get_driver().verify_connectivity()
    except Exception as exc:  # no local Neo4j running
        pytest.skip(f"Neo4j not reachable: {exc}")

    case_id = "test-store-roundtrip"
    store.run("MATCH (n {case_id: $case_id}) DETACH DELETE n", case_id=case_id)
    store.run("MERGE (p:Person {case_id: $case_id, id: $id}) SET p.name = $name",
              case_id=case_id, id="p1", name="Hypothetical Person")
    rows = store.run("MATCH (p:Person {case_id: $case_id}) RETURN p.name AS name", case_id=case_id)
    assert rows == [{"name": "Hypothetical Person"}]
    store.run("MATCH (n {case_id: $case_id}) DETACH DELETE n", case_id=case_id)
