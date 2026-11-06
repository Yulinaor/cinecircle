import pytest
from fastapi.testclient import TestClient

from cinecircle_api.catalog.service import TitleService
from cinecircle_api.main import create_app
from tests.fakes import ODYSSEY_ID, FakeOmdb, FakeTmdb
from tests.fixtures import load
from tests.integration.conftest import URL
from tests.tokens import auth_settings, make_token

USER_ID = "6f1c2b6e-0000-4000-8000-000000000001"

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_catalog")]


def test_search_odyssey_hebrew_then_open_detail():
    app = create_app(auth_settings(URL))
    app.state.title_service = TitleService(app.state.engine, FakeTmdb(), FakeOmdb())
    client = TestClient(app, headers={"Authorization": f"Bearer {make_token(USER_ID)}"})

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
