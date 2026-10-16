"use strict";

const $ = (id) => document.getElementById(id);

const video = $("video");
const photo = $("photo");
const overlay = $("overlay");
const capture = $("capture");
const toastEl = $("toast");
const stageEl = document.querySelector(".stage");

let stream = null;
let loopTimer = null;
let loopBusy = false;
let frameW = 0;
let frameH = 0;
let userMap = {}; // id -> { name, count }
let mode = null; // null = not chosen yet (no attendance is written); "in" | "out"
const DIR = { in: "masuk", out: "pulang" };
const DIR_TITLE = { in: "Masuk", out: "Pulang" };
const CAMERA_WIDTH = 640;   // see PipelineConfig.detection_working_size
const CAMERA_HEIGHT = 480;

/* ── Small helpers ─────────────────────────────────────────── */
function setStatus(msg, type) {
  const el = $("status");
  el.textContent = msg;
  el.className = "status" + (type ? " " + type : "");
}

function setBadge(text, cls) {
  const b = $("badge");
  b.textContent = text;
  b.className = "badge" + (cls ? " " + cls : "");
}

async function fetchJSON(url, options) {
  const res = await fetch(url, options);
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  return res.json();
}

const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const initials = (s) => String(s || "?").trim().split(/\s+/).slice(0, 2).map((w) => w[0]).join("").toUpperCase() || "?";

// Attendance timestamps are stored as naive UTC ISO strings; render them in the
// viewer's local time so they match the on-screen clock.
function toLocalDate(iso) {
  if (!iso) return null;
  const s = String(iso);
  const d = new Date(/[Z+]/.test(s.slice(10)) ? s : s + "Z");
  return isNaN(d.getTime()) ? null : d;
}

function fmtTime(iso) {
  const d = toLocalDate(iso);
  if (!d) return iso ? String(iso).slice(0, 19).replace("T", " ") : "—";
  const p = (n) => String(n).padStart(2, "0");
  return `${p(d.getDate())}/${p(d.getMonth() + 1)}/${d.getFullYear()} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

function fmtClock(iso) {
  const d = toLocalDate(iso);
  if (!d) return "—";
  const p = (n) => String(n).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())}`;
}

function greetWord() {
  const h = new Date().getHours();
  if (h < 11) return "Selamat Pagi";
  if (h < 15) return "Selamat Siang";
  if (h < 19) return "Selamat Sore";
  return "Selamat Malam";
}

/* ── Theme (dark / light) ──────────────────────────────────── */
function currentTheme() {
  return document.documentElement.classList.contains("light") ? "light" : "dark";
}

function applyTheme(mode) {
  document.documentElement.classList.toggle("light", mode === "light");
  try { localStorage.setItem("vf-theme", mode); } catch (_) {}
  const use = document.querySelector("#btn-theme use");
  if (use) use.setAttribute("href", mode === "light" ? "#i-sun" : "#i-moon");
  const btn = $("btn-theme");
  if (btn) btn.title = mode === "light" ? "Aktifkan tema gelap" : "Aktifkan tema terang";
}

/* ── Toast ─────────────────────────────────────────────────── */
let toastTimer = null;
function showToast(title, sub, type, ms) {
  $("toast-title").textContent = title;
  $("toast-sub").textContent = sub || "";
  $("toast-icon").textContent = type === "err" ? "!" : type === "info" ? "i" : "✓";
  toastEl.className = "toast" + (type ? " " + type : "");
  toastEl.hidden = false;
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toastEl.hidden = true; }, ms || (type === "err" ? 6000 : 3500));
}

const lastStatusByUser = {};

/* Keadaan "sedang di frame". Digunakan agar pesan (mis. "sudah tercatat")
   hanya diulang ketika orang benar-benar KELUAR lalu masuk lagi — bukan
   setiap frame selama dia tetap berdiri di depan kamera. */
const presentUsers = new Map(); // user_id -> waktu terakhir terdeteksi
const PRESENCE_GRACE_MS = 3000;  // toleransi berkedip / frame gagal deteksi

