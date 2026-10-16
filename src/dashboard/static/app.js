"use strict";

const $ = (id) => document.getElementById(id);

const video = $("video");
const photo = $("photo");
const overlay = $("overlay");
const capture = $("capture");
const badge = $("badge");
const statusEl = $("status");
const videoMsg = $("video-msg");

let stream = null;
let loopTimer = null;
let frameW = 0;
let frameH = 0;

function setStatus(msg, type) {
  statusEl.textContent = msg;
  statusEl.className = "status" + (type ? " " + type : "");
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
  } catch (e) {
    setBadge("offline", "err");
  }
}

async function startCamera() {
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    video.srcObject = stream;
    await video.play();
    photo.hidden = true;
    video.style.display = "";
    videoMsg.style.display = "none";
    $("btn-camera").textContent = "Stop camera";
    setStatus("Camera on. Live recognition is running.", "info");
    return true;
  } catch (e) {
    setStatus("Camera unavailable: " + e.message + " — you can still use Upload image.", "err");
    return false;
  }
}

function stopCamera() {
  if (stream) {
    stream.getTracks().forEach((t) => t.stop());
    stream = null;
  }
  if (photo.hidden) videoMsg.style.display = "flex";
  $("btn-camera").textContent = "Start camera";
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
    const boxH = Math.max(16, frameW / 34);
    const tw = ctx.measureText(label).width + 10;
    ctx.fillStyle = color;
    ctx.fillRect(x, y - boxH, tw, boxH);
    ctx.fillStyle = "#0f172a";
    ctx.fillText(label, x + 5, y - 3);
  }
}

async function recognizeBlob(blob) {
  const fd = new FormData();
  fd.append("file", blob, "frame.jpg");
  const data = await fetchJSON("/api/recognize", { method: "POST", body: fd });
  drawFaces(data.faces);
  return data;
}

async function liveLoop() {
  if (!$("chk-live").checked || !stream || !photo.hidden) return;
  try {
    const blob = await captureBlob();
    const data = await recognizeBlob(blob);
    const names = data.faces.filter((f) => f.match && f.match.matched).map((f) => f.match.name);
    if (names.length) {
      setStatus(`Recognized: ${names.join(", ")} (${data.elapsed_ms} ms)`, "ok");
      refreshAttendance();
      refreshStats();
    } else {
      setStatus(`${data.count} face(s), no match (${data.elapsed_ms} ms)`, "info");
    }
  } catch (e) {
    setStatus("Recognize error: " + e.message, "err");
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
  refreshUsers();
  refreshStats();
  return data;
}

async function showPhoto(file) {
  if (photo.src) URL.revokeObjectURL(photo.src);
  photo.src = URL.createObjectURL(file);
  photo.hidden = false;
  video.style.display = "none";
  videoMsg.style.display = "none";
  await photo.decode();
  setFrameSize(photo.naturalWidth, photo.naturalHeight);
  overlay.getContext("2d").clearRect(0, 0, frameW, frameH);
}

async function onEnroll() {
  const name = $("enroll-name").value.trim();
  const userId = $("enroll-id").value.trim();
  if (!name) {
    setStatus("Type a name first, then click Enroll captured face.", "err");
    $("enroll-name").focus();
    return;
  }
  if (!stream) {
    setStatus("Start the camera first, or use Register from image… to enroll from a photo.", "err");
    return;
  }
  try {
    const blob = await captureBlob();
    const data = await enrollBlob(blob, name, userId);
    setStatus(`Enrolled "${data.name}" (${data.user_id}).`, "ok");
  } catch (e) {
    setStatus("Enroll error: " + e.message, "err");
  }
}

async function onUpload(file) {
  const name = $("enroll-name").value.trim();
  const userId = $("enroll-id").value.trim();
  if (!name) {
    setStatus("Type a name, then choose an image to register that face.", "err");
    $("enroll-name").focus();
    return;
  }
  try {
    await showPhoto(file);
    const data = await enrollBlob(file, name, userId);
    drawRegisteredLabel(data.name);
    setStatus(`Registered "${data.name}" (${data.user_id}) from image. No attendance written.`, "ok");
    refreshAttendance();
  } catch (e) {
    setStatus("Register error: " + e.message, "err");
  }
}

function drawRegisteredLabel(name) {
  const ctx = overlay.getContext("2d");
  ctx.clearRect(0, 0, frameW, frameH);
  const label = `registered: ${name}`;
  const boxH = Math.max(18, frameW / 30);
  ctx.font = `${Math.max(12, frameW / 42)}px system-ui, sans-serif`;
  ctx.fillStyle = "#22c55e";
  ctx.fillRect(0, 0, ctx.measureText(label).width + 12, boxH);
  ctx.fillStyle = "#0f172a";
  ctx.textBaseline = "middle";
  ctx.fillText(label, 6, boxH / 2);
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

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function refreshUsers() {
  try {
    const data = await fetchJSON("/api/users");
    $("users-count").textContent = `(${data.count})`;
    $("users").querySelector("tbody").innerHTML = data.users
      .map((u) => {
        const last = u.last_attendance ? u.last_attendance.slice(0, 19).replace("T", " ") : "—";
        return `<tr>` +
          `<td class="mono">${esc(u.id)}</td>` +
          `<td>${esc(u.name)}</td>` +
          `<td>${last}</td>` +
          `<td><button class="icon danger" data-delete="${esc(u.id)}">Delete</button></td>` +
          `</tr>`;
      })
      .join("");
  } catch (_) {}
}

async function deleteUser(userId) {
  if (!confirm(`Delete user "${userId}"? Their templates are deactivated.`)) return;
  try {
    await fetchJSON(`/api/users/${encodeURIComponent(userId)}`, { method: "DELETE" });
    setStatus(`Deleted user ${userId}.`, "ok");
    refreshUsers();
    refreshStats();
  } catch (e) {
    setStatus("Delete error: " + e.message, "err");
  }
}

async function clearAttendance() {
  if (!confirm("Delete ALL attendance records? This cannot be undone.")) return;
  try {
    const r = await fetchJSON("/api/attendance", { method: "DELETE" });
    setStatus(`Attendance cleared (${r.deleted} record(s) removed).`, "ok");
    refreshAttendance();
    refreshStats();
    refreshUsers();
  } catch (e) {
    setStatus("Clear error: " + e.message, "err");
  }
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
    setStatus(`Sync: ${r.status}${r.error ? " (" + r.error + ")" : ""}`, r.success ? "ok" : "info");
    refreshAttendance();
    refreshStats();
  } catch (e) {
    setStatus("Sync error: " + e.message, "err");
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
  $("btn-clear-att").addEventListener("click", clearAttendance);
  $("users").querySelector("tbody").addEventListener("click", (e) => {
    const id = e.target.getAttribute && e.target.getAttribute("data-delete");
    if (id) deleteUser(id);
  });
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
