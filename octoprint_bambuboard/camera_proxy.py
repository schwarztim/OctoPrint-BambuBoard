"""RTSP camera proxy for Bambu Lab printers.

Provides per-printer RTSP stream management with lazy start, auto-stop on
inactivity, and JPEG/MJPEG frame serving via Flask routes.

Requires: opencv-python-headless (optional dependency, gated behind try/except).
"""

import logging
import os
import threading
import time

_logger = logging.getLogger("octoprint.plugins.bambuboard.camera_proxy")

# Bambu printers use self-signed TLS certs for RTSPS streams.
# Tell FFmpeg (used by OpenCV) to accept them.
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp|analyzeduration;1000000")

try:
    import cv2

    _HAS_CV2 = True
except ImportError:
    _HAS_CV2 = False
    _logger.info("opencv-python-headless not installed — camera features disabled")


class RTSPStream:
    """Manages a single RTSP stream from a Bambu printer camera."""

    FPS_CAP = 15
    JPEG_QUALITY = 70
    INACTIVITY_TIMEOUT = 60  # seconds before auto-stop

    def __init__(self, rtsp_url):
        self._url = rtsp_url
        self._lock = threading.Lock()
        self._frame = None  # Latest JPEG bytes
        self._running = False
        self._thread = None
        self._last_access = 0.0
        self._cap = None

    @property
    def active(self):
        return self._running

    @property
    def latest_frame(self):
        """Get latest JPEG frame, updating last-access timestamp."""
        self._last_access = time.time()
        with self._lock:
            return self._frame

    def start(self):
        """Start the background capture thread."""
        if self._running:
            return
        self._running = True
        self._last_access = time.time()
        self._thread = threading.Thread(
            target=self._capture_loop, name="bb-rtsp", daemon=True
        )
        self._thread.start()
        _logger.info("RTSP stream started: %s", self._url)

    def stop(self):
        """Stop the background capture thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        if self._cap:
            self._cap.release()
            self._cap = None
        with self._lock:
            self._frame = None
        _logger.info("RTSP stream stopped: %s", self._url)

    def _capture_loop(self):
        """Background loop: read RTSP frames, encode to JPEG."""
        # Use TCP transport for reliability; set short analyze duration for faster start.
        # CAP_FFMPEG is required for rtsps:// (TLS) support.
        self._cap = cv2.VideoCapture(self._url, cv2.CAP_FFMPEG)
        if not self._cap.isOpened():
            _logger.error("Failed to open RTSP stream: %s", self._url)
            # Try fallback without TLS (rtsp:// instead of rtsps://)
            fallback_url = self._url.replace("rtsps://", "rtsp://", 1)
            if fallback_url != self._url:
                _logger.info("Trying fallback without TLS: %s", fallback_url)
                self._cap = cv2.VideoCapture(fallback_url, cv2.CAP_FFMPEG)
            if not self._cap.isOpened():
                _logger.error("All RTSP connection attempts failed for: %s", self._url)
                self._running = False
                return

        frame_interval = 1.0 / self.FPS_CAP
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, self.JPEG_QUALITY]

        while self._running:
            # Auto-stop on inactivity
            if time.time() - self._last_access > self.INACTIVITY_TIMEOUT:
                _logger.info("RTSP stream idle, auto-stopping: %s", self._url)
                break

            start = time.time()
            ret, frame = self._cap.read()
            if not ret:
                _logger.warning("RTSP read failed, retrying in 2s: %s", self._url)
                time.sleep(2)
                # Reconnect
                self._cap.release()
                self._cap = cv2.VideoCapture(self._url, cv2.CAP_FFMPEG)
                continue

            # Resize to 720p max width
            h, w = frame.shape[:2]
            if w > 1280:
                scale = 1280 / w
                frame = cv2.resize(
                    frame, (1280, int(h * scale)), interpolation=cv2.INTER_AREA
                )

            # Encode to JPEG
            ok, jpeg = cv2.imencode(".jpg", frame, encode_params)
            if ok:
                with self._lock:
                    self._frame = jpeg.tobytes()

            # Throttle to FPS cap
            elapsed = time.time() - start
            if elapsed < frame_interval:
                time.sleep(frame_interval - elapsed)

        self._running = False
        if self._cap:
            self._cap.release()
            self._cap = None


class CameraProxy:
    """Manages RTSP streams for all configured Bambu printers."""

    def __init__(self, plugin):
        self._plugin = plugin
        self._streams = {}  # printer_id → RTSPStream
        self._lock = threading.Lock()

    @staticmethod
    def is_available():
        """Check if opencv is installed."""
        return _HAS_CV2

    def get_rtsp_url(self, printer_id):
        """Build the RTSP URL for a printer."""
        cfg = self._plugin._get_printer_config(printer_id)
        if not cfg:
            return None

        # Use override URL if configured
        custom_url = cfg.get("camera_url", "").strip()
        if custom_url:
            return custom_url

        # Auto-construct from printer config
        hostname = cfg.get("hostname", "")
        access_code = cfg.get("access_code", "")
        if not hostname or not access_code:
            return None

        return f"rtsps://bblp:{access_code}@{hostname}:322/streaming/live/1"

    def get_or_start_stream(self, printer_id):
        """Get an active stream, starting it if needed."""
        if not _HAS_CV2:
            return None

        with self._lock:
            stream = self._streams.get(printer_id)
            if stream and stream.active:
                return stream

            url = self.get_rtsp_url(printer_id)
            if not url:
                return None

            stream = RTSPStream(url)
            self._streams[printer_id] = stream
            stream.start()
            return stream

    def stop_stream(self, printer_id):
        """Stop a specific printer's stream."""
        with self._lock:
            stream = self._streams.pop(printer_id, None)
        if stream:
            stream.stop()

    def stop_all(self):
        """Stop all active streams."""
        with self._lock:
            streams = list(self._streams.values())
            self._streams.clear()
        for stream in streams:
            stream.stop()

    def get_snapshot(self, printer_id):
        """Get a single JPEG snapshot from a printer's camera."""
        stream = self.get_or_start_stream(printer_id)
        if not stream:
            return None

        # Wait briefly for first frame if stream just started
        for _ in range(20):  # Up to 2 seconds
            frame = stream.latest_frame
            if frame:
                return frame
            time.sleep(0.1)

        return None

    def generate_mjpeg(self, printer_id):
        """Generator that yields MJPEG multipart frames."""
        stream = self.get_or_start_stream(printer_id)
        if not stream:
            return

        while stream.active:
            frame = stream.latest_frame
            if frame:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: "
                    + str(len(frame)).encode()
                    + b"\r\n\r\n"
                    + frame
                    + b"\r\n"
                )
            time.sleep(1.0 / RTSPStream.FPS_CAP)