function updatePresence(matchedIds) {
  const now = Date.now();
  for (const [uid, seenAt] of [...presentUsers]) {
    if (matchedIds.has(uid)) { presentUsers.set(uid, now); continue; }
    // Baru dianggap keluar setelah grace period, supaya kedip atau satu frame
    // gagal deteksi tidak memicu ulang pesan.
    if (now - seenAt > PRESENCE_GRACE_MS) {
      presentUsers.delete(uid);
      delete lastStatusByUser[uid]; // kalau datang lagi, pesan ditampilkan lagi
    }
  }
  for (const uid of matchedIds) {
    if (!presentUsers.has(uid)) presentUsers.set(uid, now);
  }
}

function clearPresence() {
  presentUsers.clear();
  Object.keys(lastStatusByUser).forEach((k) => delete lastStatusByUser[k]);
  lastAttendanceKey = "";
}

/* Deteksi perubahan status attendance agar tabel/statistik tidak di-refresh
   pada setiap frame — hanya saat status benar-benar berubah. */
let lastAttendanceKey = "";
function attendanceChanged(matched) {
  const key = matched
    .map((f) => `${f.match.user_id}:${f.attendance_status}`)
    .sort()
    .join("|");
  if (key === lastAttendanceKey) return false;
  lastAttendanceKey = key;
  return true;
}

function refreshAll() {
  refreshAttendance();
  refreshStats();
  refreshUsers();
}

/* Decide the notification from the server-side attendance outcome, deduped so
   the 700 ms live loop does not repeat the same message. */
function toastForFace(face) {
  const uid = face.match.user_id;
  const name = face.match.name;
  const dir = DIR[face.direction] || "masuk";
  const time = new Date().toLocaleTimeString();
  let status = face.attendance_status;

  if (status === undefined) {
    // Older/uncached server: infer from the boolean flags, and never stay silent.
    if (face.attendance_logged) status = "logged";
    else if (face.attendance_duplicate) status = "duplicate";
    else if (face.direction === "out") status = "not_checked_in";
    else status = "unknown";
  }

  if (status === "logged") {
    showToast(`Absen ${dir} berhasil`, `${name} • ${time}`, "");
    lastStatusByUser[uid] = status;
    return;
  }

  // Non-recording outcomes: tell the user once per state change (no spam).
  if (lastStatusByUser[uid] === status) return;
  lastStatusByUser[uid] = status;

  if (status === "duplicate") {
    // "Sudah absen" adalah kondisi sukses, bukan peringatan: tampilkan
    // centang hijau seperti saat absen dicatat, hanya tidak ditulis ulang.
    const at = face.attendance_duplicate_at ? ` pukul ${fmtClock(face.attendance_duplicate_at)}` : "";
    const gate = face.gate_granted ? " · akses gate tetap diberikan" : "";
    showToast(`Sudah absen ${dir}`, `${name} tercatat${at} — tidak dicatat ulang${gate}`, "");
  } else if (status === "not_checked_in") {
    showToast("Anda belum melakukan presensi masuk", `${name} harus absen masuk dulu sebelum absen pulang`, "err");
  } else if (status === "skipped" || status === "unknown") {
    showToast("Tidak dicatat", `${name} terverifikasi tanpa menulis absensi`, "info");
  }
}

/* ── Navigation ────────────────────────────────────────────── */
function showSection(name) {
  document.querySelectorAll(".section").forEach((s) => { s.hidden = s.dataset.view !== name; });
  document.querySelectorAll("[data-section]").forEach((b) => {
    b.classList.toggle("active", b.dataset.section === name);
  });
}

function wireNav() {
  document.querySelectorAll("[data-section]").forEach((btn) => {
    btn.addEventListener("click", () => showSection(btn.dataset.section));
  });
}

/* ── Clock ─────────────────────────────────────────────────── */
function tickClock() {
  const now = new Date();
  $("clock-time").textContent = now.toLocaleTimeString("id-ID", { hour12: false });
}

