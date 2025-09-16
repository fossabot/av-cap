import threading
import time
import logging
from typing import List, Dict, Optional
from .camera import CameraCapture
from .utils import _maintain_fps, should_stop

logger = logging.getLogger(__name__)


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
