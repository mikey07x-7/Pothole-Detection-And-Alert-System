import asyncio
import base64
import csv
import datetime as dt
import json
import math
import os
import time
from collections import deque
from typing import Tuple

import cv2
import geocoder
import websockets
import numpy as np
from ultralytics import YOLO
import pytz

try:
    import serial  # type: ignore
    import pynmea2  # type: ignore
    HAS_NMEA = True
except Exception:
    HAS_NMEA = False

# =====================
# CONFIG
# =====================
MODEL_PATH = "pothole.pt"
VIDEO_SOURCE = "Video_test.mp4"   # can be .mp4, 0 (webcam), or .jpg
DEVICE = "0"

WS_HOST = "0.0.0.0"
WS_PORT = 7777
WS_PATH = "/feed"

CONF_THRESH = 0.30
IOU = 0.5
MAX_FPS = 20

DIST_THRESHOLD_M = 50
COOLDOWN_SEC = 45
HISTORY_SIZE = 200

SEND_IMAGE = True
PREVIEW_MAX_W = 512
JPEG_QUALITY = 70

CSV_LOG = "pothole_log.csv"
SHOW_WINDOW = True

# =====================
# Timezone
# =====================
IST = pytz.timezone("Asia/Kolkata")

# =====================
# Helpers
# =====================
def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def get_gps_coordinates() -> Tuple[float, float]:
    if HAS_NMEA:
        try:
            with serial.Serial("/dev/ttyUSB0", 9600, timeout=0.7) as ser:
                for _ in range(4):
                    line = ser.readline().decode("ascii", errors="ignore").strip()
                    if line.startswith("$GPGGA") or line.startswith("$GPRMC"):
                        try:
                            msg = pynmea2.parse(line)
                            lat = getattr(msg, "latitude", 0.0) or 0.0
                            lon = getattr(msg, "longitude", 0.0) or 0.0
                            if lat and lon:
                                return float(lat), float(lon)
                        except Exception:
                            pass
        except Exception:
            pass
    try:
        g = geocoder.ip("me")
        if g.ok and g.latlng:
            return float(g.latlng[0]), float(g.latlng[1])
    except Exception:
        pass
    return 0.0, 0.0