/* ── Health ────────────────────────────────────────────────── */
async function loadHealth() {
  try {
    const h = await fetchJSON("/api/health");
    setBadge(h.demo_mode ? "demo mode" : "live models", h.demo_mode ? "demo" : "ok");
    $("node-demo").textContent = h.demo_mode ? "Demo" : "Live";
    $("node-matcher").textContent = (h.matcher_backend || "linear") + " matcher";
    $("node-detector").textContent = h.detector_loaded ? "loaded" : "none";
    $("set-demo").textContent = h.demo_mode ? "Demo (synthetic embeddings)" : "Live (ONNX models)";
    $("set-detector").textContent = h.detector_loaded ? "Loaded (YuNet / SCRFD)" : "Not loaded";
    $("set-matcher").textContent = h.matcher_backend || "—";
    $("set-models").textContent = String(h.recognition_models);
    $("set-sync").textContent = h.sync_enabled ? "Enabled" : "Disabled (offline demo)";
    if (!h.sync_enabled) {
      const btn = $("btn-sync");
      btn.disabled = true;
      btn.title = "Sync is disabled: offline demo has no central server transport.";
      $("sync-note").hidden = false;
    }
  } catch (e) {
    setBadge("offline", "err");
  }
}

/* ── Camera ────────────────────────────────────────────────── */
async function startCamera() {
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      // Batasi resolusi: frame 1080p bikin JPEG 1.5 MB sehingga encode di
      // browser, upload, dan decode di server ikut mahal (~200 ms). 640x480
      // cukup untuk deteksi wajah dan jauh lebih ringan.
      video: {
        width: { ideal: CAMERA_WIDTH },
        height: { ideal: CAMERA_HEIGHT },
        frameRate: { ideal: 30, max: 30 },
      },
      audio: false,
    });
    video.srcObject = stream;
    await video.play();
    photo.hidden = true;
    video.hidden = false;
    $("video-msg").hidden = true;
    $("laser").hidden = false;
    if (stageEl) stageEl.classList.remove("photo-mode");
    setTracking(false);
    clearPresence();
    $("btn-camera").querySelector("span").textContent = "Hentikan Kamera";
    $("vf-sub").textContent = mode === null
      ? "Pilih mode Presensi Masuk / Pulang untuk mencatat absensi"
      : "Pengenalan langsung aktif";
    setStatus(mode === null
      ? "Kamera aktif. Pilih mode Presensi Masuk atau Pulang untuk mulai mencatat absensi."
      : "Kamera aktif. Pengenalan langsung berjalan.", mode === null ? "info" : "ok");
    return true;
  } catch (e) {
    setStatus("Kamera tidak tersedia: " + e.message + " — Anda masih bisa memakai Daftar dari gambar.", "err");
    return false;
  }
}

function stopCamera() {
  if (stream) {
    stream.getTracks().forEach((t) => t.stop());
    stream = null;
  }
  if (photo.hidden) $("video-msg").hidden = false;
  setTracking(false);
  clearPresence();
  $("btn-camera").querySelector("span").textContent = "Mulai Kamera";
  $("vf-sub").textContent = "Kamera belum aktif";
}

function captureBlob() {
  frameW = video.videoWidth || 640;
  frameH = video.videoHeight || 480;
  capture.width = frameW;
  capture.height = frameH;
  capture.getContext("2d").drawImage(video, 0, 0, frameW, frameH);
  return new Promise((resolve) => capture.toBlob(resolve, "image/jpeg", 0.85));
}

function setFrameSize(w, h) {
  frameW = w;
  frameH = h;
  capture.width = w;
  capture.height = h;
  overlay.width = w;
  overlay.height = h;
}

/* Toggle idle reticle vs. live tracking: the static scan reticle/laser only
   shows when no face is being tracked (or the camera is off). */
function setTracking(on) {
  if (stageEl) stageEl.classList.toggle("tracking", !!on);
}

