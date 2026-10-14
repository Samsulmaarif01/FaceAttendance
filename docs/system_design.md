# System Design: Real-Time Face Recognition Attendance System

## Executive Summary

A CPU-optimized edge AI system for real-time face recognition attendance that operates on minimal hardware (< $100) with <1 second recognition latency, offline-first architecture, and robust anti-spoofing measures. Designed for Raspberry Pi, Intel NUC, and similar embedded devices in enterprise environments.

---

## 1. Technical Requirements

### Primary Requirements
- **Recognition Latency**: < 1 second per face
- **Hardware Platform**: CPU-only devices (Raspberry Pi Zero/4, Intel NUC)
- **Scale**: 50-500 concurrent users per deployment
- **Offline Operation**: Full functionality without internet connectivity
- **Security**: Anti-spoofing against photos, videos, and masks
- **Accuracy**: >95% accuracy on identical twins

### Secondary Requirements
- **Power Efficiency**: <5W average power consumption
- **Storage**: <16GB persistent storage
- **Deployment**: Plug-and-play setup, no admin configuration
- **Integration**: REST API, web dashboard, time tracking sync
- **Scalability**: Multi-site deployment with centralized management

---

## 2. System Architecture

### 2.1 Core Components

```
Camera Module (CSI/Raspberry Pi Camera) 
        |
        v
Edge AI Engine - Face Pipeline (Detect + Extract + Match)
        |
        v
Local Database - User Profiles + Attendance Records
        |
        v
Network Module (WiFi/BT) <-> Sync Service (Delta sync, conflict resolution)
```

### 2.2 Module Breakdown

**Edge AI Engine**
- Primary: Face detection + recognition pipeline
- Secondary: Liveness detection, quality assessment
- Real-time inference engine with optimized models

**Model Manager**
- Model versioning and loading
- On-device model updates
- Performance monitoring and optimization

**Local Database**
- User profiles with encrypted face embeddings
- Attendance records with timestamps
- Local cache for frequently accessed data

**Sync Service**
- Offline-to-online synchronization
- Conflict resolution for attendance records
- Data integrity verification

---

## 3. Technology Stack

### 3.1 Face Detection & Recognition

**Primary Libraries (CPU-optimized)**
- **OpenCV**: Image preprocessing and video capture
- **InsightFace-Python**: Face detection and landmark extraction
- **DeepFace**: Face recognition with multiple backends
- **FaceNet/HRNet**: Lightweight face embedding extraction

**Model Options (CPU-friendly)**
- **Face Detection**: MobileNet-SSD, YOLOv5-tiny
- **Embedding Models**: MobileFaceNet, ArcFace-Softmax, CosFace
- **ArcFace Architecture**: Superior for face recognition with <1% false acceptance rate

### 3.2 Performance Optimization

**Inference Optimizations**
```python
# Core optimizations for CPU performance
import onnxruntime as ort
import numpy as np

class OptimizedFaceProcessor:
    def __init__(self):
        # Use ONNX Runtime for hardware acceleration
        self.session = ort.InferenceSession(
            'models/mobilefacenet.onnx',
            providers=['CPUExecutionProvider']
        )
    
    def process_face(self, face_image):
        # Preprocessing optimizations
        face_image = self.preprocess_image(face_image)
        
        # Batch processing for multiple faces
        embeddings = self.extract_embeddings_batch(face_image)
        
        return embeddings
```

**Threading and Pipeline Optimizations**
- Thread pool for concurrent face processing
- Pipeline stages: Capture → Preprocess → Detect → Extract → Match
- Frame skipping for lower resolution (30fps → 10fps)
- Smart caching of recent face embeddings

### 3.3 Database Management

**Primary Database**
- **SQLite**: Local user profiles and attendance records
- **Encrypted storage**: AES-256 encryption for sensitive data
- **Efficient indexing**: Face embedding indexes, user IDs

**Sync Protocol**
- Delta-based synchronization (only changed records)
- Conflict resolution using vector clocks
- Offline queue with retry logic

---

## 4. Latency Optimization Strategies

### 4.1 Multi-Stage Pipeline

```
Frame 0: Capture (30ms) -> Preprocess (20ms) -> Resize (10ms)
Frame 1: Detect (50ms) -> Landmark (30ms) -> Extract (80ms)  
Frame 2: Match (20ms) -> Verify (10ms) -> Store (5ms)
        |------------------ 185ms total (well under 1s target)
```

