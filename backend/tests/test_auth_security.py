import io

from PIL import Image


def test_first_user_is_admin(client, admin_headers):
    me = client.get("/api/auth/me", headers=admin_headers).json()
    assert me["role"] == "admin"


def test_login_and_wrong_password(client, user_headers):
    assert client.post("/api/auth/login", json={"email": "user@example.com", "password": "errada123"}).status_code == 401
    r = client.post("/api/auth/login", json={"email": "user@example.com", "password": "Senha12345"})
    assert r.status_code == 200 and r.json()["user"]["role"] == "user"


def test_weak_password_rejected(client):
    r = client.post("/api/auth/register", json={"name": "X", "email": "weak@example.com", "password": "123"})
    assert r.status_code == 422


def test_protected_routes(client, user_headers):
    assert client.get("/api/projects").status_code == 401
    assert client.get("/api/admin/overview", headers=user_headers).status_code == 403


def test_password_change_invalidates_old_token(client):
    r = client.post("/api/auth/register", json={"name": "Troca", "email": "troca@example.com", "password": "Senha12345"})
    old = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = client.post("/api/auth/change-password", headers=old, json={"current_password": "Senha12345", "new_password": "Nova12345"})
    assert r.status_code == 200
    assert client.get("/api/auth/me", headers=old).status_code == 401


def test_upload_rejects_fake_image(client, user_headers):
    r = client.post("/api/assets", headers=user_headers, data={"kind": "image"},
                    files={"file": ("x.png", b"<?php echo 1; ?>", "image/png")})
    assert r.status_code == 422


def test_upload_rejects_executable_extension(client, user_headers):
    r = client.post("/api/assets", headers=user_headers, data={"kind": "image"},
                    files={"file": ("x.sh", b"#!/bin/sh\necho hi", "text/plain")})
    assert r.status_code == 422


def test_upload_image_is_reencoded_and_signed(client, user_headers):
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (200, 30, 30)).save(buf, "PNG")
    r = client.post("/api/assets", headers=user_headers, data={"kind": "image"},
                    files={"file": ("foto.png", buf.getvalue(), "image/png")})
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["mime"] == "image/jpeg" and a["width"] == 64
    media = client.get(a["url"])
    assert media.status_code == 200 and media.headers["x-content-type-options"] == "nosniff"
    assert client.get(a["url"].replace("sig=", "sig=0")).status_code == 403