function drawFaces(faces) {
  overlay.width = frameW;
  overlay.height = frameH;
  const ctx = overlay.getContext("2d");
  ctx.clearRect(0, 0, frameW, frameH);
  ctx.lineWidth = Math.max(2, frameW / 220);
  ctx.font = `${Math.max(12, frameW / 40)}px system-ui, sans-serif`;
  ctx.textBaseline = "bottom";

  for (const f of faces) {
    const { x, y, w, h } = f.bbox;
    let color = "#6bd8cb";
    let label = f.liveness.is_live ? "unknown" : "spoof";
    if (!f.liveness.is_live) color = "#ffb4ab";
    if (f.match && f.match.matched) {
      color = "#4edea3";
      label = `${f.match.name} ${f.match.similarity.toFixed(2)}`;
    } else if (f.liveness.is_live) {
      label = `live? ${f.liveness.score.toFixed(2)}`;
    }

    ctx.strokeStyle = color;
    ctx.strokeRect(x, y, w, h);
    const boxH = Math.max(16, frameW / 34);
    const tw = ctx.measureText(label).width + 10;
    ctx.fillStyle = color;
    ctx.fillRect(x, y - boxH, tw, boxH);
    ctx.fillStyle = "#0b1326";
    ctx.fillText(label, x + 5, y - 3);
  }
}

function drawRegisteredLabel(name) {
  const ctx = overlay.getContext("2d");
  ctx.clearRect(0, 0, frameW, frameH);
  const label = `registered: ${name}`;
  const boxH = Math.max(18, frameW / 30);
  ctx.font = `${Math.max(12, frameW / 42)}px system-ui, sans-serif`;
  ctx.fillStyle = "#4edea3";
  ctx.fillRect(0, 0, ctx.measureText(label).width + 12, boxH);
  ctx.fillStyle = "#003824";
  ctx.textBaseline = "middle";
  ctx.fillText(label, 6, boxH / 2);
}

async function recognizeBlob(blob, direction, log) {
  const fd = new FormData();
  fd.append("file", blob, "frame.jpg");
  const gate = $("chk-gate") && $("chk-gate").checked;
  const qs = `direction=${direction || "in"}&log=${log ? "true" : "false"}&gate=${gate ? "true" : "false"}`;
  const data = await fetchJSON(`/api/recognize?${qs}`, { method: "POST", body: fd });
  drawFaces(data.faces);
  return data;
}

/* ── Instant match card ────────────────────────────────────── */
function updateMatchCard(face, recording) {
  const m = face.match;
  const name = m.name || m.user_id;
  const info = userMap[m.user_id] || {};
  const dir = DIR[face.direction] || "masuk";
  const dirTitle = DIR_TITLE[face.direction] || "Masuk";
  let status = face.attendance_status || (face.attendance_logged ? "logged" : "skipped");
  if (recording === false) status = "idle";

  $("match-empty").hidden = true;
  $("match-body").hidden = false;

  $("match-avatar-text").textContent = initials(name);
  $("match-name").textContent = name;
  $("match-role").textContent = "Pengguna terverifikasi";
  $("match-uid").textContent = `NIK: ${m.user_id}`;
  $("match-similarity").textContent = `${(m.similarity * 100).toFixed(1)}% Cocok`;
  $("match-when").textContent = status === "duplicate" && face.attendance_duplicate_at
    ? `Tercatat ${fmtClock(face.attendance_duplicate_at)}`
    : status === "logged" ? "Baru saja" : "Terverifikasi";

  const chipText = {
    logged: `Presensi ${dirTitle} Berhasil`,
    duplicate: `Sudah Presensi ${dirTitle} Hari Ini`,
    not_checked_in: "Anda Belum Presensi Masuk",
    idle: "Pilih Mode Absensi",
    skipped: "Terverifikasi",
  }[status] || "Terverifikasi";
  const chipTone = status === "not_checked_in" ? "error"
    : (status === "duplicate" || status === "logged") ? "primary" : "";
  $("match-state-chip").className = "chip" + (chipTone ? " " + chipTone : "");
  $("match-state-chip").innerHTML = `<span class="dot pulse"></span>${chipText}`;

  const dupAt = face.attendance_duplicate_at ? ` (${fmtClock(face.attendance_duplicate_at)})` : "";
  // Persistent on-screen reason (the toast is transient).
  $("vf-sub").textContent = status === "idle"
    ? "Pilih mode Presensi Masuk / Pulang untuk mencatat absensi"
    : status === "not_checked_in"
      ? "Anda belum melakukan presensi masuk hari ini"
      : status === "logged"
        ? `Absen ${dir} tercatat ${new Date().toLocaleTimeString("id-ID", { hour12: false })}`
        : status === "duplicate"
          ? `Anda sudah presensi ${dir} hari ini${dupAt}`
          : "Pengenalan langsung aktif";

  const attText = {
    logged: `Absen ${dir} tercatat`,
    duplicate: `Sudah ${dir}${dupAt}`,
    not_checked_in: "Wajib absen masuk dulu",
    idle: "Belum dicatat",
  }[status] || (info.count ? `Hadir ${info.count}×` : "Kehadiran baru");
  $("match-att").textContent = attText;

  const greetMsg = {
    logged: `Presensi ${dir} kamu berhasil terdata di sistem lokal. Have a wonderful and productive day!`,
    duplicate: `Anda sudah melakukan presensi ${dir} hari ini${dupAt} — tidak dicatat dua kali.`,
    not_checked_in: "Anda belum melakukan presensi masuk hari ini, jadi presensi pulang belum bisa dicatat.",
    idle: "Wajah dikenali, tetapi belum ada mode absensi yang dipilih — tidak ada yang dicatat.",
    skipped: "Wajah terverifikasi (mode pengenalan tanpa pencatatan absensi).",
  }[status] || "Wajah terverifikasi.";
  $("greet-name").textContent = `${greetWord()}, ${String(name).split(" ")[0]}!`;
  $("greet-msg").textContent = greetMsg;

  $("match-time").textContent = new Date().toLocaleTimeString("id-ID", { hour12: false });
  $("match-time-tag").textContent = status === "logged" ? `Baru dicatat (${dir})` : status === "duplicate" ? `Tercatat${dupAt}` : "Tidak dicatat";
  $("match-score").textContent = m.similarity.toFixed(3);
  $("match-id").textContent = m.user_id;
  $("match-conf").textContent = `Conf ${(face.confidence || 0).toFixed(2)}`;
  $("match-sync").textContent = status === "logged" ? "Lokal" : "—";
  $("match-sync-id").textContent = status === "logged" ? "status: unsynced" : "tidak ada catatan baru";
}

