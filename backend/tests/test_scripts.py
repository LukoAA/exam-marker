import io

import cv2
import numpy as np
import pytest
from PIL import Image

from app.main import app
from app.models import MarkingReport
from app.storage import LocalStorageService, get_storage_service


def _make_test_pdf_bytes() -> bytes:
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


def _create_batch_with_script(client, headers, name="Midterm Batch"):
    course, scheme = _create_course_and_scheme(client, headers)
    batch_id = client.post(
        "/batches",
        json={"course_id": course["id"], "scheme_id": scheme["id"], "name": name},
        headers=headers,
    ).json()["id"]
    pdf_bytes = _make_test_pdf_bytes()
    scripts = client.post(
        f"/batches/{batch_id}/scripts",
        files=[("files", ("script1.pdf", pdf_bytes, "application/pdf"))],
        headers=headers,
    ).json()
    return batch_id, scripts[0]["id"]


def test_get_script_detail_before_marking(client_with_storage):
    client = client_with_storage
    headers = _auth_headers(client)
    _batch_id, script_id = _create_batch_with_script(client, headers)

    resp = client.get(f"/scripts/{script_id}", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == script_id
    assert body["status"] == "queued"
    assert body["page_count"] == 1
    assert body["student_name"] is None
    assert body["matric_number"] is None
    assert body["latest_report"] is None


def test_get_script_detail_includes_latest_report(client_with_storage, db_session):
    client = client_with_storage
    headers = _auth_headers(client)
    _batch_id, script_id = _create_batch_with_script(client, headers)

    older = MarkingReport(
        script_id=script_id,
        report_json={"total_awarded": 5, "total_possible": 10},
        transcription="older transcription",
        human_readable="older summary",
    )
    newer = MarkingReport(
        script_id=script_id,
        report_json={"total_awarded": 8, "total_possible": 10},
        transcription="newer transcription",
        human_readable="newer summary",
    )
    db_session.add(older)
    db_session.commit()
    db_session.add(newer)
    db_session.commit()

    resp = client.get(f"/scripts/{script_id}", headers=headers)

    assert resp.status_code == 200
    latest_report = resp.json()["latest_report"]
    assert latest_report is not None
    assert latest_report["report_json"]["total_awarded"] == 8
    assert latest_report["human_readable"] == "newer summary"


def test_get_script_not_found(client):
    headers = _auth_headers(client)

    resp = client.get("/scripts/999", headers=headers)

    assert resp.status_code == 404


def test_get_script_not_owner_returns_404(client_with_storage):
    client = client_with_storage
    headers_a = _auth_headers(client, email="alice@example.com")
    headers_b = _auth_headers(client, email="bob@example.com")
    _batch_id, script_id = _create_batch_with_script(client, headers_a)

    resp = client.get(f"/scripts/{script_id}", headers=headers_b)

    assert resp.status_code == 404


def test_get_script_page_image(client_with_storage):
    client = client_with_storage
    headers = _auth_headers(client)
    _batch_id, script_id = _create_batch_with_script(client, headers)

    resp = client.get(f"/scripts/{script_id}/pages/1.png", headers=headers)

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert len(resp.content) > 0
    # a real PNG starts with this 8-byte signature
    assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_get_script_page_missing_page_number_returns_404(client_with_storage):
    client = client_with_storage
    headers = _auth_headers(client)
    _batch_id, script_id = _create_batch_with_script(client, headers)

    resp = client.get(f"/scripts/{script_id}/pages/99.png", headers=headers)

    assert resp.status_code == 404


def test_get_script_page_not_owner_returns_404(client_with_storage):
    client = client_with_storage
    headers_a = _auth_headers(client, email="alice@example.com")
    headers_b = _auth_headers(client, email="bob@example.com")
    _batch_id, script_id = _create_batch_with_script(client, headers_a)

    resp = client.get(f"/scripts/{script_id}/pages/1.png", headers=headers_b)

    assert resp.status_code == 404
