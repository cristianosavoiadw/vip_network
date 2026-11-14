"""Images in the bucket: <company-slug>/<kind>/<uuid>.webp (owner decision 2026-11-14)."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.modules.auth import service as auth
from tests.conftest import PASSWORD, World


@pytest.fixture
def local_storage(tmp_path, monkeypatch: pytest.MonkeyPatch):  # noqa: ANN001, ANN201
    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path))
    monkeypatch.setattr(get_settings(), "s3_endpoint", "")
    return tmp_path


def _png(w: int = 1200, h: int = 900) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (w, h), (201, 161, 74)).save(out, format="PNG")
    return out.getvalue()


async def test_company_logo_goes_to_its_folder_as_webp(world: World, local_storage) -> None:  # noqa: ANN001
    c = await world.register()  # also during sign-up
    r = await world.client.post(
        "/api/v1/media/images?kind=logo",
        headers=c.h,
        files={"file": ("logo.png", _png(), "image/png")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["key"].startswith(f"{c.slug}/logo/") and body["key"].endswith(".webp")
    assert body["url"] == f"/api/v1/media/{body['key']}"
    assert (local_storage / body["key"]).is_file()
    got = await world.client.get(body["url"])
    assert got.status_code == 200 and got.headers["content-type"] == "image/webp"
    img = Image.open(io.BytesIO(got.content))
    assert max(img.size) <= 512
    # the profile keeps the URL
    r = await world.client.patch(
        "/api/v1/organizations/me", headers=c.h, json={"logo_url": body["url"]}
    )
    assert r.json()["logo_url"] == body["url"]


async def test_rejects_non_images_and_bad_kind(world: World, local_storage) -> None:  # noqa: ANN001
    c = await world.register()
    r = await world.client.post(
        "/api/v1/media/images?kind=logo",
        headers=c.h,
        files={"file": ("x.png", b"not an image", "image/png")},
    )
    assert r.json()["code"] == "file_type"
    r = await world.client.post(
        "/api/v1/media/images?kind=other",
        headers=c.h,
        files={"file": ("x.png", _png(), "image/png")},
    )
    assert r.json()["code"] == "image_kind"
    assert (await world.client.get("/api/v1/media/../etc/passwd")).status_code == 404


async def test_platform_images_by_the_team(world: World, local_storage) -> None:  # noqa: ANN001
    email = world.email()
    async with SessionLocal() as s:
        await auth.create_user(s, email=email, password=PASSWORD, kind="admin", admin_role="owner")
        await s.commit()
    token = (
        await world.client.post(
            "/api/v1/auth/admin/login", json={"email": email, "password": PASSWORD}
        )
    ).json()["access_token"]
    r = await world.client.post(
        "/api/v1/admin/media/images?kind=event",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("jantar.jpg", _png(), "image/png")},
    )
    assert r.status_code == 200 and r.json()["key"].startswith("vip-network/event/")
    c = await world.register()
    r = await world.client.post(
        "/api/v1/admin/media/images?kind=event",
        headers=c.h,
        files={"file": ("x.png", _png(), "image/png")},
    )
    assert r.status_code == 403


async def test_company_presentation_pdf_is_on_the_public_profile(
    world: World, local_storage
) -> None:  # noqa: ANN001
    from app.modules.admin.demo_pdf import presentation_pdf

    a = await world.active_company()
    b = await world.active_company()
    pdf = presentation_pdf(
        "Empresa A", "Embalagens", "São Paulo", "Fabricamos embalagens.", ["Caixas"]
    )
    r = await world.client.post(
        "/api/v1/media/presentation",
        headers=a.h,
        files={"file": ("Apresentação Empresa A.pdf", pdf, "application/pdf")},
    )
    assert r.status_code == 200, r.text
    info = r.json()
    assert info["name"] == "Apresentação Empresa A.pdf" and info["size"] == len(pdf)
    assert info["url"].startswith(f"/api/v1/media/{a.slug}/apresentacao/")
    got = await world.client.get(info["url"])
    assert got.status_code == 200 and got.content == pdf
    assert got.headers["content-type"] == "application/pdf"
    # another company sees it on the profile
    page = (await world.client.get(f"/api/v1/companies/{a.slug}", headers=b.h)).json()
    assert page["org"]["presentation"]["url"] == info["url"]
    # only PDF
    bad = await world.client.post(
        "/api/v1/media/presentation",
        headers=a.h,
        files={"file": ("x.pdf", b"PK zip", "application/pdf")},
    )
    assert bad.json()["code"] == "file_type"
    # removal clears the profile and the file
    await world.client.delete("/api/v1/media/presentation", headers=a.h)
    page = (await world.client.get(f"/api/v1/companies/{a.slug}", headers=b.h)).json()
    assert page["org"]["presentation"] is None
    assert (await world.client.get(info["url"])).status_code == 404