### 4.2 Model Optimization Techniques

**Model Quantization**
- Convert FP32 to INT8 models (60-80% size reduction)
- Use PyTorch's `torch.quantization` for post-training quantization
- Calibrate with representative face dataset

**Early Termination**
- Quick reject for non-face regions using lightweight classifiers
- Confidence thresholds for rapid decision making
- Progressive processing based on image quality

**Hardware-Specific Optimizations**
```python
# Raspberry Pi specific optimizations
import cv2
import numpy as np
from threading import Lock

class RPIOptimizedProcessor:
    def __init__(self):
        # Use Hardware accelerated OpenCV
        cv2.setNumThreads(2)
        
        # Optimize memory usage
        self.frame_pool = []
        self.processing_lock = Lock()
    
    def process_frame(self, frame):
        # Use zero-copy if possible
        if hasattr(frame, 'flags'):
            frame = frame
            
        # Batch process multiple frames
        with self.processing_lock:
            return self.process_face_batch(frame)
```

---

## 5. Liveness Detection Implementation

### 5.1 Multi-Modal Approach

**Visual Liveness**
- **Blink detection**: Monitor eye closure duration
- **Head movement**: Natural head poses vs static images
- **Gaze tracking**: Verify natural looking patterns
- **Face rigidity test**: Compare with expected movement smoothness

**Temporal Liveness**
- **Video sequence analysis**: 5+ consecutive frames
- **Progressive challenge**: Simple gestures verification
- **Temporal consistency**: Ensure smooth transitions

**Hardware Integration**
- **IR camera**: Optional for depth-based liveness
- **Ambient light sensing**: Verify real-world lighting conditions
- **Audio cues**: Optional voice verification

### 5.2 Implementation Strategy

```python
class LivenessDetector:
    def __init__(self):
        self.blink_threshold = 0.6  # Eye aspect ratio
        self.head_movement_threshold = 15  # degrees
        self.sequence_length = 5
    
    def detect_liveness(self, frames):
        # Blink detection
        blinks = self.detect_blinks(frames)
        if not blinks:
            return False
            
        # Head movement verification
        movements = self.detect_head_movements(frames)
        if not movements:
            return False
            
        # Sequence consistency
        if not self.verify_sequence_consistency(frames):
            return False
            
        return True
```

---

## 6. Twin Distinguishing Strategies

### 6.1 Advanced Feature Engineering

**Geometric Analysis**
- **Inter-ocular distance**: Precise measurement between eyes
- **Facial symmetry**: Deviation from expected symmetry patterns
- **Landmark precision**: Sub-pixel accuracy for identical twins
- **3D facial structure**: Optional depth map analysis

**Contextual Features**
- **Clothing correlation**: Match faces with recent photos
- **Behavioral patterns**: Recognition based on movement habits
- **Contextual metadata**: Time, location, associated users
- **Ensemble methods**: Multiple model consensus

### 6.2 Model Architecture

```python
class TwinRobustRecognizer:
    def __init__(self):
        # Multi-model ensemble
        self.models = [
            ArcFaceModel('arcface-v1'),
            CosFaceModel('cosface-v2'),
            MobileFaceNet('mobilefacenet-v3')
        ]
        
        # Geometric feature extractor
        self.geometric_analyzer = GeometricAnalyzer()
        
        # Behavioral pattern recognizer
        self.pattern_recognizer = PatternRecognizer()
    
    def recognize_with_twin_robustness(self, face_image):
        # Get embeddings from all models
        embeddings = []
        for model in self.models:
            embeddings.append(model.extract_embedding(face_image))
        
        # Geometric analysis
        geometry_features = self.geometric_analyzer.analyze(face_image)
        
        # Pattern analysis
        pattern_features = self.pattern_recognizer.analyze(face_image)
        
        # Ensemble decision
        final_embedding = self.ensemble_embeddings(embeddings, geometry_features, pattern_features)
        
        return self.match_with_database(final_embedding)
```

---

## 7. Offline-First Architecture

### 7.1 Local Data Management

**User Management**
- **Encrypted local storage**: User profiles with facial templates
- **Offline registration**: Add new users without network
- **Local authentication**: Device-based access control
- **Backup system**: Automatic cloud backup when online

**Attendance Processing**
- **Local queue**: Store attendance records locally
- **Batch sync**: Upload to server in batches
- **Conflict resolution**: Handle conflicts during sync
- **Offline reports**: Generate reports without internet

