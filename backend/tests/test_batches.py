import io

import cv2
import numpy as np
import pytest
from PIL import Image

from app.main import app
from app.storage import LocalStorageService, get_storage_service


def _make_test_pdf_bytes() -> bytes:
    """A tiny single-page PDF with alternating dark/light bars, enough for
    preprocess.py's rotation/deskew row-projection heuristics to run on."""
    width, height = 300, 400
    image = np.full((height, width, 3), 255, dtype=np.uint8)
    y = 20
    while y + 12 < height - 20:
        cv2.rectangle(image, (20, y), (width - 20, y + 12), (0, 0, 0), thickness=-1)
        y += 22
    pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    buffer = io.BytesIO()
    pil_image.save(buffer, "PDF")
    return buffer.getvalue()


@pytest.fixture()
def client_with_storage(client, tmp_path):
    app.dependency_overrides[get_storage_service] = lambda: LocalStorageService(root=tmp_path)
    yield client


def _auth_headers(client, email="jane@example.com", password="hunter22", name="Jane Doe"):
    client.post("/auth/register", json={"email": email, "password": password, "name": name})
    token = client.post(
        "/auth/login", json={"email": email, "password": password}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_course_and_scheme(client, headers, code="CSC301"):
    course = client.post(
        "/courses",
        json={
            "code": code,
            "title": "Operating Systems",
            "total_marks": 100,
            "grading_scale": {"A": [70, 100], "F": [0, 39]},
            "language": "English",
        },
        headers=headers,
    ).json()
    scheme = client.post(
        f"/courses/{course['id']}/schemes",
        json={"content": "Q1: ... 10 marks"},
        headers=headers,
    ).json()
    return course, scheme


def _create_batch(client, headers, course_id, scheme_id, name="Midterm Batch"):
    return client.post(
        "/batches",
        json={"course_id": course_id, "scheme_id": scheme_id, "name": name},
        headers=headers,
    )


def test_create_batch_success(client):
    headers = _auth_headers(client)
    course, scheme = _create_course_and_scheme(client, headers)

    resp = _create_batch(client, headers, course["id"], scheme["id"])

    assert resp.status_code == 201
    body = resp.json()
    assert body["course_id"] == course["id"]
    assert body["scheme_id"] == scheme["id"]
    assert body["name"] == "Midterm Batch"
    assert body["status"] == "pending"


def test_create_batch_requires_auth(client):
    resp = client.post(
        "/batches", json={"course_id": 1, "scheme_id": 1, "name": "x"}, headers={}
    )

    assert resp.status_code == 401


def test_create_batch_rejects_course_not_owned(client):
    headers_a = _auth_headers(client, email="alice@example.com")
    headers_b = _auth_headers(client, email="bob@example.com")
    course, scheme = _create_course_and_scheme(client, headers_a)

    resp = _create_batch(client, headers_b, course["id"], scheme["id"])

    assert resp.status_code == 404


def test_create_batch_rejects_scheme_from_another_course(client):
    headers = _auth_headers(client)
    course_1, _scheme_1 = _create_course_and_scheme(client, headers, code="CSC301")
    course_2, scheme_2 = _create_course_and_scheme(client, headers, code="MTH201")

    # scheme_2 belongs to course_2, not course_1
    resp = _create_batch(client, headers, course_1["id"], scheme_2["id"])

    assert resp.status_code == 404


def test_list_batches_for_course(client):
    headers = _auth_headers(client)
    course, scheme = _create_course_and_scheme(client, headers)
    batch_1 = _create_batch(client, headers, course["id"], scheme["id"], name="Midterm").json()
    batch_2 = _create_batch(client, headers, course["id"], scheme["id"], name="Final").json()

    resp = client.get(f"/batches?course_id={course['id']}", headers=headers)

    assert resp.status_code == 200
    ids = [b["id"] for b in resp.json()]
    assert ids == [batch_1["id"], batch_2["id"]]


def test_list_batches_excludes_other_courses(client):
    headers = _auth_headers(client)
    course_1, scheme_1 = _create_course_and_scheme(client, headers, code="CSC301")
    course_2, scheme_2 = _create_course_and_scheme(client, headers, code="MTH201")
    _create_batch(client, headers, course_1["id"], scheme_1["id"], name="CSC batch")
    _create_batch(client, headers, course_2["id"], scheme_2["id"], name="MTH batch")

    resp = client.get(f"/batches?course_id={course_1['id']}", headers=headers)

    assert resp.status_code == 200
    names = [b["name"] for b in resp.json()]
    assert names == ["CSC batch"]


def test_list_batches_rejects_course_not_owned(client):
    headers_a = _auth_headers(client, email="alice@example.com")
    headers_b = _auth_headers(client, email="bob@example.com")
    course, _scheme = _create_course_and_scheme(client, headers_a)

    resp = client.get(f"/batches?course_id={course['id']}", headers=headers_b)

    assert resp.status_code == 404


def test_get_batch_not_owner_returns_404(client):
    headers_a = _auth_headers(client, email="alice@example.com")
    headers_b = _auth_headers(client, email="bob@example.com")
    course, scheme = _create_course_and_scheme(client, headers_a)
    batch_id = _create_batch(client, headers_a, course["id"], scheme["id"]).json()["id"]

    resp = client.get(f"/batches/{batch_id}", headers=headers_b)

    assert resp.status_code == 404


def test_upload_pdf_creates_script_and_pages(client_with_storage, tmp_path):
    client = client_with_storage
    headers = _auth_headers(client)
    course, scheme = _create_course_and_scheme(client, headers)
    batch_id = _create_batch(client, headers, course["id"], scheme["id"]).json()["id"]
    pdf_bytes = _make_test_pdf_bytes()

    # Genuine multipart upload: a real (filename, bytes, content_type) file part,
    # not a plain form field — this is what a browser file <input> or FastAPI's
    # own Swagger "Try it out" sends for a `list[UploadFile] = File(...)` param.
    resp = client.post(
        f"/batches/{batch_id}/scripts",
        files=[("files", ("script1.pdf", pdf_bytes, "application/pdf"))],
        headers=headers,
    )

    assert resp.status_code == 201
    scripts = resp.json()
    assert len(scripts) == 1
    script = scripts[0]
    assert script["original_filename"] == "script1.pdf"
    assert script["status"] == "queued"
    assert script["page_count"] == 1

    script_dir = tmp_path / "batches" / str(batch_id) / "scripts" / str(script["id"])
    original_pdf_path = script_dir / "original.pdf"
    page_1_path = script_dir / "pages" / "1.png"
    assert original_pdf_path.is_file()
    assert original_pdf_path.read_bytes() == pdf_bytes
    assert page_1_path.is_file()
    assert page_1_path.stat().st_size > 0

    detail = client.get(f"/batches/{batch_id}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["status"] == "pending"
    assert len(body["scripts"]) == 1
    assert body["scripts"][0]["page_count"] == 1


def test_upload_multiple_pdfs_creates_multiple_scripts(client_with_storage):
    client = client_with_storage
    headers = _auth_headers(client)
    course, scheme = _create_course_and_scheme(client, headers)
    batch_id = _create_batch(client, headers, course["id"], scheme["id"]).json()["id"]
    pdf_bytes = _make_test_pdf_bytes()

    resp = client.post(
        f"/batches/{batch_id}/scripts",
        files=[
            ("files", ("script1.pdf", pdf_bytes, "application/pdf")),
            ("files", ("script2.pdf", pdf_bytes, "application/pdf")),
        ],
        headers=headers,
    )

    assert resp.status_code == 201
    filenames = {s["original_filename"] for s in resp.json()}
    assert filenames == {"script1.pdf", "script2.pdf"}


def test_upload_rejects_non_pdf_file(client_with_storage):
    client = client_with_storage
    headers = _auth_headers(client)
    course, scheme = _create_course_and_scheme(client, headers)
    batch_id = _create_batch(client, headers, course["id"], scheme["id"]).json()["id"]

    resp = client.post(
        f"/batches/{batch_id}/scripts",
        files=[("files", ("notes.txt", b"not a pdf", "text/plain"))],
        headers=headers,
    )

    assert resp.status_code == 400


def test_upload_requires_batch_ownership(client_with_storage):
    client = client_with_storage
    headers_a = _auth_headers(client, email="alice@example.com")
    headers_b = _auth_headers(client, email="bob@example.com")
    course, scheme = _create_course_and_scheme(client, headers_a)
    batch_id = _create_batch(client, headers_a, course["id"], scheme["id"]).json()["id"]
    pdf_bytes = _make_test_pdf_bytes()

    resp = client.post(
        f"/batches/{batch_id}/scripts",
        files=[("files", ("script1.pdf", pdf_bytes, "application/pdf"))],
        headers=headers_b,
    )

    assert resp.status_code == 404