def b64_jpeg_preview(img_bgr) -> str:
    h, w = img_bgr.shape[:2]
    if w > PREVIEW_MAX_W:
        scale = PREVIEW_MAX_W / float(w)
        img_bgr = cv2.resize(img_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode("ascii") if ok else ""

class Deduper:
    def __init__(self, dist_m: float, cooldown_s: float, history_size: int = 200):
        self.dist_m = dist_m
        self.cooldown_s = cooldown_s
        self.recent = deque(maxlen=history_size)

    def is_duplicate(self, lat: float, lon: float, now: float) -> bool:
        for t, la, lo in self.recent:
            if now - t <= self.cooldown_s and haversine(lat, lon, la, lo) < self.dist_m:
                return True
        return False

    def push(self, lat: float, lon: float, now: float) -> None:
        self.recent.append((now, lat, lon))

# =====================
# WebSocket server
# =====================
clients = set()
client_connected_event = asyncio.Event()

async def ws_handler(*args):
    if len(args) == 2:
        websocket, path = args
    else:
        websocket, = args
        path = WS_PATH  # default

    if path != WS_PATH:
        await websocket.close(code=1008, reason="Invalid path")
        return

    clients.add(websocket)
    print("Client connected")
    client_connected_event.set()
    try:
        await websocket.wait_closed()
    finally:
        clients.remove(websocket)
        print("Client disconnected")
        if not clients:
            client_connected_event.clear()

async def broadcast(payload: dict):
    if not clients:
        return
    msg = json.dumps({"type": "detection", "payload": payload}, separators=(",", ":"))
    await asyncio.gather(*[ws.send(msg) for ws in list(clients)], return_exceptions=True)

# =====================
# Detection loop
# =====================
async def detect_loop():
    model = YOLO(MODEL_PATH)
    dummy = np.zeros((32, 32, 3), dtype=np.uint8)
    model.predict(source=dummy, imgsz=640, device=DEVICE, verbose=False)

    if VIDEO_SOURCE.lower().endswith((".jpg", ".png")):
        frame = cv2.imread(VIDEO_SOURCE)
        if frame is None:
            print("Could not load image")
            return
        results = model.predict(frame, conf=CONF_THRESH, iou=IOU, imgsz=640, device=DEVICE, verbose=False)[0]
        if hasattr(results, "boxes") and results.boxes is not None and len(results.boxes) > 0:
            lat, lon = get_gps_coordinates()
            for b in results.boxes:
                conf = float(b.conf[0])
                payload = {
                    "id": f"det_{int(time.time()*1000)}",
                    "timestamp": dt.datetime.now(IST).isoformat(),
                    "latitude": float(lat),
                    "longitude": float(lon),
                    "confidence": conf,
                }
                if SEND_IMAGE:
                    payload["image_base64"] = b64_jpeg_preview(frame)
                    print("Broadcasting:", payload)
                await broadcast(payload)
        return

    cap = cv2.VideoCapture(VIDEO_SOURCE)
    try:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap.set(cv2.CAP_PROP_FPS, MAX_FPS)
    except Exception:
        pass

    deduper = Deduper(DIST_THRESHOLD_M, COOLDOWN_SEC, HISTORY_SIZE)
    last_tick = 0.0
    frame_id = 0

    if not os.path.exists(CSV_LOG):
        with open(CSV_LOG, "w", newline="") as f:
            csv.writer(f).writerow(["timestamp", "lat", "lon", "confidence"])

    while True:
        ok, frame = cap.read()
        if not ok:
            await asyncio.sleep(0.05)
            continue

        now = time.time()
        if MAX_FPS > 0:
            dt_wait = (1.0 / MAX_FPS) - (now - last_tick)
            if dt_wait > 0:
                await asyncio.sleep(dt_wait)
        last_tick = time.time()

        results = model.predict(frame, conf=CONF_THRESH, iou=IOU, imgsz=640, device=DEVICE, verbose=False)[0]

        lat, lon = get_gps_coordinates()

        if hasattr(results, "boxes") and results.boxes is not None and len(results.boxes) > 0:
            for b in results.boxes:
                conf = float(b.conf[0])
                if lat or lon:
                    if deduper.is_duplicate(lat, lon, now=last_tick):
                        continue

                payload = {
                    "id": f"det_{int(time.time()*1000)}_{frame_id}",
                    "timestamp": dt.datetime.now(IST).isoformat(),
                    "latitude": float(lat),
                    "longitude": float(lon),
                    "confidence": conf,
                }
                if SEND_IMAGE:
                    try:
                        payload["image_base64"] = b64_jpeg_preview(frame)
                    except Exception:
                        pass

                await broadcast(payload)

                with open(CSV_LOG, "a", newline="") as f:
                    csv.writer(f).writerow([payload["timestamp"], payload["latitude"], payload["longitude"], payload["confidence"]])

                if lat or lon:
                    deduper.push(lat, lon, now=last_tick)

        if SHOW_WINDOW:
            if hasattr(results, "boxes") and results.boxes is not None:
                for b in results.boxes:
                    x1, y1, x2, y2 = map(int, b.xyxy[0].tolist())
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    conf = float(b.conf[0])
                    cv2.putText(frame, f"pothole {conf:.2f}", (x1, max(15, y1-6)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1)
            cv2.imshow("Pothole Detection", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        frame_id += 1

    cap.release()
    cv2.destroyAllWindows()

# =====================
# Main entry
# =====================
async def main():
    print(f"Loading model from {MODEL_PATH} ...")
    async with websockets.serve(ws_handler, WS_HOST, WS_PORT):
        url = f"ws://localhost:{WS_PORT}{WS_PATH}"
        print(f"WebSocket server ready at {url}")

        print("Waiting for client connection...")
        await client_connected_event.wait()
        print("Client connected, starting detection loop")

        await detect_loop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