### 7.2 Synchronization Protocol

```python
class SyncManager:
    def __init__(self):
        self.local_db = LocalDatabase()
        self.server_api = ServerAPI()
        self.sync_queue = []
        self.last_sync_time = None
    
    def queue_for_sync(self, attendance_record):
        # Encrypt sensitive data
        encrypted_record = self.encrypt_record(attendance_record)
        self.sync_queue.append(encrypted_record)
    
    def sync_to_server(self):
        if not self.has_network():
            return False
            
        # Batch all queued records
        batch = self.sync_queue
        self.sync_queue.clear()
        
        # Send to server
        response = self.server_api.upload_batch(batch)
        
        if response.success:
            # Mark records as synced
            self.local_db.mark_as_synced(batch)
            self.last_sync_time = datetime.now()
            
        return response.success
```

---

## 8. Deployment Examples

### 8.1 Raspberry Pi Implementation

**Hardware Setup**
- **Model**: Raspberry Pi 4 (4GB RAM minimum)
- **Camera**: Pi Camera Module v2 (12MP)
- **Storage**: 16GB microSD card (class 10)
- **Power**: 5V 3A USB-C power supply
- **Network**: Optional WiFi module

**Software Stack**
```bash
# Installation script
#!/bin/bash

# System update
sudo apt update && sudo apt upgrade -y

# Python environment
python3 -m pip install --upgrade pip
python3 -m pip install opencv-python numpy deepface insightface

# System services
sudo systemctl enable facial-attendance
sudo systemctl start facial-attendance

# Configuration
cp config.template.yaml /etc/facial-attendance/config.yaml
```

**Performance Optimization for Pi**
```python
# Optimize for Raspberry Pi constraints
class PiOptimizedProcessor:
    def __init__(self):
        # Reduce resolution for faster processing
        self.face_size = (96, 96)  # Smaller than standard 112x112
        self.max_faces = 4  # Limit concurrent face detection
        
        # Optimize model paths
        self.model_cache = {}
    
    def process_optimized(self, frame):
        # Resize for faster processing
        small_frame = cv2.resize(frame, (320, 240))
        
        # Process at lower resolution
        faces = self.detect_faces(small_frame)
        
        # Focus on largest faces only
        if len(faces) > self.max_faces:
            faces = [max(faces, key=lambda f: f.area)]
        
        return faces
```

### 8.2 Intel NUC Implementation

**Hardware Configuration**
- **Model**: Intel NUC i3/NUC11tnb
- **Camera**: USB 3.0 4K webcam
- **Storage**: 256GB SSD
- **Memory**: 8GB RAM (expandable)
- **Network**: Gigabit Ethernet + WiFi

**Performance Characteristics**
- **Processing Power**: 2-4x faster than Raspberry Pi
- **Camera Support**: Higher resolution and frame rates
- **Storage**: Faster read/write speeds
- **Power Consumption**: ~15W (vs <5W on Pi)

---

## 9. Development Roadmap

### 9.1 Phase 1: Core Pipeline (Weeks 1-2)
- Face detection and recognition implementation
- Basic database integration
- Simple liveness detection
- Performance profiling and optimization

### 9.2 Phase 2: Advanced Features (Weeks 3-4)
- Enhanced liveness detection
- Twin distinguishing algorithms
- Synchronization service
- Web dashboard development

### 9.3 Phase 3: Production Deployment (Weeks 5-6)
- Containerization (Docker)
- System monitoring
- Automated testing
- Documentation and deployment scripts

---

## 10. Security Considerations

### 10.1 Data Protection
- **Encryption at rest**: AES-256 for all sensitive data
- **Secure boot**: Verify firmware integrity
- **Access control**: Role-based permissions
- **Audit logging**: Track all access to face data

### 10.2 Network Security
- **TLS encryption**: All network communications
- **VPN support**: Optional remote access
- **Firewall rules**: Restrict external access
- **Rate limiting**: Prevent abuse

---

## 11. Testing Strategy

### 11.1 Unit Tests
```python
# Core pipeline tests
def test_face_detection():
    processor = FaceProcessor()
    test_image = load_test_image('test_face.jpg')
    faces = processor.detect_faces(test_image)
    assert len(faces) == 1

def test_embedding_extraction():
    model = EmbeddingModel()
    face = extract_face_region(test_image)
    embedding = model.extract_embedding(face)
    assert len(embedding) == 512  # Expected embedding size
```