async function liveLoop() {
  if (loopBusy) return;                    // jangan tumpang tindih dengan loop sebelumnya
  if (!$("chk-live").checked || !stream || !photo.hidden) return;
  loopBusy = true;
  try {
    const blob = await captureBlob();
    const recording = mode !== null;
    const data = await recognizeBlob(blob, mode || "in", recording);
    setTracking(data.count > 0);
    $("vf-elapsed").textContent = `AI ${data.elapsed_ms}ms`;
    $("latency-value").textContent = `${data.elapsed_ms}ms (Optimal)`;
    const matched = data.faces.filter((f) => f.match && f.match.matched);
    updatePresence(new Set(matched.map((f) => f.match.user_id)));
    if (!recording) {
      // No mode chosen yet: recognise only, never write attendance.
      if (matched.length) {
        setStatus(`Terdeteksi: ${matched.map((f) => f.match.name).join(", ")} — pilih mode Masuk/Pulang untuk mencatat absensi.`, "info");
        updateMatchCard(matched[0], false);
      } else if (data.count > 0) {
        setStatus(`${data.count} wajah terdeteksi (${data.elapsed_ms} ms)`, "info");
      } else {
        setStatus(`Tidak ada wajah terdeteksi (${data.elapsed_ms} ms)`, "info");
      }
      return;
    }
    if (matched.length) {
      const names = matched.map((f) => f.match.name);
      setStatus(`Terdeteksi (${DIR[matched[0].direction] || "masuk"}): ${names.join(", ")} (${data.elapsed_ms} ms)`, "ok");
      for (const f of matched) toastForFace(f);
      updateMatchCard(matched[0], true);
      // Refresh tabel hanya saat status attendance benar-benar BERUBAH.
      // Sebelumnya 3 request + render ulang penuh tiap tick (700 ms): saat wajah
      // terdeteksi itu membuat antrean menumpuk danappeared "lambat" justru
      // setelah record pertama tercatat (tabel baru punya isi untuk dirender).
      if (attendanceChanged(matched)) refreshAll();
    } else if (data.count > 0) {
      setStatus(`${data.count} wajah terdeteksi, belum ada yang cocok (${data.elapsed_ms} ms)`, "info");
    } else {
      setStatus(`Tidak ada wajah terdeteksi (${data.elapsed_ms} ms)`, "info");
    }
  } catch (e) {
    setStatus("Galat pengenalan: " + e.message, "err");
  } finally {
    loopBusy = false;
  }
}

