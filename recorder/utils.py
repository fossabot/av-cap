import time
import yaml
import av
import os
import platform
import logging
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

# Platform detection
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
IS_JETSON = os.path.exists("/etc/nv_tegra_release") if IS_LINUX else False


def _maintain_fps(loop_start_time: float, frame_interval: float) -> None:
    elapsed = time.time() - loop_start_time
    if elapsed < frame_interval:
        time.sleep(frame_interval - elapsed)


def should_stop(start_time: float, duration: Optional[int]) -> bool:
    return duration is not None and (time.time() - start_time) >= duration


def get_setting(cli_value, config_value, default):
    return cli_value if cli_value is not None else (config_value if config_value is not None else default)


def load_config(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


def get_camera_device_path(camera_id) -> str:
    """Get the appropriate camera device path based on the platform"""
    if IS_WINDOWS:
        # Handle both integer IDs and string names
        if isinstance(camera_id, str):
            return f"video={camera_id}"
        else:
            return f"video={camera_id}"
    elif IS_LINUX:
        return f"/dev/video{camera_id}"
    else:
        return f"/dev/video{camera_id}"  # Default to Linux-style


def get_platform_backend() -> str:
    """Return the single appropriate AV input backend for the current platform."""
    if IS_WINDOWS:
        return 'dshow'
    elif IS_LINUX:
        return 'v4l2'
    else:
        # macOS or others
        return 'avfoundation'


def list_windows_cameras() -> List[str]:
    """List available Windows camera names using DirectShow"""
    available_cameras = []
    
    try:
        # Best-effort probe; DirectShow device enumeration isn't exposed directly via PyAV.
        av.open("video=", format='dshow')
    except Exception as e:
        logger.debug(f"Error listing Windows cameras: {e}")
    
    # Try common camera names and indices
    test_cameras = [
        "Integrated Webcam",
        "USB2.0 HD UVC WebCam", 
        "USB Camera",
        "Webcam",
        "Camera",
        # Note: DirectShow requires names; numeric indices generally won't work.
    ]
    
    for camera_name in test_cameras:
        try:
            device_path = get_camera_device_path(camera_name)
            container = av.open(device_path, format='dshow')
            if container.streams.video:
                available_cameras.append(camera_name)
            container.close()
        except:
            continue
    
    return available_cameras


def list_available_cameras() -> List:
    """List available camera devices based on platform"""
    available_cameras = []
    
    if IS_WINDOWS:
        # On Windows, list camera names (best-effort)
        available_cameras = list_windows_cameras()
    elif IS_LINUX:
        # On Linux, check /dev/video* devices
        for i in range(10):
            device_path = f"/dev/video{i}"
            if os.path.exists(device_path):
                try:
                    container = av.open(device_path, format='v4l2')
                    if container.streams.video:
                        available_cameras.append(i)
                    container.close()
                except:
                    continue
    else:
        # macOS (avfoundation) or other fallback: we cannot reliably enumerate here without FFmpeg CLI.
        available_cameras = []
    
    return available_cameras


def resolve_windows_camera_name(camera_id) -> Optional[str]:
    """Best-effort: map a numeric/unknown Windows camera_id to a plausible DirectShow name."""
    if isinstance(camera_id, str) and camera_id.strip():
        return camera_id
    # Probe a small list of common device names
    for name in [
        "Integrated Webcam",
        "USB2.0 HD UVC WebCam",
        "USB Camera",
        "Webcam",
        "Camera",
    ]:
        try:
            device_path = f"video={name}"
            container = av.open(device_path, format='dshow')
            if container.streams.video:
                container.close()
                return name
            container.close()
        except Exception:
            continue
    return None
