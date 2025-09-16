#!/usr/bin/env python3
"""
Multi-Camera Capture System for Jetson
Captures frames from multiple cameras and saves them with timestamps.
Uses av (PyAV) for video capture and Pillow for image processing.
"""

import av
import argparse
import time
from datetime import datetime
from pathlib import Path
import yaml
import threading
from typing import List, Dict, Optional
import logging
from PIL import Image
import platform
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Platform detection
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
IS_JETSON = os.path.exists("/etc/nv_tegra_release") if IS_LINUX else False

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


def _maintain_fps(loop_start_time: float, frame_interval: float) -> None:
    """Sleep just enough to maintain target FPS based on loop start time."""
    elapsed = time.time() - loop_start_time
    if elapsed < frame_interval:
        time.sleep(frame_interval - elapsed)


def get_setting(cli_value, config_value, default):
    """Resolve a setting with CLI taking precedence over config, then default."""
    return cli_value if cli_value is not None else (config_value if config_value is not None else default)


def should_stop(start_time: float, duration: Optional[int]) -> bool:
    """Return True if duration is set and has elapsed since start_time."""
    return duration is not None and (time.time() - start_time) >= duration


class CameraCapture:
    """Handles capture from a single camera using av (PyAV)"""

    def __init__(self, camera_id, output_dir: str, fps: int = 30):
        # On Windows, prefer device names for DirectShow. If numeric provided, try to resolve.
        if IS_WINDOWS and not isinstance(camera_id, str):
            resolved = resolve_windows_camera_name(camera_id)
            self.camera_id = resolved if resolved is not None else camera_id
        else:
            self.camera_id = camera_id
        # Create safe directory name from camera_id
        safe_camera_name = str(camera_id).replace(" ", "_").replace(":", "_")
        self.output_dir = Path(output_dir) / f"camera_{safe_camera_name}"
        self.fps = fps
        self.is_running = False
        self.container = None
        self.video_stream = None
        self.frame_count = 0

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Initialized camera {camera_id} with output directory: {self.output_dir}")

    def start(self) -> bool:
        """Start camera capture"""
        try:
            # Get platform-specific backend
            input_format = get_platform_backend()
            device_path = get_camera_device_path(self.camera_id)
            
            logger.info(f"Platform: {platform.system()}, Jetson: {IS_JETSON}")
            logger.info(f"Using backend: {input_format}")
            
            # Create input URL based on platform and format
            input_url = self._get_input_url(input_format, device_path)
            
            # Build a list of option attempts for better compatibility, especially on Windows/dshow
            option_attempts: List[Dict[str, str]] = []
            base_options = self._get_format_options(input_format)
            
            if input_format == 'dshow':
                # Many dshow devices fail if you force size/framerate. Try progressively.
                option_attempts = [
                    {},
                    {'framerate': base_options.get('framerate', '30')},
                    {'video_size': '640x480'},
                    {'video_size': '1280x720'},
                    {'video_size': '1920x1080'},
                    {'video_size': '1280x720', 'framerate': base_options.get('framerate', '30')},
                ]
            else:
                option_attempts = [base_options]
            
            last_error: Optional[Exception] = None
            for opts in option_attempts:
                try:
                    logger.debug(f"Opening with {input_format} URL: {input_url}, options: {opts}")
                    self.container = av.open(input_url, format=input_format, options=opts)
                    self.video_stream = self.container.streams.video[0]
                    self.video_stream.thread_type = 'AUTO'
                    logger.info(f"Camera {self.camera_id} opened with format {input_format} and options {opts}")
                    self.is_running = True
                    return True
                except Exception as e:
                    last_error = e
                    if self.container:
                        try:
                            self.container.close()
                        finally:
                            self.container = None
                    continue
            logger.error(f"Failed to open camera {self.camera_id} with format {input_format}: {last_error}")
            return False

        except Exception as e:
            logger.error(f"Error starting camera {self.camera_id}: {e}")
            return False

    def _get_input_url(self, input_format: str, device_path: str) -> str:
        """Get the input URL based on format and platform"""
        if input_format == 'v4l2':
            return device_path
        elif input_format == 'dshow':
            return device_path
        else:  # avfoundation or other
            return device_path

    def _get_format_options(self, input_format: str) -> Dict[str, str]:
        """Get format-specific options"""
        options = {
            'video_size': '1920x1080',
            'framerate': str(self.fps)
        }
        
        if input_format == 'dshow':
            options['video_size'] = '1920x1080'
        elif input_format == 'avfoundation':
            # avfoundation typically uses options like 'pixel_format'
            pass
            
        return options

    def stop(self):
        """Stop camera capture"""
        self.is_running = False
        if self.container:
            self.container.close()
            self.container = None
        logger.info(f"Camera {self.camera_id} stopped")

    def capture_frame(self) -> Optional[Image.Image]:
        """Capture a single frame"""
        if not self.is_running or not self.container:
            return None

        try:
            # Decode frames from the video stream
            for frame in self.container.decode(self.video_stream):
                # Convert to PIL Image directly
                pil_image = frame.to_image()
                logger.debug(f"Captured frame from camera {self.camera_id}")
                return pil_image
        except Exception as e:
            logger.error(f"Failed to capture frame from camera {self.camera_id}: {e}")
        return None

    def save_frame(self, frame: Image.Image) -> str:
        """Save frame with timestamp using Pillow"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        filename = f"camera_{self.camera_id}_{timestamp}_{self.frame_count:06d}.jpg"
        filepath = self.output_dir / filename

        # Save PIL Image directly with high quality
        frame.save(str(filepath), 'JPEG', quality=95, optimize=True)
        self.frame_count += 1

        return str(filepath)

    def capture_save_frame(self) -> Optional[str]:
        """Capture a single frame and save it. Returns filepath if saved."""
        if not self.is_running:
            return None
        frame = self.capture_frame()
        if frame is None:
            return None
        return self.save_frame(frame)

    def run(self, duration: Optional[int] = None):
        """Run single camera capture loop"""
        if not self.start():
            logger.error("Failed to start camera")
            return

        logger.info("Using single camera mode (no threading)")
        frame_interval = 1.0 / self.fps
        start_time = time.time()

        try:
            if duration:
                logger.info(f"Capturing for {duration} seconds...")
            else:
                logger.info("Capturing continuously. Press Ctrl+C to stop...")

            while self.is_running:
                loop_start = time.time()

                filepath = self.capture_save_frame()
                if filepath:
                    logger.debug(f"Saved frame: {filepath}")

                # Check duration limit
                if should_stop(start_time, duration):
                    break

                # Maintain FPS
                _maintain_fps(loop_start, frame_interval)

        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            self.stop()


class MultiCameraCapture:
    """Manages multiple camera captures with threading"""

    def __init__(self, camera_ids: List, output_dir: str, fps: int = 30):
        self.camera_ids = camera_ids
        self.output_dir = output_dir
        self.fps = fps
        self.cameras: Dict = {}
        self.is_running = False
        self.threads: List[threading.Thread] = []

    def detect_available_cameras(self) -> Dict:
        """Detect and start available cameras, returning started CameraCapture objects."""
        available_cameras: Dict = {}

        for camera_id in self.camera_ids:
            camera = CameraCapture(camera_id, self.output_dir, self.fps)
            if camera.start():
                # Test if we can actually capture a frame
                frame = camera.capture_frame()
                if frame is not None:
                    logger.info(f"Camera {camera_id} is available")
                    available_cameras[camera_id] = camera
                    continue
                # If frame capture failed, release the resource
                camera.stop()
                logger.debug(f"Camera {camera_id} opened but failed to capture a frame")
            else:
                logger.debug(f"Camera {camera_id} is not available")

        return available_cameras

    def start_all(self) -> bool:
        """Start all available cameras"""
        detected = self.detect_available_cameras()

        if not detected:
            logger.error("No available cameras found")
            return False

        self.cameras = detected
        logger.info(f"Started {len(self.cameras)} available cameras: {list(self.cameras.keys())}")

        self.is_running = True
        return True

    def stop_all(self):
        """Stop all cameras"""
        logger.info("Stopping all cameras...")
        self.is_running = False

        for camera in self.cameras.values():
            camera.stop()

        # Wait for threads to finish
        for thread in self.threads:
            thread.join()

    def capture_loop(self, camera_id):
        """Continuous capture loop for a single camera (threaded mode)"""
        camera = self.cameras[camera_id]
        frame_interval = 1.0 / self.fps

        logger.info(f"Starting capture loop for camera {camera_id}")

        while self.is_running:
            start_time = time.time()

            filepath = camera.capture_save_frame()
            if filepath:
                logger.debug(f"Saved frame from camera {camera_id}: {filepath}")

            # Maintain FPS
            _maintain_fps(start_time, frame_interval)

    def start_capture_threads(self):
        """Start capture threads for all cameras"""
        self.threads = []

        for camera_id in self.cameras.keys():
            thread = threading.Thread(
                target=self.capture_loop,
                args=(camera_id,),
                daemon=True
            )
            thread.start()
            self.threads.append(thread)

        logger.info(f"Started {len(self.threads)} capture threads")

    def run(self, duration: Optional[int] = None):
        """Run the capture system with threading"""
        if not self.start_all():
            logger.error("Failed to start cameras")
            return
        logger.info(f"Started {len(self.cameras)} cameras with threading")

        self.start_capture_threads()

        try:
            if duration:
                logger.info(f"Capturing for {duration} seconds...")
            else:
                logger.info("Capturing continuously. Press Ctrl+C to stop...")

            start_time = time.time()
            while True:
                if should_stop(start_time, duration):
                    break
                time.sleep(1)

        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            self.stop_all()


def main():
    parser = argparse.ArgumentParser(description="Multi-Camera Capture System for Jetson")
    parser.add_argument("--config", type=str, default="./config.yaml",
                       help="Path to YAML config with cameras/output_dir/fps/duration (default: ./config.yaml)")
    parser.add_argument("--cameras", nargs="+", default=None,
                       help="Camera IDs or names to capture from (overrides config). On Windows, use names like 'Integrated Webcam'")
    parser.add_argument("--output", type=str, default=None,
                       help="Output directory for captured frames (overrides config)")
    parser.add_argument("--fps", type=int, default=None,
                       help="Frames per second for each camera (overrides config)")
    parser.add_argument("--duration", type=int, default=None,
                       help="Capture duration in seconds (default: continuous)")
    parser.add_argument("--list-cameras", action="store_true",
                       help="List available cameras and exit")

    args = parser.parse_args()

    # Handle list cameras option
    if args.list_cameras:
        print(f"Platform: {platform.system()}")
        print(f"Jetson detected: {IS_JETSON}")
        print("Scanning for available cameras...")
        
        available_cameras = list_available_cameras()
        if available_cameras:
            print(f"Found {len(available_cameras)} available cameras: {available_cameras}")
        else:
            print("No cameras found")
        return

    # Load config YAML from the path specified in --config
    config_data = {}
    config_path = Path(args.config) if args.config else None

    if config_path is not None and config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f) or {}
            logger.info(f"Loaded config from {config_path}")
        except Exception as e:
            logger.error(f"Failed to load config file {config_path}: {e}")
    else:
        logger.info("Config file not found; using CLI values or defaults")

    # Determine effective settings with CLI overriding config, and sensible defaults
    effective_cameras = get_setting(args.cameras, config_data.get("cameras"), [0])
    # Only coerce to int on Linux. On Windows/macOS, keep strings to support backend requirements.
    if IS_LINUX:
        try:
            effective_cameras = [int(cam) for cam in effective_cameras] if effective_cameras else [0]
        except (ValueError, TypeError):
            pass
    
    effective_output = get_setting(args.output, config_data.get("output_dir"), "./frames")
    effective_fps = int(get_setting(args.fps, config_data.get("fps"), 30))
    effective_duration = get_setting(args.duration, config_data.get("duration"), None)

    # Create output directory
    output_dir = Path(effective_output)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Starting multi-camera capture system")
    logger.info(f"Platform: {platform.system()}")
    logger.info(f"Jetson detected: {IS_JETSON}")
    logger.info(f"Cameras: {effective_cameras}")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"FPS: {effective_fps}")

    # Choose the appropriate capture system based on camera count
    if len(effective_cameras) == 1:
        # Use single camera mode for better performance
        logger.info("Single camera detected - using optimized single camera mode")
        camera = CameraCapture(effective_cameras[0], str(output_dir), effective_fps)
        camera.run(effective_duration)
    else:
        # Use multi-camera mode with threading
        logger.info("Multiple cameras detected - using threaded multi-camera mode")
        capture_system = MultiCameraCapture(effective_cameras, str(output_dir), effective_fps)
        capture_system.run(effective_duration)

if __name__ == "__main__":
    main()