function scheduleLoop() {
  if (loopTimer) clearInterval(loopTimer);
  loopTimer = setInterval(() => { liveLoop(); }, 700);
}

/* ── Stats ─────────────────────────────────────────────────── */
async function refreshStats() {
  try {
    const s = await fetchJSON("/api/stats");
    $("stat-records").textContent = s.total;
    $("stat-users").textContent = s.users;
    $("stat-synced").textContent = s.synced;
    $("stat-pending").textContent = s.pending;
    const pct = s.total ? Math.round((s.synced / s.total) * 100) : 0;
    $("stat-records-bar").style.width = `${pct}%`;
    $("stat-records-foot").textContent = `${s.synced} tersinkron dari ${s.total} catatan`;
    $("stat-records-sub").textContent = `${s.users} pengguna`;
    $("node-bar").style.width = `${Math.min(100, 60 + s.users * 4)}%`;
  } catch (_) {}
}

/* ── Users ─────────────────────────────────────────────────── */
async function refreshUsers() {
  try {
    const data = await fetchJSON("/api/users");
    userMap = {};
    data.users.forEach((u) => { userMap[u.id] = { name: u.name, count: u.attendance_count }; });
    $("users-count").textContent = `(${data.count})`;
    const tbody = $("users").querySelector("tbody");
    if (!data.users.length) {
      tbody.innerHTML = `<tr><td class="table-empty" colspan="5">Belum ada pengguna terdaftar.</td></tr>`;
      return;
    }
    tbody.innerHTML = data.users
      .map((u) => {
        const last = u.last_attendance ? fmtTime(u.last_attendance) : "—";
        const today = (u.checked_in_today || u.checked_out_today)
          ? (u.checked_in_today ? dirBadge("in") : "") + (u.checked_out_today ? dirBadge("out") : "")
          : `<span class="muted tiny">belum</span>`;
        return `<tr>` +
          `<td class="mono nowrap">${esc(u.id)}</td>` +
          `<td><div class="user-name-cell"><span class="avatar-cell">${esc(initials(u.name))}</span>` +
          `<span class="user-name-text">${esc(u.name)}</span></div></td>` +
          `<td class="today-cell"><div class="chip-row">${today}</div></td>` +
          `<td class="mono nowrap">${last}</td>` +
          `<td class="action-cell"><button class="btn danger icon-only" data-delete="${esc(u.id)}" title="Hapus pengguna">` +
          `<svg class="icon sm"><use href="#i-trash"/></svg></button></td>` +
          `</tr>`;
      })
      .join("");
  } catch (_) {}
}

async function deleteUser(userId) {
  if (!confirm(`Hapus pengguna "${userId}"? Template-nya akan dinonaktifkan.`)) return;
  try {
    await fetchJSON(`/api/users/${encodeURIComponent(userId)}`, { method: "DELETE" });
    setStatus(`Pengguna ${userId} dihapus.`, "ok");
    showToast("Pengguna dihapus", userId, "info");
    refreshUsers();
    refreshStats();
  } catch (e) {
    setStatus("Galat hapus: " + e.message, "err");
  }
}

/* ── Attendance ────────────────────────────────────────────── */
function statusBadge(synced) {
  return synced
    ? `<span class="chip primary"><span class="dot"></span>Tersinkron</span>`
    : `<span class="chip"><span class="dot" style="background:var(--outline)"></span>Unsynced</span>`;
}

function dirBadge(dir) {
  return dir === "out"
    ? `<span class="chip"><span class="dot" style="background:var(--secondary)"></span>Pulang</span>`
    : `<span class="chip primary"><span class="dot"></span>Masuk</span>`;
}

