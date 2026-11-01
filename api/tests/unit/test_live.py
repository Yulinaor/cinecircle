from fastapi.testclient import TestClient

from cinecircle_api.main import create_app
from cinecircle_api.settings import Settings


def test_live_ok():
    app = create_app(Settings(database_url="postgresql+psycopg://x@127.0.0.1:1/x", _env_file=None))
    r = TestClient(app).get("/live")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
