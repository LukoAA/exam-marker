def _auth_headers(client, email="jane@example.com", password="hunter22", name="Jane Doe"):
    client.post("/auth/register", json={"email": email, "password": password, "name": name})
    resp = client.post("/auth/login", json={"email": email, "password": password})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_course(client, headers, code="CSC301", title="Operating Systems"):
    return client.post(
        "/courses",
        json={
            "code": code,
            "title": title,
            "total_marks": 100,
            "grading_scale": {"A": [70, 100], "B": [60, 69], "F": [0, 39]},
            "language": "English",
        },
        headers=headers,
    )


def test_create_course_requires_auth(client):
    resp = _create_course(client, headers={})

    assert resp.status_code == 401


def test_create_course_owned_by_current_user(client):
    headers = _auth_headers(client)

    resp = _create_course(client, headers)

    assert resp.status_code == 201
    body = resp.json()
    assert body["code"] == "CSC301"
    assert body["title"] == "Operating Systems"
    assert float(body["total_marks"]) == 100.0
    assert body["grading_scale"] == {"A": [70, 100], "B": [60, 69], "F": [0, 39]}
    assert "user_id" in body


def test_list_courses_only_returns_own_courses(client):
    headers_a = _auth_headers(client, email="alice@example.com")
    headers_b = _auth_headers(client, email="bob@example.com")
    _create_course(client, headers_a, code="CSC301")
    _create_course(client, headers_b, code="MTH201")

    resp = client.get("/courses", headers=headers_a)

    assert resp.status_code == 200
    codes = [c["code"] for c in resp.json()]
    assert codes == ["CSC301"]


def test_get_course_not_owner_returns_404(client):
    headers_a = _auth_headers(client, email="alice@example.com")
    headers_b = _auth_headers(client, email="bob@example.com")
    course_id = _create_course(client, headers_a).json()["id"]

    resp = client.get(f"/courses/{course_id}", headers=headers_b)

    assert resp.status_code == 404


def test_get_nonexistent_course_returns_404(client):
    headers = _auth_headers(client)

    resp = client.get("/courses/999", headers=headers)

    assert resp.status_code == 404


def test_update_course_owner_can_patch(client):
    headers = _auth_headers(client)
    course_id = _create_course(client, headers).json()["id"]

    resp = client.patch(f"/courses/{course_id}", json={"title": "OS Updated"}, headers=headers)

    assert resp.status_code == 200
    assert resp.json()["title"] == "OS Updated"
    assert resp.json()["code"] == "CSC301"


def test_update_course_not_owner_returns_404(client):
    headers_a = _auth_headers(client, email="alice@example.com")
    headers_b = _auth_headers(client, email="bob@example.com")
    course_id = _create_course(client, headers_a).json()["id"]

    resp = client.patch(f"/courses/{course_id}", json={"title": "Hijacked"}, headers=headers_b)

    assert resp.status_code == 404


def test_delete_course_owner_can_delete(client):
    headers = _auth_headers(client)
    course_id = _create_course(client, headers).json()["id"]

    resp = client.delete(f"/courses/{course_id}", headers=headers)
    assert resp.status_code == 204

    follow_up = client.get(f"/courses/{course_id}", headers=headers)
    assert follow_up.status_code == 404


def test_delete_course_not_owner_returns_404(client):
    headers_a = _auth_headers(client, email="alice@example.com")
    headers_b = _auth_headers(client, email="bob@example.com")
    course_id = _create_course(client, headers_a).json()["id"]

    resp = client.delete(f"/courses/{course_id}", headers=headers_b)

    assert resp.status_code == 404


def test_scheme_versions_increment_and_are_appended(client):
    headers = _auth_headers(client)
    course_id = _create_course(client, headers).json()["id"]

    v1 = client.post(
        f"/courses/{course_id}/schemes",
        json={"content": "Q1: ... 10 marks", "special_instructions": None, "selection_rule": None},
        headers=headers,
    )
    v2 = client.post(
        f"/courses/{course_id}/schemes",
        json={"content": "Q1: revised ... 10 marks"},
        headers=headers,
    )

    assert v1.status_code == 201
    assert v1.json()["version"] == 1
    assert v2.status_code == 201
    assert v2.json()["version"] == 2

    listing = client.get(f"/courses/{course_id}/schemes", headers=headers)
    assert listing.status_code == 200
    versions = [s["version"] for s in listing.json()]
    assert versions == [1, 2]
    assert listing.json()[0]["content"] == "Q1: ... 10 marks"
    assert listing.json()[1]["content"] == "Q1: revised ... 10 marks"


def test_scheme_endpoints_respect_ownership(client):
    headers_a = _auth_headers(client, email="alice@example.com")
    headers_b = _auth_headers(client, email="bob@example.com")
    course_id = _create_course(client, headers_a).json()["id"]

    post_resp = client.post(
        f"/courses/{course_id}/schemes", json={"content": "sneaky"}, headers=headers_b
    )
    get_resp = client.get(f"/courses/{course_id}/schemes", headers=headers_b)

    assert post_resp.status_code == 404
    assert get_resp.status_code == 404