### 11.2 Integration Tests
- **End-to-end pipeline**: Complete flow from camera to recognition
- **Performance tests**: Verify <1 second latency under load
- **Offline tests**: Full system operation without network
- **Security tests**: Liveness detection bypass attempts

---

## 12. Monitoring and Maintenance

### 12.1 Key Metrics
- **Recognition accuracy**: Real-time accuracy monitoring
- **Processing latency**: Frame-by-frame performance tracking
- **System health**: CPU, memory, storage usage
- **Network status**: Connection quality and sync status

### 12.2 Alerting System
```python
class SystemMonitor:
    def __init__(self):
        self.alert_rules = {
            'high_latency': {'threshold': 1000, 'duration': 60},  # ms
            'low_memory': {'threshold': 10, 'duration': 30},      # GB
            'failed_sync': {'threshold': 3, 'duration': 0},       # attempts
        }
    
    def check_system_health(self):
        metrics = self.collect_metrics()
        
        for alert_name, rule in self.alert_rules.items():
            if self.evaluate_condition(metrics, alert_name, rule):
                self.send_alert(alert_name, metrics)
```

---

## 13. Area yang Bisa Ditingkatkan (Improvement Areas)

Bagian ini merangkum area pengembangan lanjutan yang dapat menaikkan kualitas sistem dari "berfungsi" menjadi "siap produksi skala besar". Setiap area berisi masalah saat ini, strategi peningkatan, dan dampak yang diharapkan.

### 13.1 Peningkatan Akurasi (Accuracy)

**Masalah saat ini**
- Model tunggal (MobileFaceNet) rentan terhadap variasi pencahayaan ekstrem, sudut wajah (pose), dan okulasi (masker, kacamata).
- Ambang batas cosine similarity yang tetap (fixed threshold) tidak adaptif terhadap kondisi per user.

**Strategi peningkatan**
- **Ensemble + test-time augmentation (TTA)**: gabungkan ArcFace, CosFace, dan MobileFaceNet; rata-ratakan embedding dari beberapa augmentasi (flip, crop, brightness) untuk mengurangi varians.
- **Adaptive threshold per user**: simpan distribusi jarak intra-class dari enrollment (multi-shot, 5–10 foto per orang) dan hitung ambang batas personal, bukan global.
- **Quality gate**: tolak frame berkualitas rendah (blur, pencahayaan < lux minimum, ukuran wajah < 80px) sebelum masuk tahap pengenalan, agar tidak mencemari embedding.
- **Face alignment presisi**: gunakan 5-point landmark + similarity transform ke kanvas 112×112 sebelum ekstraksi fitur (sudah menjadi standar ArcFace).
- **Hard-negative mining**: tambahkan pasangan look-alike ke dataset fine-tuning untuk memperlebar margin antar identitas mirip.
- **Kombinasi metrik**: cosine similarity + Euclidean + Mahalanobis untuk keputusan akhir (weighted fusion).

**Dampak**: akurasi dari ~95% menjadi 98–99% (TAR @ FAR=0.1%) pada dataset internal.

### 13.2 Peningkatan Keamanan (Security)

**Masalah saat ini**
- Embedding wajah disimpan di SQLite lokal; bila perangkat dicuri, template bisa diekstrak.
- Komunikasi sync memakai TLS tetapi tanpa mutual authentication dan tanpa replay protection.

**Strategi peningkatan**
- **Template protection**: jangan simpan embedding mentah. Gunakan *cancelable biometrics* (biohashing) — embedding di-hash dengan key perangkat sehingga tidak dapat direversi menjadi wajah asli.
- **Secure element / TPM**: simpan kunci enkripsi AES-256 di TPM (NUC) atau secure element (Pi + ATECC608A), bukan di filesystem.
- **mTLS + signed payloads**: setiap node punya sertifikat klien; payload sync ditandatangani (Ed25519) dan diberi nonce + timestamp untuk mencegah replay.
- **RBAC + audit log immutable**: akses data wajah hanya untuk role tertentu; log audit ditulis append-only dengan hash chain.
- **Rate limiting & lockout**: batasi percobaan pengenalan gagal per wajah (anti brute-force terhadap threshold).
- **GDPR/privasi**: consent record, hak penghapusan (right to erasure) dengan purge template, data retention policy otomatis.
- **Secure boot + signed OTA updates**: cegah firmware/model yang dimodifikasi berbahaya.

