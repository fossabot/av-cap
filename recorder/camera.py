import av
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
import logging
from PIL import Image
import platform
import os
from .utils import _maintain_fps, should_stop, get_camera_device_path, get_platform_backend, resolve_windows_camera_name

logger = logging.getLogger(__name__)

# Platform detection
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
IS_JETSON = os.path.exists("/etc/nv_tegra_release") if IS_LINUX else False


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
        # Mock mode fields
        self.mock_mode = False
        self.mock_width = 1280
        self.mock_height = 720

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
            # Enable mock mode if camera cannot be opened
            logger.warning("Falling back to mock mode: generating random frames")
            self.is_running = True
            self.mock_mode = True
            # Try to parse desired video size from options if present
            try:
                size = self._get_format_options(input_format).get('video_size', '1280x720')
                w, h = size.split('x')
                self.mock_width = int(w)
                self.mock_height = int(h)
            except Exception:
                pass
            return True

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
        if not self.is_running:
            return None

        # Mock frame generation path
        if self.mock_mode:
            try:
                # Generate random RGB image using os.urandom to avoid numpy dependency
                num_bytes = self.mock_width * self.mock_height * 3
                random_bytes = os.urandom(num_bytes)
                pil_image = Image.frombytes('RGB', (self.mock_width, self.mock_height), random_bytes)
                return pil_image
            except Exception as e:
                logger.error(f"Failed to generate mock frame: {e}")
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
