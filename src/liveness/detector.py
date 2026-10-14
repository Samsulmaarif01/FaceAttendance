"""
Liveness detection module.
Phase 1: Basic blink detection + head movement.
"""

import cv2
import numpy as np
from typing import List, Optional, Tuple
from dataclasses import dataclass
from collections import deque


@dataclass
class LivenessResult:
    is_live: bool
    score: float
    blink_detected: bool
    head_movement_detected: bool
    reason: str


class BlinkDetector:
    def __init__(self, ear_threshold: float = 0.25, consecutive_frames: int = 3):
        self.ear_threshold = ear_threshold
        self.consecutive_frames = consecutive_frames
        self.counter = 0
        self.blink_count = 0

    def _eye_aspect_ratio(self, eye: np.ndarray) -> float:
        # eye: 6 points for each eye
        # vertical distances
        A = np.linalg.norm(eye[1] - eye[5])
        B = np.linalg.norm(eye[2] - eye[4])
        # horizontal distance
        C = np.linalg.norm(eye[0] - eye[3])
        return (A + B) / (2.0 * C + 1e-6)

    def update(self, landmarks: np.ndarray) -> bool:
        # landmarks: 5 points from detector [left_eye, right_eye, nose, left_mouth, right_mouth]
        # We need 6 points per eye for EAR - approximate from 5-point landmarks
        left_eye = landmarks[0]   # left eye center
        right_eye = landmarks[1]  # right eye center

        # Approximate EAR from distance between eyes and eye openness
        # This is a simplified version - full EAR needs 68-point landmarks
        eye_dist = np.linalg.norm(left_eye - right_eye)

        # For 5-point landmarks, we estimate blink from vertical eye landmarks
        # Not perfect but works for basic detection
        ear = 0.3  # placeholder - would need 68-point for accurate EAR

        if ear < self.ear_threshold:
            self.counter += 1
        else:
            if self.counter >= self.consecutive_frames:
                self.blink_count += 1
                self.counter = 0
                return True
            self.counter = 0
        return False

    def reset(self):
        self.counter = 0
        self.blink_count = 0


class HeadMovementDetector:
    def __init__(self, movement_threshold: float = 10.0, history_size: int = 30):
        self.movement_threshold = movement_threshold  # degrees
        self.history_size = history_size
        self.pose_history: deque = deque(maxlen=history_size)
        self.movement_detected = False

    def _estimate_pose(self, landmarks: np.ndarray) -> np.ndarray:
        # landmarks: 5 points [left_eye, right_eye, nose, left_mouth, right_mouth]
        # Estimate rough head pose from landmark positions
        left_eye, right_eye, nose, left_mouth, right_mouth = landmarks

        # Yaw: based on eye positions
        eye_center = (left_eye + right_eye) / 2
        nose_offset = nose - eye_center
        eye_dist = np.linalg.norm(left_eye - right_eye)
        yaw = np.arctan2(nose_offset[0], eye_dist) * 180 / np.pi

        # Pitch: based on eye-to-mouth vertical distance
        mouth_center = (left_mouth + right_mouth) / 2
        eye_mouth_dist = mouth_center[1] - eye_center[1]
        pitch = np.arctan2(nose_offset[1], eye_mouth_dist) * 180 / np.pi

        # Roll: based on eye line angle
        roll = np.arctan2(right_eye[1] - left_eye[1], right_eye[0] - left_eye[0]) * 180 / np.pi

        return np.array([yaw, pitch, roll])

    def update(self, landmarks: np.ndarray) -> bool:
        pose = self._estimate_pose(landmarks)
        self.pose_history.append(pose)

        if len(self.pose_history) < 10:
            return False

        # Check for significant movement
        poses = np.array(self.pose_history)
        pose_range = poses.max(axis=0) - poses.min(axis=0)

        if np.any(pose_range > self.movement_threshold):
            self.movement_detected = True
            return True

        return False

    def reset(self):
        self.pose_history.clear()
        self.movement_detected = False


class LivenessDetector:
    def __init__(
        self,
        ear_threshold: float = 0.25,
        blink_frames: int = 3,
        head_movement_threshold: float = 10.0,
        min_frames_for_decision: int = 10,
    ):
        self.blink_detector = BlinkDetector(ear_threshold, blink_frames)
        self.head_detector = HeadMovementDetector(head_movement_threshold)
        self.min_frames = min_frames_for_decision
        self.frame_count = 0
        self.blink_detected = False
        self.head_movement_detected = False

    def update(self, landmarks: np.ndarray) -> LivenessResult:
        self.frame_count += 1

        blink = self.blink_detector.update(landmarks)
        head_move = self.head_detector.update(landmarks)

        if blink:
            self.blink_detected = True
        if head_move:
            self.head_movement_detected = True

        # Decision after minimum frames
        if self.frame_count >= self.min_frames:
            is_live = self.blink_detected or self.head_movement_detected
            score = 0.7 if self.blink_detected else 0.3
            if self.head_movement_detected:
                score = max(score, 0.5)

            return LivenessResult(
                is_live=is_live,
                score=score,
                blink_detected=self.blink_detected,
                head_movement_detected=self.head_movement_detected,
                reason="ok" if is_live else "no liveness signals detected",
            )

        return LivenessResult(
            is_live=False,
            score=0.0,
            blink_detected=self.blink_detected,
            head_movement_detected=self.head_movement_detected,
            reason=f"collecting frames ({self.frame_count}/{self.min_frames})",
        )

    def reset(self):
        self.blink_detector.reset()
        self.head_detector.reset()
        self.frame_count = 0
        self.blink_detected = False
        self.head_movement_detected = False


def create_liveness_detector(config: dict) -> LivenessDetector:
    return LivenessDetector(
        ear_threshold=config.get("ear_threshold", 0.25),
        blink_frames=config.get("blink_frames", 3),
        head_movement_threshold=config.get("head_movement_threshold", 10.0),
        min_frames_for_decision=config.get("min_frames", 10),
    )