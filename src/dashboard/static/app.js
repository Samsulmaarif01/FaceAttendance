"use strict";

const $ = (id) => document.getElementById(id);

const video = $("video");
const overlay = $("overlay");
const capture = $("capture");
const badge = $("badge");
const statusEl = $("status");
const videoMsg = $("video-msg");

let stream = null;
let loopTimer = null;

function setStatus(msg) {
  statusEl.textContent = msg;
}

function setBadge(text, cls) {
  badge.textContent = text;
  badge.className = "badge" + (cls ? " " + cls : "");
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

async function loadHealth() {
  try {
    const h = await fetchJSON("/api/health");
    if (h.demo_mode) setBadge("demo mode", "demo");
    else setBadge("live models", "ok");
    setStatus(`models=${h.recognition_models}  detector=${h.detector_loaded}  matcher=${h.matcher_backend}`);
  } catch (e) {
    setBadge("offline", "err");
  }
}

async function startCamera() {
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    video.srcObject = stream;
    await video.play();
    videoMsg.style.display = "none";
    $("btn-camera").textContent = "Stop camera";
    return true;
  } catch (e) {
    setStatus("Camera unavailable: " + e.message + " (you can still use Upload image)");
    return false;
  }
}

function stopCamera() {
  if (stream) {
    stream.getTracks().forEach((t) => t.stop());
    stream = null;
  }
  videoMsg.style.display = "flex";
  $("btn-camera").textContent = "Start camera";
}

function captureBlob() {
  const w = video.videoWidth || 640;
  const h = video.videoHeight || 480;
  capture.width = w;
  capture.height = h;
  const ctx = capture.getContext("2d");
  ctx.drawImage(video, 0, 0, w, h);
  return new Promise((resolve) => capture.toBlob(resolve, "image/jpeg", 0.85));
}

function drawFaces(faces, frameW, frameH) {
  overlay.width = frameW;
  overlay.height = frameH;
  const ctx = overlay.getContext("2d");
  ctx.clearRect(0, 0, frameW, frameH);
  ctx.lineWidth = Math.max(2, frameW / 220);
  ctx.font = `${Math.max(12, frameW / 40)}px system-ui, sans-serif`;
  ctx.textBaseline = "bottom";

  for (const f of faces) {
    const { x, y, w, h } = f.bbox;
    let color = "#f59e0b";
    let label = f.liveness.is_live ? "unknown" : "spoof";
    if (!f.liveness.is_live) color = "#ef4444";
    if (f.match && f.match.matched) {
      color = "#22c55e";
      label = `${f.match.name} ${f.match.similarity.toFixed(2)}`;
    } else if (f.liveness.is_live) {
      label = `live? ${f.liveness.score.toFixed(2)}`;
    }

    ctx.strokeStyle = color;
    ctx.strokeRect(x, y, w, h);
    const tw = ctx.measureText(label).width + 10;
    ctx.fillStyle = color;
    ctx.fillRect(x, y - Math.max(16, frameW / 34), tw, Math.max(16, frameW / 34));
    ctx.fillStyle = "#0f172a";
    ctx.fillText(label, x + 5, y - 3);
  }
}

async function recognizeBlob(blob) {
  const fd = new FormData();
  fd.append("file", blob, "frame.jpg");
  const data = await fetchJSON("/api/recognize", { method: "POST", body: fd });
  drawFaces(data.faces, capture.width, capture.height);
  return data;
}

async function liveLoop() {
  if (!$("chk-live").checked || !stream) return;
  try {
    const blob = await captureBlob();
    const data = await recognizeBlob(blob);
    const names = data.faces
      .filter((f) => f.match && f.match.matched)
      .map((f) => f.match.name);
    if (names.length) {
      setStatus(`Recognized: ${names.join(", ")} (${data.elapsed_ms} ms)`);
      refreshAttendance();
      refreshStats();
    } else {
      setStatus(`${data.count} face(s), no match (${data.elapsed_ms} ms)`);
    }
  } catch (e) {
    setStatus("Recognize error: " + e.message);
  }
}

