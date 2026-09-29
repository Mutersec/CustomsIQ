"""The site owner's admin panel and the activity log behind it.

Access is by e-mail, not role: only a signed-in account whose verified e-mail
is in CUSTOMSIQ_OWNER_EMAILS gets in, and everyone else — admins by role
included — sees a plain 404.
"""

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.customsiq import admin, auth
from src.customsiq.api import _conn, app
from src.customsiq.config import settings
from src.customsiq.database import fetch_activity, get_email_for_user, get_user_by_username
from tests.helpers import (
    PASSWORD,
    code_sent_to,
    signed_in_test_client,
    unique_email,
    unique_username,
)

ADMIN_GETS = (
    "/admin",
    "/admin/api/overview",
    "/admin/api/users",
    "/admin/api/activity",
    "/admin/api/searches/unmatched",
)

STATIC = Path(__file__).parent.parent / "src" / "customsiq" / "static"
PANEL = Path(__file__).parent.parent / "src" / "customsiq" / "private_pages" / "admin.html"


def _verified_client(outbox: list, email: str) -> tuple[TestClient, str]:
    """A client signed in through the real e-mail sign-up, and its username."""
    client = TestClient(app)
    username = unique_username("u")
    assert (
        client.post(
            "/auth/register", json={"username": username, "email": email, "password": PASSWORD}
        ).status_code
        == 202
    )
    verified = client.post(
        "/auth/verify", json={"email": email, "code": code_sent_to(outbox, email)}
    )
    assert verified.status_code == 200, verified.text
    return client, username


@pytest.fixture
def owner(outbox: list, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, str]:
    email = unique_email("owner")
    # Listed in a different case, with a stray blank entry: both must be tolerated.
    monkeypatch.setattr(settings, "owner_emails", f" someone@else.org , , {email.upper()} ")
    return _verified_client(outbox, email)


@pytest.fixture
def member(outbox: list) -> tuple[TestClient, str]:
    return _verified_client(outbox, unique_email("member"))


def _rows(username: str, action: str = "") -> list:
    return fetch_activity(_conn, username=username, action=action or None, limit=200)[0]


class TestAccess:
    def test_the_owner_gets_in(self, owner: tuple) -> None:
        client, _ = owner
        for path in ADMIN_GETS:
            assert client.get(path).status_code == 200, path
        assert client.get("/auth/me").json()["is_owner"] is True

    @pytest.mark.parametrize("role", auth.ROLE_ORDER)
    def test_any_other_signed_in_account_gets_404(self, owner: tuple, role: str) -> None:
        client = signed_in_test_client(role)
        for path in ADMIN_GETS:
            assert client.get(path).status_code == 404, (role, path)
        assert client.post("/admin/api/users/x/role", json={"role": "admin"}).status_code == 404
        assert client.delete("/admin/api/users/x").status_code == 404
        assert client.get("/auth/me").json()["is_owner"] is False

    def test_the_demo_admin_gets_404(self, owner: tuple) -> None:
        client = TestClient(app)
        demo_name, demo_password, _ = auth.DEMO_USERS[-1]
        if get_user_by_username(_conn, demo_name) is None:
            auth.create_user(_conn, demo_name, demo_password, auth.ADMIN)
        login = client.post("/auth/login", json={"username": demo_name, "password": demo_password})
        assert login.status_code == 200
        assert client.get("/admin/api/users").status_code == 404

    def test_a_verified_member_whose_email_is_not_listed_gets_404(
        self, owner: tuple, member: tuple
    ) -> None:
        client, _ = member
        assert client.get("/admin").status_code == 404

    def test_nobody_gets_in_when_no_owner_is_configured(
        self, owner: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "owner_emails", "")
        client, _ = owner
        assert client.get("/admin").status_code == 404
        assert client.get("/auth/me").json()["is_owner"] is False

    def test_anonymous_callers_are_stopped_by_the_sign_in_gate(self) -> None:
        for path in ADMIN_GETS:
            assert TestClient(app).get(path).status_code == 401

    def test_the_panel_page_is_not_under_the_public_static_mount(self) -> None:
        assert not (STATIC / "admin.html").exists()
        assert TestClient(app).get("/static/admin.html").status_code == 404
        assert PANEL.exists()


