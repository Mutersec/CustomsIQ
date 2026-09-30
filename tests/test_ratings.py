"""Star ratings and comments about the service, published only after the owner approves.

Every test works through the real API on the shared app connection, so each one
finds its own rows by the unique username it created rather than by position.
"""

import re
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.customsiq import ratings
from src.customsiq.api import _conn, app
from src.customsiq.config import settings
from src.customsiq.database import (
    delete_user,
    fetch_activity,
    get_connection,
    get_rating_for_user,
    get_user_by_username,
    upsert_rating,
)
from tests.helpers import PASSWORD, code_sent_to, unique_email, unique_username

ROOT = Path(__file__).parent.parent / "src" / "customsiq"
INDEX = ROOT / "static" / "index.html"
PANEL = ROOT / "private_pages" / "admin.html"


def _verified_client(outbox: list, email: str) -> tuple[TestClient, str]:
    client = TestClient(app)
    username = unique_username("r")
    client.post("/auth/register", json={"username": username, "email": email, "password": PASSWORD})
    response = client.post(
        "/auth/verify", json={"email": email, "code": code_sent_to(outbox, email)}
    )
    assert response.status_code == 200, response.text
    return client, username


@pytest.fixture
def owner(outbox: list, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    email = unique_email("owner")
    monkeypatch.setattr(settings, "owner_emails", email)
    return _verified_client(outbox, email)[0]


@pytest.fixture
def member(outbox: list) -> tuple[TestClient, str]:
    return _verified_client(outbox, unique_email("member"))


def _post(client: TestClient, rating: int = 5, comment: str = "Very useful for our team.", **kw):
    return client.post("/ratings", json={"rating": rating, "comment": comment, **kw})


def _public_names(client: TestClient) -> list[str]:
    return [item["username"] for item in client.get("/ratings").json()["items"]]


def _id_of(owner: TestClient, username: str) -> int:
    rows = owner.get("/admin/api/ratings").json()
    return next(r["id"] for r in rows if r["username"] == username)


class TestSubmitting:
    def test_a_new_rating_waits_for_approval(self, member: tuple) -> None:
        client, name = member
        saved = _post(client, 4, "Good search, fast answers.", company="Acme Lojistik").json()
        assert saved["status"] == "pending"
        assert saved["company"] == "Acme Lojistik"
        body = client.get("/ratings").json()
        assert body["mine"]["status"] == "pending" and body["mine"]["rating"] == 4
        assert name not in _public_names(client)

    def test_the_company_is_optional(self, member: tuple) -> None:
        client, _ = member
        assert _post(client, company="   ").json()["company"] is None
        assert _post(client).json()["company"] is None

    def test_one_rating_per_account_and_editing_replaces_it(self, member: tuple) -> None:
        client, name = member
        _post(client, 2, "First impression was mixed.")
        _post(client, 5, "Changed my mind, it is great.")
        user = get_user_by_username(_conn, name)
        row = get_rating_for_user(_conn, user.id)
        assert (row.rating, row.comment) == (5, "Changed my mind, it is great.")

    @pytest.mark.parametrize(
        "body",
        [
            {"rating": 0, "comment": "Long enough comment."},
            {"rating": 6, "comment": "Long enough comment."},
            {"rating": 3, "comment": "short"},
            {"rating": 3, "comment": "          x"},
            {"rating": 3, "comment": "x" * 501},
            {"rating": 3, "comment": "Long enough comment.", "company": "c" * 81},
        ],
    )
    def test_invalid_input_is_refused(self, member: tuple, body: dict) -> None:
        client, _ = member
        assert client.post("/ratings", json=body).status_code == 422

    def test_the_user_can_withdraw_it(self, member: tuple) -> None:
        client, _ = member
        _post(client)
        assert client.delete("/ratings/mine").json() == {"deleted": True}
        assert client.get("/ratings").json()["mine"] is None
        assert client.delete("/ratings/mine").json() == {"deleted": False}

    def test_it_is_logged_for_the_owner(self, member: tuple) -> None:
        client, name = member
        _post(client, 5, "Logged comment text.")
        row = fetch_activity(_conn, username=name, action="rating")[0][0]
        assert row.result_count == 5 and "Logged comment text." in row.detail

    def test_markup_is_stored_as_plain_text(self, member: tuple) -> None:
        client, _ = member
        comment = "<script>alert(1)</script> nice"
        assert _post(client, 5, comment).json()["comment"] == comment

    def test_sign_in_is_required(self) -> None:
        anonymous = TestClient(app)
        assert anonymous.get("/ratings").status_code == 401
        assert _post(anonymous).status_code == 401
        assert anonymous.delete("/ratings/mine").status_code == 401


class TestModeration:
    def test_approval_publishes_it(self, owner: TestClient, member: tuple) -> None:
        client, name = member
        _post(client, 5, "Approved comment, thank you.")
        rating_id = _id_of(owner, name)
        response = owner.post(f"/admin/api/ratings/{rating_id}/status", json={"status": "approved"})
        assert response.status_code == 200
        assert name in _public_names(client)
        assert client.get("/ratings").json()["mine"]["status"] == "approved"

    def test_rejection_keeps_it_hidden(self, owner: TestClient, member: tuple) -> None:
        client, name = member
        _post(client, 1, "Rejected comment text.")
        owner.post(f"/admin/api/ratings/{_id_of(owner, name)}/status", json={"status": "rejected"})
        assert name not in _public_names(client)
        assert client.get("/ratings").json()["mine"]["status"] == "rejected"

    def test_editing_an_approved_rating_sends_it_back(
        self, owner: TestClient, member: tuple
    ) -> None:
        client, name = member
        _post(client, 5, "Originally approved text.")
        owner.post(f"/admin/api/ratings/{_id_of(owner, name)}/status", json={"status": "approved"})
        _post(client, 5, "Edited later, needs a new look.")
        assert name not in _public_names(client)
        assert client.get("/ratings").json()["mine"]["status"] == "pending"

    def test_the_owner_can_delete_one(self, owner: TestClient, member: tuple) -> None:
        client, name = member
        _post(client)
        rating_id = _id_of(owner, name)
        assert owner.delete(f"/admin/api/ratings/{rating_id}").status_code == 200
        assert owner.delete(f"/admin/api/ratings/{rating_id}").status_code == 404
        assert client.get("/ratings").json()["mine"] is None

    def test_the_owner_list_filters_by_status(self, owner: TestClient, member: tuple) -> None:
        client, name = member
        _post(client)
        pending = owner.get("/admin/api/ratings", params={"status": "pending"}).json()
        assert name in [r["username"] for r in pending]
        assert all(r["status"] == "pending" for r in pending)
        assert owner.get("/admin/api/ratings", params={"status": "bogus"}).status_code == 422

    def test_the_overview_counts_pending_ratings(self, owner: TestClient, member: tuple) -> None:
        before = owner.get("/admin/api/overview").json()["ratings_pending"]
        _post(member[0])
        assert owner.get("/admin/api/overview").json()["ratings_pending"] == before + 1

    def test_non_owners_get_404(self, member: tuple, owner: TestClient) -> None:
        client, _ = member
        assert client.get("/admin/api/ratings").status_code == 404
        assert (
            client.post("/admin/api/ratings/1/status", json={"status": "approved"}).status_code
            == 404
        )
        assert client.delete("/admin/api/ratings/1").status_code == 404

    def test_deleting_an_account_removes_its_rating(self, member: tuple) -> None:
        client, name = member
        _post(client)
        user = get_user_by_username(_conn, name)
        delete_user(_conn, user.id)
        assert get_rating_for_user(_conn, user.id) is None


class TestSummary:
    @pytest.fixture
    def conn(self) -> sqlite3.Connection:
        return get_connection(":memory:")

    def test_only_approved_ratings_count(self, conn: sqlite3.Connection) -> None:
        now = "2026-09-30T10:00:00+00:00"
        for user_id, stars, status in [
            (1, 5, "approved"),
            (2, 4, "approved"),
            (3, 4, "approved"),
            (4, 1, "pending"),
            (5, 1, "rejected"),
        ]:
            upsert_rating(conn, user_id, f"u{user_id}", stars, "A fine comment.", None, status, now)
        viewer = type("U", (), {"id": 4})()
        body = ratings.overview(conn, viewer)  # type: ignore[arg-type]
        assert body["count"] == 3
        assert body["average"] == 4.3
        assert body["distribution"] == {"5": 1, "4": 2, "3": 0, "2": 0, "1": 0}
        assert [i["username"] for i in body["items"]] == ["u3", "u2", "u1"]
        assert body["mine"]["status"] == "pending"
        # What other users see carries no ids and no status.
        assert set(body["items"][0]) == {"username", "rating", "comment", "company", "date"}

    def test_no_ratings_yet(self, conn: sqlite3.Connection) -> None:
        body = ratings.overview(conn, type("U", (), {"id": 1})())  # type: ignore[arg-type]
        assert body["count"] == 0 and body["average"] is None and body["items"] == []


class TestThePages:
    def test_the_card_sits_last_before_the_footer(self) -> None:
        html = INDEX.read_text(encoding="utf-8")
        card = html.index('id="ratings-panel"')
        assert html.index('data-i18n="reviewHistory.title"') < card < html.index("</main>")

    def test_every_rating_string_exists_in_all_three_languages(self) -> None:
        html = INDEX.read_text(encoding="utf-8")
        blocks = re.findall(r"\n      ratings: \{\n(.*?)\n      \},\n", html, re.S)
        assert len(blocks) == 3
        keys = [set(re.findall(r"(\w+): ", block)) for block in blocks]
        assert keys[0] == keys[1] == keys[2]
        for key in re.findall(r'data-i18n(?:-aria|-placeholder)?="ratings\.(\w+)"', html):
            assert key in keys[0], key

    def test_comments_are_escaped_before_they_reach_the_page(self) -> None:
        html = INDEX.read_text(encoding="utf-8")
        assert "${escapeHtml(r.comment)}" in html
        assert "${escapeHtml(r.username)}" in html
        panel = PANEL.read_text(encoding="utf-8")
        assert "${escapeHtml(r.comment)}" in panel

    def test_the_admin_panel_has_the_ratings_tab(self) -> None:
        panel = PANEL.read_text(encoding="utf-8")
        assert 'data-tab="ratings"' in panel and 'id="panel-ratings"' in panel
        assert '"rating"' in panel.split("const ACTIONS = [", 1)[1].split("]", 1)[0]
