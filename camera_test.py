#!/usr/bin/env python3
"""
Camera Test Script for Jetson
Tests camera connectivity and lists available cameras.
"""

import cv2
import numpy as np
import argparse
import time
from pathlib import Path

def test_camera(camera_id: int, duration: int = 5) -> bool:
    """Test if a camera is accessible and working"""
    print(f"Testing camera {camera_id}...")
    
    # Try different backends
    backends = [cv2.CAP_V4L2, cv2.CAP_GSTREAMER, cv2.CAP_ANY]
    
    for backend in backends:
        try:
            cap = cv2.VideoCapture(camera_id, backend)
            if cap.isOpened():
                print(f"  ✓ Camera {camera_id} opened with backend {backend}")
                
                # Try to read a frame
                ret, frame = cap.read()
                if ret:
                    print(f"  ✓ Successfully captured frame: {frame.shape}")
                    
                    # Save a test frame
                    test_dir = Path("test_frames")
                    test_dir.mkdir(exist_ok=True)
                    test_file = test_dir / f"test_camera_{camera_id}.jpg"
                    cv2.imwrite(str(test_file), frame)
                    print(f"  ✓ Saved test frame to {test_file}")
                    
                    # Capture for specified duration
                    start_time = time.time()
                    frame_count = 0
                    
                    while time.time() - start_time < duration:
                        ret, frame = cap.read()
                        if ret:
                            frame_count += 1
                        time.sleep(0.1)
                    
                    actual_fps = frame_count / duration
                    print(f"  ✓ Captured {frame_count} frames in {duration}s ({actual_fps:.1f} FPS)")
                    
                    cap.release()
                    return True
                else:
                    print(f"  ✗ Failed to read frame from camera {camera_id}")
                    cap.release()
            else:
                print(f"  ✗ Failed to open camera {camera_id} with backend {backend}")
                
        except Exception as e:
            print(f"  ✗ Error testing camera {camera_id} with backend {backend}: {e}")
    
    return False

def list_available_cameras(max_cameras: int = 10) -> list:
    """List all available cameras"""
    print(f"Scanning for cameras (0 to {max_cameras-1})...")
    
    available_cameras = []
    
    for i in range(max_cameras):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            # Try to read a frame to confirm it's working
            ret, frame = cap.read()
            if ret:
                available_cameras.append(i)
                print(f"  ✓ Camera {i} is available")
            cap.release()
        else:
            print(f"  ✗ Camera {i} is not available")
    
    return available_cameras

def main():
    parser = argparse.ArgumentParser(description="Test camera connectivity on Jetson")
    parser.add_argument("--scan", action="store_true", 
                       help="Scan for available cameras")
    parser.add_argument("--test", nargs="+", type=int, default=[0],
                       help="Test specific camera IDs")
    parser.add_argument("--duration", type=int, default=5,
                       help="Test duration in seconds (default: 5)")
    parser.add_argument("--max-cameras", type=int, default=10,
                       help="Maximum camera ID to scan (default: 10)")
    
    args = parser.parse_args()
    
    print("=== Jetson Camera Test Tool ===\n")
    
    if args.scan:
        print("1. Scanning for available cameras...")
        available = list_available_cameras(args.max_cameras)
        print(f"\nFound {len(available)} available cameras: {available}")
        
        if available:
            print("\n2. Testing available cameras...")
            for camera_id in available:
                test_camera(camera_id, args.duration)
                print()
    
    if args.test:
        print("Testing specified cameras...")
        for camera_id in args.test:
            test_camera(camera_id, args.duration)
            print()
    
    print("Test completed!")

if __name__ == "__main__":
    main() 