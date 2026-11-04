import json
import subprocess

from app.video import timeline as tl

COMPANY = {"name": "Bella Napoli", "segment": "Pizzaria", "description": "Pizzaria artesanal com forno a lenha.",
           "product": "Pizza grande", "offer": "R$ 49,90 às terças", "differentials": "forno a lenha, massa natural",
           "whatsapp": "(19) 98765-4321", "instagram": "bellanapoli"}


def _create(client, headers, **settings):
    tpl = client.get("/api/templates?category=pizzarias", headers=headers).json()["items"][0]
    r = client.post("/api/projects", headers=headers, json={"template_id": tpl["id"], "company": COMPANY,
                                                            "settings": {"duration": 15, **settings}})
    assert r.status_code == 201, r.text
    return r.json()


def test_templates_catalog(client, user_headers):
    data = client.get("/api/templates", headers=user_headers).json()
    assert len(data["categories"]) == 13
    assert len(data["items"]) >= 36


def test_full_flow_script_edit_render(client, user_headers):
    p = _create(client, user_headers, quality="720p")
    job = client.post(f"/api/projects/{p['id']}/script", headers=user_headers).json()
    assert job["status"] == "completed", job
    p = client.get(f"/api/projects/{p['id']}", headers=user_headers).json()
    assert p["status"] == "ready" and len(p["scenes"]) >= 3
    sid = p["scenes"][0]["id"]
    r = client.patch(f"/api/projects/{p['id']}/scenes/{sid}", headers=user_headers,
                     json={"title": "Título editado", "duration": 4, "transition": "slideleft"})
    assert r.status_code == 200 and r.json()["title"] == "Título editado"
    ids = [s["id"] for s in p["scenes"]][::-1]
    r = client.post(f"/api/projects/{p['id']}/scenes/reorder", headers=user_headers, json={"scene_ids": ids})
    assert [s["id"] for s in r.json()["scenes"]] == ids
    tlj = client.get(f"/api/projects/{p['id']}/timeline", headers=user_headers).json()
    assert tlj["total"] > 0
    job = client.post(f"/api/projects/{p['id']}/preview", headers=user_headers).json()
    assert job["status"] == "completed", job
    p = client.get(f"/api/projects/{p['id']}", headers=user_headers).json()
    assert p["preview"] and p["preview"]["kind"] == "video"
    video = client.get(p["preview"]["url"])
    assert video.status_code == 200 and len(video.content) > 10_000
    info = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", "-"],
                          input=video.content, capture_output=True)
    meta = json.loads(info.stdout)
    kinds = {s["codec_type"] for s in meta["streams"]}
    assert kinds == {"video", "audio"}
    assert abs(float(meta["format"]["duration"]) - 15) < 2.5


def test_ownership_isolation(client, user_headers, other_headers):
    p = _create(client, user_headers)
    assert client.get(f"/api/projects/{p['id']}", headers=other_headers).status_code == 404
    assert client.delete(f"/api/projects/{p['id']}", headers=other_headers).status_code == 404
    assert client.post(f"/api/projects/{p['id']}/render", headers=other_headers).status_code == 404


def test_duplicate_export_delete(client, user_headers):
    p = _create(client, user_headers)
    client.post(f"/api/projects/{p['id']}/script", headers=user_headers)
    dup = client.post(f"/api/projects/{p['id']}/duplicate", headers=user_headers).json()
    assert dup["id"] != p["id"] and len(dup["scenes"]) > 0
    z = client.get(f"/api/projects/{p['id']}/export", headers=user_headers)
    assert z.status_code == 200 and z.headers["content-type"] == "application/zip"
    imp = client.post("/api/projects/import", headers=user_headers, files={"file": ("p.zip", z.content, "application/zip")})
    assert imp.status_code == 201, imp.text
    assert len(imp.json()["scenes"]) == len(dup["scenes"])
    assert client.delete(f"/api/projects/{p['id']}", headers=user_headers).status_code == 204
    assert client.get(f"/api/projects/{dup['id']}", headers=user_headers).status_code == 200


def test_invalid_settings_rejected(client, user_headers):
    p = _create(client, user_headers)
    r = client.patch(f"/api/projects/{p['id']}", headers=user_headers, json={"settings": {"duration": 17}})
    assert r.status_code == 422
    r = client.patch(f"/api/projects/{p['id']}", headers=user_headers, json={"settings": {"palette": ["red"]}})
    assert r.status_code == 422


def test_dashboard_reflects_real_data(client, user_headers):
    d = client.get("/api/dashboard", headers=user_headers).json()
    assert d["projects_total"] >= 3 and d["templates_available"] >= 36


def test_admin_endpoints(client, admin_headers):
    assert client.get("/api/admin/overview", headers=admin_headers).status_code == 200
    assert client.get("/api/admin/users", headers=admin_headers).status_code == 200
    r = client.put("/api/admin/settings/storage", headers=admin_headers, json={"values": {"max_image_upload_mb": 20}})
    assert r.status_code == 200 and r.json()["max_image_upload_mb"] == 20


def test_timeline_fit_to_target():
    scenes = [tl.SceneIn(str(i), 3, "fade", "texto", "", 5.0) for i in range(4)]
    t = tl.compute(scenes, target=15, fit=True, narration_enabled=True, subtitles_enabled=True, end_card_duration=3)
    assert t.tempo > 1.0
    assert all(s.captions for s in t.scenes)
    t2 = tl.compute([tl.SceneIn("a", 2, "fade")], target=30, fit=True, narration_enabled=False,
                    subtitles_enabled=False, end_card_duration=4)
    assert abs(t2.total - 30) < 0.01