async function refreshAttendance() {
  try {
    const data = await fetchJSON("/api/attendance?limit=50");
    $("att-count").textContent = `(${data.count})`;

    const tbody = $("attendance").querySelector("tbody");
    tbody.innerHTML = data.records.length
      ? data.records
          .map((r) => `<tr><td class="mono">${esc(r.user_id)}</td><td>${esc((userMap[r.user_id] || {}).name || "—")}</td><td>${dirBadge(r.direction)}</td><td>${fmtTime(r.timestamp)}</td><td>${r.similarity.toFixed(3)}</td><td>${r.synced ? "yes" : "no"}</td></tr>`)
          .join("")
      : `<tr><td class="table-empty" colspan="6">Belum ada catatan presensi.</td></tr>`;

    const feed = $("feed");
    feed.innerHTML = data.records.length
      ? data.records.slice(0, 6)
          .map((r) => {
            const name = (userMap[r.user_id] || {}).name || r.user_id;
            return `<div class="feed-row">` +
              `<div class="feed-left">` +
              `<span class="feed-avatar">${esc(initials(name))}</span>` +
              `<div class="feed-info"><span class="strong">${esc(name)}</span><span class="muted tiny">${esc(r.user_id)} • Presensi ${esc(DIR[r.direction] || "masuk")}</span></div>` +
              `</div>` +
              `<div class="feed-right">` +
              `<div class="feed-time"><span class="mono strong">${fmtTime(r.timestamp)}</span><span class="outline tiny">Akurasi ${(r.similarity * 100).toFixed(1)}%</span></div>` +
              dirBadge(r.direction) +
              statusBadge(r.synced) +
              `</div>` +
              `</div>`;
          })
          .join("")
      : `<div class="feed-empty">Belum ada aktivitas presensi.</div>`;
  } catch (_) {}
}

async function clearAttendance() {
  if (!confirm("Hapus SEMUA catatan presensi? Tindakan ini tidak bisa dibatalkan.")) return;
  try {
    const r = await fetchJSON("/api/attendance", { method: "DELETE" });
    setStatus(`Presensi dibersihkan (${r.deleted} catatan dihapus).`, "ok");
    showToast("Presensi dibersihkan", `${r.deleted} catatan dihapus`, "info");
    refreshAttendance();
    refreshStats();
    refreshUsers();
  } catch (e) {
    setStatus("Galat clear: " + e.message, "err");
  }
}

async function onSync() {
  try {
    const r = await fetchJSON("/api/sync", { method: "POST" });
    if (r.status === "disabled") {
      setStatus("Sync nonaktif — demo offline tanpa server pusat.", "info");
      return;
    }
    setStatus(`Sync: ${r.status}${r.error ? " (" + r.error + ")" : ""}`, r.success ? "ok" : "info");
    refreshAttendance();
    refreshStats();
  } catch (e) {
    setStatus("Galat sync: " + e.message, "err");
  }
}

/* ── Enroll / register ─────────────────────────────────────── */
async function enrollBlob(blob, name, userId) {
  const fd = new FormData();
  fd.append("name", name);
  if (userId) fd.append("user_id", userId);
  fd.append("file", blob, "enroll.jpg");
  const data = await fetchJSON("/api/enroll", { method: "POST", body: fd });
  refreshUsers();
  refreshStats();
  return data;
}

async function showPhoto(file) {
  if (photo.src) URL.revokeObjectURL(photo.src);
  photo.src = URL.createObjectURL(file);
  photo.hidden = false;
  video.hidden = true;
  $("video-msg").hidden = true;
  $("laser").hidden = true;
  if (stageEl) stageEl.classList.add("photo-mode");
  await photo.decode();
  setFrameSize(photo.naturalWidth, photo.naturalHeight);
  overlay.getContext("2d").clearRect(0, 0, frameW, frameH);
}