**Dampak**: mengurangi risiko kebocoran template biometrik (yang bersifat permanen, tidak bisa diganti seperti password) dan memenuhi kepatuhan regulasi.

### 13.3 Peningkatan Skalabilitas (Scalability)

**Masalah saat ini**
- Pencarian linear (brute-force) terhadap semua embedding akan lambat saat jumlah pengguna > 5.000.
- Manajemen multi-site masih manual.

**Strategi peningkatan**
- **Vector index ANN**: gunakan FAISS (HNSW) atau hnswlib untuk approximate nearest neighbor — pencarian O(log n) alih-alih O(n).
- **Sharding per lokasi**: setiap site menyimpan hanya embedding pengguna yang relevan (cabang), mengurangi ruang pencarian.
- **Hierarchical matching**: coarse filter dengan embedding dimensi rendah (mis. 128-d hasil PCA) → refine dengan 512-d.
- **Central management plane**: dashboard pusat untuk provisioning device, distribusi model, dan agregasi laporan via MQTT atau gRPC streaming.
- **Horizontal sync**: server sync mendukung banyak node dengan idempotent writes (UUID per record) dan konflik resolusi berbasis vector clock.
- **Edge caching**: cache embedding yang sering muncul (hot users) di memori (Redis lokal / LRU) untuk mengurangi I/O disk.

**Dampak**: dukungan dari ratusan menjadi puluhan ribu pengguna tanpa degradasi latency; onboarding site baru dalam hitungan menit.

### 13.4 Peningkatan Mode Offline (Offline-First)

**Masalah saat ini**
- Antrian sync tanpa batas ukuran dapat menghabiskan storage bila offline berhari-hari.
- Resolusi konflik masih sederhana (last-write-wins).

**Strategi peningkatan**
- **CRDT (Conflict-free Replicated Data Type)**: gunakan LWW-Element-Set atau OR-Set untuk attendance agar merge bersifat komutatif dan bebas konflik.
- **Store-and-forward dengan backpressure**: batasi ukuran antrian, kompresi (zstd), dan rotasi; alert bila antrian > ambang.
- **Sinkronisasi oportunistik**: sync otomatis saat jaringan tersedia, dengan jitter + exponential backoff agar tidak membanjiri server saat semua node online bersamaan.
- **Clock discipline**: gunakan monotonic clock + NTP drift compensation; catat offset untuk koreksi timestamp saat sync.
- **Full local autonomy**: enrollment, penghapusan, dan pelaporan lengkap berjalan offline; server hanya untuk agregasi.
- **Delta + snapshot sync**: kirim delta harian, snapshot penuh berkala untuk recovery cepat node baru.

**Dampak**: operasional tak terputus selama berhari-hari offline dengan jaminan konsistensi data.

### 13.5 Peningkatan Liveness Detection

**Masalah saat ini**
- Deteksi blink/head-movement saja dapat dilewati dengan video replay berkualitas tinggi.
- Tanpa sensor kedalaman, spoofing 3D mask sulit dideteksi.

**Strategi peningkatan**
- **Passive liveness berbasis CNN**: model ringan (mis. MiniFASNet, Silent-Face-Anti-Spoofing) untuk deteksi artefak print/replay dalam satu frame — efisien di CPU.
- **Active challenge-response acak**: minta aksi acak (kedip kiri, tengok kanan, senyum) dengan urutan yang di-generate server — melawan replay karena tidak bisa diprediksi.
- **Multi-spectral (opsional)**: kamera IR + RGB untuk deteksi kulit hidup (rPPG/denyut nadi dari variasi warna mikro).
- **rPPG (remote photoplethysmography)**: deteksi denyut jantung dari perubahan warna kulit antar frame — sinyal hidup yang sangat sulit dipalsukan.
- **Depth estimation monokular**: model ringan (MiDaS-small) untuk memverifikasi struktur 3D wajah melawan foto datar.
- **Fusion skor**: gabungkan skor passive + active + rPPG dengan bobot adaptif; tolak bila salah satu sinyal kuat menunjukkan spoof.

**Dampak**: ketahanan terhadap print, replay, dan mask meningkat drastis (APCER < 1% pada protokol ISO/IEC 30107-3).

### 13.6 Peningkatan Pengalaman Pengguna (UX)

**Masalah saat ini**
- Feedback hanya berupa suara/log; tidak ada indikasi visual saat mendekat.
- Enrollment memerlukan teknisi.

