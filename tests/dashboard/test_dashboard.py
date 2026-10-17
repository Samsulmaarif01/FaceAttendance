"""Menjaga dashboard (HTML/CSS/JS polos, tanpa build step) tetap konsisten.

Tidak ada bundler atau linter di repo ini, jadi tidak ada yang memvalidasi
hubungan CSS <-> markup. Bug yang pernah lolos ke produksi:

    index.html : <img id="match-avatar-photo" alt="" hidden />   # tanpa class
    style.css  : .match-avatar-photo { position: absolute; ... } # selector class

Aturan itu tidak pernah berlaku, sehingga foto profil di kartu kiosk tampil
mentah seukuran aslinya. Tes di bawah menangkap kelas CSS yang tidak pernah
dipasang dan ID CSS yang tidak ada di markup.
"""

import re
from pathlib import Path

import pytest

DASHBOARD = Path(__file__).resolve().parents[2] / "src" / "dashboard"
HTML_PATH = DASHBOARD / "index.html"
CSS_PATH = DASHBOARD / "static" / "style.css"
JS_PATH = DASHBOARD / "static" / "app.js"

# Kelas "tone" yang dirangkai dari variabel di JS, mis. `"badge " + cls` atau
# `setStatus(msg, "err")`, sehingga tidak pernah muncul sebagai literal penuh.
DYNAMIC_CLASSES = {"demo", "err", "error", "info", "ok"}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _strip_css_noise(css: str) -> str:
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"url\([^)]*\)", "", css)
    return css[css.find("{"):] if "{" in css else css


def _is_hex_color(token: str) -> bool:
    return len(token) in (3, 4, 6, 8) and all(c in "0123456789abcdefABCDEF" for c in token)


def css_classes(css: str) -> set:
    return set(re.findall(r"\.([A-Za-z][\w-]*)", _strip_css_noise(css)))


def css_ids(css: str) -> set:
    return {
        token
        for token in re.findall(r"#([A-Za-z][\w-]*)", _strip_css_noise(css))
        if not _is_hex_color(token)
    }


def applied_classes(html: str, js: str) -> set:
    """Kelas yang benar-benar dipasang ke elemen."""
    used = set()
    for source in (html, js):
        # class="a b c" di markup maupun di template string JS
        for match in re.finditer(r"""class\s*=\s*["']([^"']*)["']""", source):
            used.update(match.group(1).split())
        # className = "badge"  /  className = "badge " + cls
        for match in re.finditer(r"""className\s*=\s*["']([^"']*)["']""", source):
            used.update(match.group(1).split())
    # classList.add("a", "b") / toggle(...) / remove(...) / contains(...)
    for match in re.finditer(r"classList\.(?:add|remove|toggle|contains)\(([^)]*)\)", js):
        used.update(re.findall(r"""["']([\w-]+)["']""", match.group(1)))
    return used


@pytest.fixture(scope="module")
def sources():
    for path in (HTML_PATH, CSS_PATH, JS_PATH):
        if not path.is_file():
            pytest.fail(f"aset dashboard hilang: {path}")
    return _read(HTML_PATH), _read(CSS_PATH), _read(JS_PATH)


def test_every_css_class_is_actually_applied(sources):
    """Kelas CSS yang tidak pernah dipasang = aturan mati (dan bug tampilan)."""
    html, css, js = sources
    used = applied_classes(html, js) | DYNAMIC_CLASSES
    dead = sorted(css_classes(css) - used)
    assert dead == [], (
        "Kelas CSS ini tidak pernah dipasang ke elemen mana pun "
        f"(selektornya tidak akan berlaku): {dead}"
    )


def test_every_css_id_exists_in_the_markup(sources):
    """ID CSS yang tidak ada di markup = salah ketik / sisa layout lama."""
    html, css, _ = sources
    markup_ids = set(re.findall(r"""id=["']([\w-]+)["']""", html))
    missing = sorted(css_ids(css) - markup_ids)
    assert missing == [], f"ID CSS tanpa elemen di index.html: {missing}"


def test_avatar_photo_is_an_id_selector_not_a_class(sources):
    """Regresi langsung: elemen avatar hanya punya id, jadi wajib distyling #id."""
    html, css, _ = sources
    tag = re.search(r"<img[^>]*match-avatar-photo[^>]*>", html)
    assert tag is not None, "elemen #match-avatar-photo tidak ditemukan"
    assert "class=" not in tag.group(0), (
        "elemen avatar tidak punya atribut class, jadi jangan distyling "
        "dengan selector class"
    )
    assert re.search(r"#match-avatar-photo\s*\{[^}]*object-fit:\s*cover", css), (
        "aturan #match-avatar-photo (posisi + object-fit) tidak ditemukan"
    )


def test_stop_camera_clears_overlay_and_timer(sources):
    """Memastikan stopCamera membersihkan kanvas overlay, timer loop, dan status tracking."""
    _, _, js = sources
    assert "function clearOverlay()" in js, "fungsi clearOverlay() tidak ditemukan"
    stop_cam_match = re.search(r"function stopCamera\(\)\s*\{([\s\S]*?)\n\}\n", js)
    assert stop_cam_match is not None, "fungsi stopCamera() tidak ditemukan"
    body = stop_cam_match.group(1)
    assert "clearOverlay()" in body, "stopCamera harus memanggil clearOverlay() agar tracking tidak nyangkut"
    assert "clearInterval(loopTimer)" in body, "stopCamera harus mematikan loopTimer"
    assert "setTracking(false)" in body, "stopCamera harus mereset tracking stage"


def test_fullscreen_mode_moves_toast_to_bottom_and_removes_switch_camera(sources):
    """Memastikan tombol kamera switch dihapus, fullscreen button aktif, dan toast diatur di bawah saat fullscreen."""
    html, css, js = sources
    assert "btn-switch" not in html, "ikon / tombol ganti kamera seharusnya sudah dihapus dari HTML"
    assert "btn-switch" not in js, "referensi btn-switch seharusnya sudah dihapus dari JS"
    assert "btn-fullscreen" in html, "tombol fullscreen harus ada di markup"
    assert "is-fullscreen" in css, "aturan CSS is-fullscreen harus ada"
    assert re.search(r"\.stage(?::fullscreen|\.is-fullscreen)[\s\S]*?\.toast\s*\{[^}]*bottom:\s*24px", css), (
        "toast harus diposisikan di bagian bawah saat fullscreen"
    )


def test_enroll_modal_kiosk_dialog(sources):
    """Memastikan dialog pendaftaran wajah mandiri (modal kiosk) tersedia dan terhubung lengkap."""
    html, css, js = sources
    assert 'id="dlg-enroll"' in html, "modal #dlg-enroll harus ada di index.html"
    assert 'id="enroll-video"' in html, "video kamera pendaftaran harus ada"
    assert 'id="btn-enroll-snap"' in html, "tombol ambil foto harus ada"
    assert 'id="btn-enroll-save"' in html, "tombol simpan foto harus ada"
    assert 'id="btn-enroll-retake"' in html, "tombol ambil ulang harus ada"
    assert "openEnrollModal" in js, "fungsi openEnrollModal harus ada di app.js"
    assert "closeEnrollModal" in js, "fungsi closeEnrollModal harus ada di app.js"
    assert "snapEnrollPhoto" in js, "fungsi snapEnrollPhoto harus ada di app.js"
    assert ".dlg-enroll" in css, "aturan CSS .dlg-enroll harus ada"
    assert ".enroll-stage" in css, "aturan CSS .enroll-stage harus ada"



