import cv2
from .base_camera import BaseCamera

class WebCamera(BaseCamera):
    """Standard webcam implementation"""
    
    def __init__(self, camera_id=0, width=640, height=480):
        """
        Args:
            camera_id (int): Camera ID, default is 0
            width (int): Camera width, default is 640
            height (int): Camera height, default is 480
        """
        self.camera_id = camera_id
        self.cap = None        

        self.width = width
        self.height = height
        self.fps = 30
        
    def initialize(self):
        """Initialize the camera"""
        try:
            self.cap = cv2.VideoCapture(self.camera_id)
            if not self.cap.isOpened():
                print(f"Unable to open camera ID {self.camera_id}")
                return False
                
            # Set camera properties
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self.cap.set(cv2.CAP_PROP_FPS, self.fps)
            
            # Read and display actual settings
            actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = int(self.cap.get(cv2.CAP_PROP_FPS))
            
            print(f"WebCamera {self.camera_id} initialization successful:")
            print(f"Resolution: {actual_width}x{actual_height}")
            print(f"FPS: {actual_fps}")
            
            return True
            
        except Exception as e:
            print(f"WebCamera initialization failed: {str(e)}")
            if self.cap is not None:
                self.cap.release()
                self.cap = None
            return False
        
    def get_frame(self):
        """Get a single frame from the camera"""
        if self.cap is None:
            return False, None
        return self.cap.read()
        
    def release(self):
        """Release camera resources"""
        if self.cap is not None:
            self.cap.release()
            self.cap = None