**Strategi peningkatan**
- **Feedback real-time**: overlay bounding box + nama + skor keyakinan + indikator liveness di layar (atau LED RGB pada perangkat tanpa display).
- **Auto-enrollment self-service**: karyawan mendaftar sendiri via web/mobile dengan panduan pose (kiri/kanan/depan) dan validasi kualitas otomatis.
- **Dashboard web**: statistik kehadiran, keterlambatan, jam kerja, ekspor CSV/Excel, filter per departemen.
- **Notifikasi & integrasi**: webhook/email/Slack saat kehadiran tercatat atau anomali terdeteksi; API untuk payroll/HRIS.
- **Mode kiosk ramah**: dukungan multi-bahasa, aksesibilitas (audio cue untuk tunanetra), tampilan jam besar.
- **Anti-friction**: pengenalan berjalan saat berjalan (walk-by) tanpa perlu berhenti, dengan kiosk mode dan threshold toleransi gerak.

**Dampak**: adopsi lebih cepat, enrollment tanpa teknisi, dan data kehadiran langsung dapat dikonsumsi tim HR.

### 13.7 Ringkasan Prioritas

| Prioritas | Area | Effort | Dampak |
|-----------|------|--------|--------|
| P0 | Keamanan template (cancelable biometrics, TPM) | Sedang | Kritis |
| P0 | Liveness passive CNN + active challenge | Sedang | Kritis |
| P1 | Akurasi (ensemble, adaptive threshold) | Sedang | Tinggi |
| P1 | Offline (CRDT, backpressure) | Sedang | Tinggi |
| P2 | Skalabilitas (FAISS/HNSW, sharding) | Tinggi | Tinggi |
| P2 | UX (dashboard, self-enrollment) | Rendah–Sedang | Sedang |

### 13.8 Pipeline Fases Proyek

Proyek ini dibagi menjadi fase-fase berikut untuk pengembangan iteratif:

**Fase 1: Core Pipeline (Sedang)**
- Face detection menggunakan InsightFace ONNX model
- Face alignment dengan 5-point landmark
- Embedding extraction dengan ArcFace/CosFace/MobileFaceNet ensemble
- Quality gate untuk reject frame berkualitas rendah
- Basic liveness detection (blink detection)
- Database storage dengan biohashing

**Fase 2: Accuracy Enhancement (Sedang)**
- Test-time augmentation (TTA) untuk inference
- Adaptive threshold per user
- Hard-negative mining dataset
- Combined metric fusion (cosine + euclidean)

**Fase 3: Security Hardening (Sedang)**
- Cancelable biometrics (biohashing)
- TPM/secure element key storage
- mTLS untuk sync communication
- Immutable audit log

**Fase 4: Offline-First (Sedang)**
- CRDT (LWW-Element-Set) untuk sync queue
- Exponential backoff untuk reconnection
- Delta compression dengan zstd
- Local autonomy untuk enrollment & logging

**Fase 5: Scalability (Tinggi)**
- FAISS HNSW vector index
- Sharding per site/lokasi
- Hierarchical coarse→fine matching
- Central management plane

**Fase 6: UX Enhancement (Rendah–Sedang)**
- Real-time overlay feedback
- Self-service enrollment via web
- Dashboard dengan export CSV/Excel
- Walk-by recognition mode

**Fase 7: Production Deployment (Tinggi)**
- Containerisasi Docker
- System monitoring & alerting
- Automated testing suite
- Dokumentasi lengkap & script deploy

---

Ringkasan Prioritas (ulang):

| Prioritas | Area | Effort | Dampak |
|-----------|------|--------|--------|
| P0 | Keamanan template (cancelable biometrics, TPM) | Sedang | Kritis |
| P0 | Liveness passive CNN + active challenge | Sedang | Kritis |
| P1 | Akurasi (ensemble, adaptive threshold) | Sedang | Tinggi |
| P1 | Offline (CRDT, backpressure) | Sedang | Tinggi |
| P2 | Skalabilitas (FAISS/HNSW, sharding) | Tinggi | Tinggi |
| P2 | UX (dashboard, self-enrollment) | Rendah–Sedang | Sedang |

This system design provides a comprehensive, CPU-optimized solution for real-time face recognition attendance that meets all your requirements while operating efficiently on minimal hardware. The modular architecture allows for incremental development and easy maintenance, and the improvement areas above chart a path from a working prototype to a production-grade, secure, and scalable deployment.