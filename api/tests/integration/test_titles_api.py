import pytest
from fastapi.testclient import TestClient

from cinecircle_api.catalog.service import TitleService
from cinecircle_api.main import create_app
from cinecircle_api.settings import Settings
from tests.fakes import ODYSSEY_ID, FakeOmdb, FakeTmdb
from tests.fixtures import load
from tests.integration.conftest import URL

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_catalog")]


def test_search_odyssey_hebrew_then_open_detail():
    app = create_app(Settings(database_url=URL, _env_file=None))
    app.state.title_service = TitleService(app.state.engine, FakeTmdb(), FakeOmdb())
    client = TestClient(app)

    r = client.get("/titles/search", params={"q": "האודיסאה", "type": "movie"})
    assert r.status_code == 200
    assert ODYSSEY_ID in [item["tmdb_id"] for item in r.json()["results"]]

    r = client.get(f"/titles/tmdb/movie/{ODYSSEY_ID}", params={"lang": "he"})
    assert r.status_code == 200
    he = r.json()
    assert he["ratings"]["imdb"]["rating"] == float(load("omdb/odyssey")["imdbRating"])
    assert he["name_lang"] == "he" and he["overview_lang"] == "he"

    r = client.get(f"/titles/{he['id']}", params={"lang": "en"})
    assert r.status_code == 200
    assert r.json()["id"] == he["id"] and r.json()["name_lang"] == "en"