class TestTheActivityLog:
    def test_a_search_is_logged_with_its_count_and_top_code(self, member: tuple) -> None:
        client, username = member
        top = client.get("/search", params={"q": "condom", "limit": 3}).json()
        rows = _rows(username, "search")
        assert rows[0].detail == "condom"
        assert rows[0].result_count == len(top)
        assert rows[0].top_code == top[0]["code"] == "401410"

    def test_a_search_with_no_results_is_logged_as_zero(self, member: tuple) -> None:
        client, username = member
        assert client.get("/search", params={"q": "qqzzxxvv"}).json() == []
        assert _rows(username, "search")[0].result_count == 0

    def test_every_tool_writes_its_own_action(self, member: tuple) -> None:
        client, username = member
        client.get("/classify", params={"description": "cotton t-shirt"})
        client.get("/screen", params={"name": "Example Trading"})
        client.get(
            "/calculate-duty",
            params={"hs_code": "6109100010", "country_of_origin": "CN", "customs_value": 1000},
        )
        client.get(
            "/assess-risk",
            params={
                "country_of_origin": "CN",
                "party_name": "Example Co",
                "customs_value": 500,
                "description": "cotton t-shirt",
            },
        )
        actions = {row.action for row in _rows(username)}
        assert {"signup", "classify", "screen", "duty", "risk"} <= actions

    def test_sign_in_and_sign_out_are_logged(self, member: tuple) -> None:
        client, username = member
        client.post("/auth/logout")
        client.post("/auth/login", json={"username": username, "password": PASSWORD})
        actions = [row.action for row in _rows(username)]
        assert actions[:3] == ["login", "logout", "signup"]

    def test_no_password_or_code_ever_reaches_the_log(self, outbox: list) -> None:
        email = unique_email("secret")
        client, username = _verified_client(outbox, email)
        code = code_sent_to(outbox, email)
        client.post("/auth/login", json={"username": username, "password": PASSWORD})
        for row in _rows(username):
            text = " ".join(str(value) for value in row)
            assert PASSWORD not in text and code not in text

    def test_invoice_content_is_never_logged(self, member: tuple) -> None:
        client, username = member
        pdf = (Path(__file__).parent / "fixtures" / "sample_invoice.pdf").read_bytes()
        response = client.post(
            "/extract-invoice", content=pdf, headers={"Content-Type": "application/pdf"}
        )
        assert response.status_code == 200
        row = _rows(username, "invoice")[0]
        assert row.result_count == len(response.json()["fields"])
        values = [f["value"] for f in response.json()["fields"] if len(f["value"]) > 3]
        assert values and not [v for v in values if v in (row.detail or "")]

    def test_a_long_query_is_clipped(self, member: tuple) -> None:
        _, username = member
        user = get_user_by_username(_conn, username)
        admin.record(_conn, user, "search", "x" * 500, 0)
        assert len(_rows(username, "search")[0].detail) == admin.MAX_DETAIL

    def test_a_failed_write_never_breaks_the_request(
        self, member: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client, _ = member

        def boom(*_args: object) -> None:
            raise RuntimeError("disk full")

        monkeypatch.setattr("src.customsiq.database.insert_activity", boom)
        assert client.get("/search", params={"q": "condom"}).status_code == 200

    def test_old_rows_are_pruned_after_the_retention_period(
        self, member: tuple, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _, username = member
        user = get_user_by_username(_conn, username)
        admin.record(_conn, user, "search", "old query", 1)
        admin.record(_conn, user, "search", "new query", 1)
        monkeypatch.setattr(settings, "activity_retention_days", 30)
        later = datetime.now(timezone.utc) + timedelta(days=31)
        admin.prune(_conn, now=later)
        assert _rows(username) == []


class TestTheAdminApi:
    def test_overview(self, owner: tuple) -> None:
        client, _ = owner
        body = client.get("/admin/api/overview").json()
        assert body["users_total"] >= 1 and body["users_new_today"] >= 1
        system = body["system"]
        assert system["hs6_codes"] == 2897 and system["cn_codes"] > 10_000
        assert system["mail_configured"] is True
        assert "test-key" not in str(body)

    def test_users_list_shows_email_method_and_last_activity(
        self, owner: tuple, member: tuple
    ) -> None:
        client, owner_name = owner
        member_client, member_name = member
        member_client.get("/search", params={"q": "condom"})
        users = {u["username"]: u for u in client.get("/admin/api/users").json()}
        member_id = get_user_by_username(_conn, member_name).id
        assert users[member_name]["email"] == get_email_for_user(_conn, member_id)
        assert users[member_name]["method"] == "email"
        assert users[member_name]["last_activity"]
        assert users[owner_name]["is_owner"] is True
        assert users[member_name]["is_owner"] is False

    def test_activity_filters_and_paging(self, owner: tuple, member: tuple) -> None:
        client, _ = owner
        member_client, member_name = member
        for query in ("condom", "qqzzxxvv", "solar panel"):
            member_client.get("/search", params={"q": query})
        mine = client.get("/admin/api/activity", params={"user": member_name}).json()
        assert mine["total"] == 4  # the sign-up plus three searches
        zero = client.get("/admin/api/activity", params={"user": member_name, "zero": True}).json()
        assert [row["detail"] for row in zero["items"]] == ["qqzzxxvv"]
        text = client.get("/admin/api/activity", params={"user": member_name, "q": "SOLAR"}).json()
        assert [row["detail"] for row in text["items"]] == ["solar panel"]
        page = client.get(
            "/admin/api/activity", params={"user": member_name, "limit": 2, "offset": 2}
        ).json()
        assert [row["action"] for row in page["items"]] == ["search", "signup"]

    def test_unmatched_searches_are_grouped_and_counted(self, owner: tuple, member: tuple) -> None:
        client, _ = owner
        member_client, _ = member
        word = "zzq" + unique_username("w").split("-")[1]
        for typed in (word, word.upper(), word):
            member_client.get("/search", params={"q": typed})
        # A screening with no hit is the good outcome, not a missing word.
        member_client.get("/screen", params={"name": word + " trading"})
        rows = {r["query"]: r["count"] for r in client.get("/admin/api/searches/unmatched").json()}
        assert rows[word] == 3
        assert word + " trading" not in rows

    def test_role_change(self, owner: tuple, member: tuple) -> None:
        client, _ = owner
        _, member_name = member
        response = client.post(f"/admin/api/users/{member_name}/role", json={"role": "analyst"})
        assert response.status_code == 200
        assert get_user_by_username(_conn, member_name).role == "analyst"
        bad = client.post(f"/admin/api/users/{member_name}/role", json={"role": "emperor"})
        assert bad.status_code == 400

    def test_delete_removes_the_account_its_sessions_and_email(
        self, owner: tuple, member: tuple
    ) -> None:
        client, _ = owner
        member_client, member_name = member
        member_client.get("/search", params={"q": "condom"})
        member_id = get_user_by_username(_conn, member_name).id
        assert client.delete(f"/admin/api/users/{member_name}").status_code == 200
        assert get_user_by_username(_conn, member_name) is None
        assert get_email_for_user(_conn, member_id) is None
        # The session died with the account.
        assert member_client.get("/search", params={"q": "condom"}).status_code == 401
        # The activity stays, as the audit trail.
        assert _rows(member_name, "search")
        assert client.delete(f"/admin/api/users/{member_name}").status_code == 404

    def test_the_owner_cannot_delete_or_demote_themselves(self, owner: tuple) -> None:
        client, owner_name = owner
        assert client.delete(f"/admin/api/users/{owner_name}").status_code == 400
        demote = client.post(f"/admin/api/users/{owner_name}/role", json={"role": "viewer"})
        assert demote.status_code == 400
        assert get_user_by_username(_conn, owner_name) is not None


class TestThePages:
    def test_every_panel_string_exists_in_all_three_languages(self) -> None:
        html = PANEL.read_text(encoding="utf-8")
        blocks = re.split(r"\n    (en|tr|de): \{\n", html.split("const STRINGS = {", 1)[1])
        keys = {
            lang: set(re.findall(r"(\w+): (?:\"|\{\s)", body.split("\n  };", 1)[0]))
            for lang, body in zip(blocks[1::2], blocks[2::2])
        }
        assert set(keys) == {"en", "tr", "de"}
        assert keys["en"] == keys["tr"] == keys["de"]
        for key in re.findall(r'data-i18n="([\w.]+)"', html):
            assert key.split(".")[-1] in keys["en"], key

    def test_the_sign_in_page_no_longer_promises_no_tracking(self) -> None:
        login = (STATIC / "login.html").read_text(encoding="utf-8")
        for phrase in ("no tracking", "izleme yok", "kein Tracking"):
            assert phrase not in login
        assert "Searches and actions are logged" in login
        assert "aramalar ve işlemler kayıt altına alınır" in login
        assert "Suchen und Aktionen werden" in login

    def test_the_app_shows_the_admin_link_only_when_the_server_says_owner(self) -> None:
        index = (STATIC / "index.html").read_text(encoding="utf-8")
        assert 'id="admin-link" href="/admin"' in index and "hidden></a>" in index
        assert "payload.is_owner" in index
