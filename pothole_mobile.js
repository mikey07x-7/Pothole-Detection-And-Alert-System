// ========================
// CONFIG
// ========================
const DEFAULT_WS_URL = "ws://localhost:7777/feed"; // change if needed
let ws = null;
let detectionHistory = [];
let wsConnected = false;
let map;

// ========================
// AUTHORITY ACCESS
// ========================
let isAuthority = false;
const AUTHORITY_EMAIL = "authority@gmail.com";

document.addEventListener("DOMContentLoaded", () => {
  const authBtn = document.getElementById("btn-authority-login");
  const lockStatus = document.createElement("div");
  lockStatus.id = "authority-lock";
  lockStatus.className = "muted lock-status locked";
  lockStatus.innerHTML = "🔒 Locked – Authority only";
  document.querySelector(".authority-card .card-header").appendChild(lockStatus);

  authBtn.addEventListener("click", () => {
    const email = document.getElementById("authority-email").value.trim();
    if (email.toLowerCase() === AUTHORITY_EMAIL.toLowerCase()) {
      isAuthority = true;
      lockStatus.className = "muted lock-status unlocked";
      lockStatus.innerHTML = "🔓 Unlocked – Authority mode enabled";
      showToast("Authority access granted ✅", "success");
      renderHistory();
    } else {
      isAuthority = false;
      lockStatus.className = "muted lock-status locked";
      lockStatus.innerHTML = "🔒 Locked – Authority only";
      showToast("Access denied ❌ (Invalid email)", "error");
      renderHistory();
    }
  });

  // Filters & search
  document.getElementById("history-filter").addEventListener("change", renderHistory);
  document.getElementById("history-search").addEventListener("input", renderHistory);
});

// ========================
// HELPER FUNCTIONS
// ========================
function formatTimestamp(ts) {
  try {
    const d = new Date(ts);
    return d.toLocaleString("en-IN", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch (e) {
    return ts; // fallback
  }
}

// ========================
// MAPBOX INIT
// ========================
function initMap() {
  const tokenInput = document.getElementById("mapbox-token");
  const token =
    tokenInput?.value ||
    "mapbox-token";

  mapboxgl.accessToken = token;

  map = new mapboxgl.Map({
    container: "map",
    style: "mapbox://styles/mapbox/streets-v12",
    center: [77.5946, 12.9716], // default Bangalore
    zoom: 12,
  });
}

function addMapMarker(lat, lon, confidence) {
  if (!map || lat === 0.0 || lon === 0.0) return;
  new mapboxgl.Marker({ color: confidence > 0.5 ? "red" : "orange" })
    .setLngLat([lon, lat])
    .addTo(map);
}

// ========================
// CONNECT WEBSOCKET
// ========================
function connectWS() {
  if (ws && ws.readyState === WebSocket.OPEN) return;

  const url = DEFAULT_WS_URL;
  ws = new WebSocket(url);

  ws.onopen = () => {
    wsConnected = true;
    document.getElementById("ws-status").innerText = "connected";
    document.getElementById("ws-dot").className = "dot connected";
    console.log("[WS] Connected to", url);
  };

  ws.onclose = () => {
    wsConnected = false;
    document.getElementById("ws-status").innerText = "disconnected";
    document.getElementById("ws-dot").className = "dot disconnected";
    console.warn("[WS] Disconnected");
    setTimeout(connectWS, 3000); // auto-retry
  };

  ws.onmessage = (ev) => {
    try {
      console.log("[WS] Incoming:", ev.data);
      const parsed = JSON.parse(ev.data);

      let det = null;
      if (parsed.type === "detection" && parsed.payload) {
        det = parsed.payload;
      } else if (parsed.latitude && parsed.longitude) {
        det = parsed;
      }

      if (det) {
        det.fixed = false;
        detectionHistory.push(det);
        document.getElementById("count").innerText = detectionHistory.length;
        if (det.latitude && det.longitude && !(det.latitude === 0.0 && det.longitude === 0.0)) {
          addMapMarker(det.latitude, det.longitude, det.confidence);
        }
        renderHistory();
      }
    } catch (err) {
      console.error("[WS] Message parse error", err, ev.data);
    }
  };
}

// ========================
// RENDER HISTORY WITH FILTERS
// ========================
function renderHistory() {
  const filter = document.getElementById("history-filter").value;
  const search = document.getElementById("history-search").value.toLowerCase();
  const list = document.getElementById("history");
  list.innerHTML = "";

  let items = [...detectionHistory];

  // Apply filters
  if (filter === "fixed") {
    items = items.filter((d) => d.fixed);
  } else if (filter === "notfixed") {
    items = items.filter((d) => !d.fixed);
  }

  // Apply search
  if (search) {
    items = items.filter((d) =>
      JSON.stringify(d).toLowerCase().includes(search)
    );
  }

  // Sort order
  if (filter === "oldest") {
    items.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
  } else {
    items.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
  }

  // Always put fixed items at the bottom
  items.sort((a, b) => (a.fixed === b.fixed ? 0 : a.fixed ? 1 : -1));

  for (let det of items) {
    const item = document.createElement("div");
    item.className = "item" + (det.fixed ? " fixed" : "");
    item.innerHTML = `
      <div class="thumb" style="background-image:url('${det.image_base64 || ""}')"></div>
      <div class="meta">
        <div><strong>${formatTimestamp(det.timestamp) || ""}</strong></div>
        <div class="muted">
          ${det.latitude && det.longitude && !(det.latitude === 0.0 && det.longitude === 0.0)
            ? `Lat: ${det.latitude?.toFixed?.(6)}, Lon: ${det.longitude?.toFixed?.(6)}`
            : "No location available"}
        </div>
        <div class="muted">Confidence: ${(det.confidence * 100).toFixed(1)}%</div>
        ${det.fixed ? '<span class="badge-fixed">Fixed</span>' : ""}
      </div>
    `;

    if (!det.fixed && isAuthority) {
      const fixBtn = document.createElement("button");
      fixBtn.textContent = "Mark Fixed";
      fixBtn.className = "secondary";
      fixBtn.addEventListener("click", () => {
        det.fixed = true;
        showToast("Marked as Fixed ✅", "success");
        renderHistory();
      });
      item.appendChild(fixBtn);
    }

    list.appendChild(item);
  }
}

// ========================
// TOAST HELPER
// ========================
function showToast(msg, type = "info") {
  const wrap = document.getElementById("toast-wrap");
  const div = document.createElement("div");
  div.className = `toast ${type}`;
  div.textContent = msg;
  wrap.appendChild(div);
  setTimeout(() => div.remove(), 3000);
}

// ========================
// INIT ON PAGE LOAD
// ========================
window.addEventListener("load", () => {
  if (Notification && Notification.permission !== "granted") {
    Notification.requestPermission();
  }
  initMap();
  connectWS();
});
