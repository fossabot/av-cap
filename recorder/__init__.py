"""
Multi-Camera Capture System package
Provides classes and utilities to capture frames from one or more cameras.
Uses PyAV for cross-platform video capture and Pillow for image processing.
"""

from .camera import CameraCapture
from .multi_camera import MultiCameraCapture
from . import utils
from .utils import (
    list_available_cameras,
    get_camera_device_path,
    get_platform_backend,
    resolve_windows_camera_name,
    IS_WINDOWS,
    IS_LINUX,
    IS_JETSON
)

__all__ = [
    "CameraCapture",
    "MultiCameraCapture",
    "utils",
    "list_available_cameras",
    "get_camera_device_path",
    "get_platform_backend",
    "resolve_windows_camera_name",
    "IS_WINDOWS",
    "IS_LINUX",
    "IS_JETSON",
]
