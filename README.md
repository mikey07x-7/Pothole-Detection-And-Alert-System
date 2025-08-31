# 🛣️ Deep Learning-based Automated Pothole Detection and Alert System

This project is an **end-to-end AI-powered solution** for **pothole detection, visualization, and reporting**.  
It uses **YOLO (Ultralytics)** for real-time pothole detection, integrates with **GPS** for location tagging, and streams detections via **WebSockets** to a **mobile-friendly web app** with **Mapbox visualization**.  

---

## 📂 Project Structure

```
├── Pothole.py              # Main detection + WebSocket server script
├── pothole.pt              # Trained YOLO model (custom-trained for potholes)
├── Video_test.mp4          # Sample video input
├── pothole_log.csv         # Auto-generated CSV log of detections
├── requirements.txt        # Dependencies
├── /data                   # Training dataset
│   ├── train/images
│   ├── train/labels
│   ├── val/images
│   ├── val/labels
├── data.yaml               # YOLO dataset configuration
├── train.py                # YOLO training script
└── pothole_mobile.html     # Mobile-friendly web app (Mapbox + WebSocket)
```  

---

## 🚀 Features

- ✅ **YOLOv11-based pothole detection** (works on images, video, or webcam)  
- ✅ **GPS integration** (via USB NMEA GPS or IP-based geolocation fallback)  
- ✅ **WebSocket server** → real-time streaming of detections to frontend  
- ✅ **CSV logging** → stores timestamp, GPS, and confidence values  
- ✅ **Mobile-friendly UI** with **Mapbox integration** for pothole mapping  
- ✅ **Authority mode** → login for municipal staff to mark potholes as fixed  
- ✅ **Glassmorphism design** for modern, clean mobile UI  

---

## 🏗️ Tech Stack

- **Deep Learning** → Python, Ultralytics YOLO, OpenCV, NumPy  
- **Backend** → Async WebSockets, GPS integration  
- **Frontend** → HTML, CSS, JavaScript (glassmorphism UI)  
- **Visualization** → Mapbox GL JS for interactive pothole mapping  

---

## ⚙️ Installation & Usage

### 🔹 Pre-steps
```bash
# 1. Clone project
git clone (https://github.com/mikey07x-7/Pothole-Detection-And-Alert-System)
cd pothole-detection

# 2. Create virtual environment
conda create -n pothole python=3.10
conda activate pothole

# 3. Install dependencies
pip install ultralytics
pip install -r requirements.txt
```

### 🔹 Training YOLO Model
1. Prepare dataset in YOLO format:
   ```
   data/
   ├── train/images
   ├── train/labels
   ├── val/images
   ├── val/labels
   ```
2. Create `data.yaml` with paths to your dataset.  
3. Train the model:  
   ```bash
   yolo detect train data=data.yaml model=yolov8n.pt epochs=50 imgsz=640
   ```
4. Save trained weights as `pothole.pt`.

---

### 🔹 Running Detection  
```bash
python Pothole.py
```
- Runs detection on **image, video, or webcam** (set in `VIDEO_SOURCE`).  
- Starts **WebSocket server** at:  
  ```
  ws://localhost:7777/feed
  ```  
- Logs detections into `pothole_log.csv`.  
- Shows real-time detection window (`q` to quit).  

---

### 🔹 Running Web App  
1. Open `pothole_mobile.html` in your browser.  
2. Update fields:  
   - **WebSocket URL** → `ws://localhost:7777/feed`  
   - **Mapbox Token** → your Mapbox API key  
3. Start detecting potholes and see them appear on the **map interface**.  

---

## 🛰️ GPS Setup

### Option A: Using USB GPS Module (NMEA)
- Connect GPS module to `/dev/ttyUSB0` (Linux) or COM port (Windows).  
- Install drivers if needed.  
- The script uses `pyserial` + `pynmea2` to parse live GPS data.  

### Option B: Using IP-based Geolocation (Fallback)
- If no GPS module is found, the script automatically fetches location using **`geocoder`** (IP lookup).  
- Accuracy is lower than GPS but useful for quick tests.  

---

## 📊 Outputs

- **Console log** → model loading, WebSocket connections, detection events  
- **CSV file** → structured log of detections  
- **Frontend Mapbox UI** → pothole markers appear live on map  

---

## 📌 Roadmap / Future Upgrades

- [ ] Deploy as a **real-time backend inference server**  
- [ ] Convert into a **Progressive Web App (PWA) / Android app**  
- [ ] Add **cloud storage** for centralized pothole reporting  
- [ ] Integrate with **municipal dashboards** for automated alerts  

---

## 🎯 Demo Preview

📷 *(Add screenshots or GIFs here showing YOLO detection + Mapbox visualization)*