function scheduleLoop() {
  if (loopTimer) clearInterval(loopTimer);
  loopTimer = setInterval(() => { liveLoop(); }, 700);
}

async function enrollBlob(blob, name, userId) {
  const fd = new FormData();
  fd.append("name", name);
  if (userId) fd.append("user_id", userId);
  fd.append("file", blob, "enroll.jpg");
  const data = await fetchJSON("/api/enroll", { method: "POST", body: fd });
  setStatus(`Enrolled ${data.name} (${data.user_id})`);
  refreshUsers();
}

async function onEnroll() {
  const name = $("enroll-name").value.trim();
  if (!name) { setStatus("Enter a name before enrolling"); return; }
  if (!stream) { setStatus("Start the camera first (or use Upload image)"); return; }
  try {
    const blob = await captureBlob();
    await enrollBlob(blob, name);
  } catch (e) {
    setStatus("Enroll error: " + e.message);
  }
}

async function onUpload(file) {
  const name = $("enroll-name").value.trim();
  if (!name) { setStatus("Enter a name, then choose an image to enroll"); return; }
  try {
    await enrollBlob(file, name);
  } catch (e) {
    setStatus("Enroll error: " + e.message);
  }
}

function statCard(k, v) {
  return `<div class="stat"><div class="v">${v}</div><div class="k">${k}</div></div>`;
}

async function refreshStats() {
  try {
    const s = await fetchJSON("/api/stats");
    $("stats").innerHTML =
      statCard("records", s.total) +
      statCard("users", s.users) +
      statCard("synced", s.synced) +
      statCard("pending", s.pending);
  } catch (_) {}
}

async function refreshUsers() {
  try {
    const data = await fetchJSON("/api/users");
    $("users-count").textContent = `(${data.count})`;
    $("users").querySelector("tbody").innerHTML = data.users
      .map((u) => `<tr><td class="mono">${u.id}</td><td>${u.name}</td><td>${u.created_at.slice(0, 19).replace("T", " ")}</td></tr>`)
      .join("");
  } catch (_) {}
}

async function refreshAttendance() {
  try {
    const data = await fetchJSON("/api/attendance?limit=50");
    $("att-count").textContent = `(${data.count})`;
    $("attendance").querySelector("tbody").innerHTML = data.records
      .map((r) => `<tr><td class="mono">${r.user_id}</td><td>${r.timestamp.slice(0, 19).replace("T", " ")}</td><td>${r.similarity.toFixed(3)}</td><td>${r.synced ? "yes" : "no"}</td></tr>`)
      .join("");
  } catch (_) {}
}

async function onSync() {
  try {
    const r = await fetchJSON("/api/sync", { method: "POST" });
    setStatus(`Sync: ${r.status}${r.error ? " (" + r.error + ")" : ""}`);
    refreshAttendance();
    refreshStats();
  } catch (e) {
    setStatus("Sync error: " + e.message);
  }
}

function wire() {
  $("btn-camera").addEventListener("click", () => {
    if (stream) { stopCamera(); return; }
    startCamera().then((ok) => { if (ok) scheduleLoop(); });
  });
  $("btn-enroll").addEventListener("click", onEnroll);
  $("btn-upload").addEventListener("click", () => $("upload").click());
  $("upload").addEventListener("change", (e) => {
    if (e.target.files.length) onUpload(e.target.files[0]);
    e.target.value = "";
  });
  $("btn-sync").addEventListener("click", onSync);
  video.addEventListener("loadedmetadata", () => {
    overlay.width = video.videoWidth;
    overlay.height = video.videoHeight;
  });
}

wire();
loadHealth();
refreshStats();
refreshUsers();
refreshAttendance();
setInterval(() => { refreshStats(); refreshAttendance(); refreshUsers(); }, 5000);