async function onEnroll() {
  const name = $("enroll-name").value.trim();
  const userId = $("enroll-id").value.trim();
  if (!name) {
    setStatus("Isi nama dulu, lalu klik Daftarkan wajah kamera.", "err");
    $("enroll-name").focus();
    return;
  }
  if (!stream) {
    setStatus("Aktifkan kamera dulu, atau gunakan Daftar dari gambar… untuk mendaftar dari foto.", "err");
    return;
  }
  try {
    const blob = await captureBlob();
    const data = await enrollBlob(blob, name, userId);
    setStatus(`Terdaftar "${data.name}" (${data.user_id}).`, "ok");
    showToast("Wajah terdaftar", `${data.name} (${data.user_id})`, "");
  } catch (e) {
    setStatus("Galat pendaftaran: " + e.message, "err");
  }
}

async function onUpload(file) {
  const name = $("enroll-name").value.trim();
  const userId = $("enroll-id").value.trim();
  if (!name) {
    setStatus("Isi nama, lalu pilih gambar untuk mendaftarkan wajah tersebut.", "err");
    $("enroll-name").focus();
    return;
  }
  try {
    await showPhoto(file);
    const data = await enrollBlob(file, name, userId);
    drawRegisteredLabel(data.name);
    setStatus(`Terdaftar "${data.name}" (${data.user_id}) dari gambar. Tidak ada absensi yang dicatat.`, "ok");
    showToast("Pendaftaran berhasil", `${data.name} — tanpa absensi`, "info");
    refreshAttendance();
  } catch (e) {
    setStatus("Galat pendaftaran: " + e.message, "err");
  }
}

/* ── Wiring ────────────────────────────────────────────────── */
function wire() {
  wireNav();
  showSection("presensi");
  applyTheme(currentTheme());
  $("btn-theme").addEventListener("click", () => applyTheme(currentTheme() === "light" ? "dark" : "light"));

  $("btn-camera").addEventListener("click", () => {
    if (stream) { stopCamera(); return; }
    startCamera().then((ok) => { if (ok) scheduleLoop(); });
  });

  $("btn-switch").addEventListener("click", () => {
    const restart = !!stream;
    stopCamera();
    startCamera().then((ok) => { if (ok) scheduleLoop(); else if (restart) setStatus("Gagal memuat ulang kamera.", "err"); });
  });

  $("btn-fullscreen").addEventListener("click", () => {
    const stage = document.querySelector(".stage");
    if (document.fullscreenElement) document.exitFullscreen();
    else if (stage && stage.requestFullscreen) stage.requestFullscreen();
  });

  const inBtn = $("btn-mode-in");
  const outBtn = $("btn-mode-out");
  const setMode = (next) => {
    mode = next;
    inBtn.classList.toggle("active", next === "in");
    outBtn.classList.toggle("active", next === "out");
    clearPresence();
    $("vf-hint").textContent = next === "in"
      ? "Posisikan Wajah — Mode Presensi Masuk"
      : "Posisikan Wajah — Mode Presensi Pulang";
    setStatus(`Mode: Presensi ${next === "in" ? "Masuk" : "Pulang"}.`, "info");
  };
  inBtn.addEventListener("click", () => setMode("in"));
  outBtn.addEventListener("click", () => setMode("out"));
  window.addEventListener("keydown", (e) => {
    if (e.key === "F1") { e.preventDefault(); inBtn.click(); }
    else if (e.key === "F2") { e.preventDefault(); outBtn.click(); }
  });

  $("btn-enroll").addEventListener("click", onEnroll);
  $("btn-upload").addEventListener("click", () => $("upload").click());
  $("upload").addEventListener("change", (e) => {
    if (e.target.files.length) onUpload(e.target.files[0]);
    e.target.value = "";
  });
  $("btn-sync").addEventListener("click", onSync);
  $("btn-clear-att").addEventListener("click", clearAttendance);
  $("users").querySelector("tbody").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-delete]");
    if (btn) deleteUser(btn.getAttribute("data-delete"));
  });

  video.addEventListener("loadedmetadata", () => {
    overlay.width = video.videoWidth;
    overlay.height = video.videoHeight;
  });
}

wire();
tickClock();
setInterval(tickClock, 1000);
loadHealth();
refreshStats();
refreshUsers();
refreshAttendance();
setInterval(() => { refreshStats(); refreshAttendance(); refreshUsers(); }, 5000);
