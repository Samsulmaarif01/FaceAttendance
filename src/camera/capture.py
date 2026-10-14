"""
Camera capture module for face attendance system.
Supports OpenCV and PiCamera2 backends.
"""

import cv2
import numpy as np
from abc import ABC, abstractmethod
from typing import Optional, Tuple
from dataclasses import dataclass


@dataclass
class CameraConfig:
    device_id: int = 0
    width: int = 640
    height: int = 480
    fps: int = 30
    backend: str = "opencv"


class CameraBackend(ABC):
    @abstractmethod
    def open(self) -> bool:
        pass

    @abstractmethod
    def read(self) -> Optional[np.ndarray]:
        pass

    @abstractmethod
    def release(self) -> None:
        pass

    @abstractmethod
    def is_opened(self) -> bool:
        pass


class OpenCVBackend(CameraBackend):
    def __init__(self, config: CameraConfig):
        self.config = config
        self.cap: Optional[cv2.VideoCapture] = None

    def open(self) -> bool:
        self.cap = cv2.VideoCapture(self.config.device_id)
        if not self.cap.isOpened():
            return False
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.config.fps)
        return True

    def read(self) -> Optional[np.ndarray]:
        if self.cap is None:
            return None
        ret, frame = self.cap.read()
        return frame if ret else None

    def release(self) -> None:
        if self.cap:
            self.cap.release()
            self.cap = None

    def is_opened(self) -> bool:
        return self.cap is not None and self.cap.isOpened()


class PiCameraBackend(CameraBackend):
    def __init__(self, config: CameraConfig):
        self.config = config
        self.camera = None

    def open(self) -> bool:
        try:
            from picamera2 import Picamera2
            self.camera = Picamera2()
            config = self.camera.create_video_configuration(
                main={"size": (self.config.width, self.config.height)}
            )
            self.camera.configure(config)
            self.camera.start()
            return True
        except ImportError:
            return False

    def read(self) -> Optional[np.ndarray]:
        if self.camera is None:
            return None
        frame = self.camera.capture_array()
        # Convert RGB to BGR for OpenCV compatibility
        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    def release(self) -> None:
        if self.camera:
            self.camera.stop()
            self.camera = None

    def is_opened(self) -> bool:
        return self.camera is not None


class Camera:
    def __init__(self, config: CameraConfig):
        self.config = config
        self.backend = self._create_backend()

    def _create_backend(self) -> CameraBackend:
        if self.config.backend == "picamera2":
            return PiCameraBackend(self.config)
        return OpenCVBackend(self.config)

    def start(self) -> bool:
        return self.backend.open()

    def capture(self) -> Optional[np.ndarray]:
        return self.backend.read()

    def stop(self) -> None:
        self.backend.release()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


def create_camera(config: CameraConfig) -> Camera:
    return Camera(config)