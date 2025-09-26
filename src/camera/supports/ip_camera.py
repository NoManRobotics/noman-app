import cv2
from .base_camera import BaseCamera

class IpCamera(BaseCamera):
    """IP camera implementation, can be used to connect to phone cameras or other network cameras"""
    
    def __init__(self, ip_address, port=8081, username="", password="", protocol="http", path="", width=640, height=480):
        """
        Args:
            ip_address (str): Camera IP address
            port (int): Port number, default 8081
            username (str): Username, default ""
            password (str): Password, default ""
            protocol (str): Protocol type ("http", "rtsp", "mjpeg"), default "http"
            path (str): URL path after the address, default ""
            width (int): Camera width, default is 640
            height (int): Camera height, default is 480
        """
        self.ip_address = ip_address
        self.port = port
        self.username = username
        self.password = password
        self.protocol = protocol.lower()
        self.path = path
        self.url = self._build_url()
        self.cap = None
        
        # Default resolution and frame rate
        self.width = width
        self.height = height
        self.fps = 30
        
    def _build_url(self):
        """Build camera URL based on protocol and authentication"""
        # Build authentication part
        if self.username and self.password:
            auth = f"{self.username}:{self.password}@"
        else:
            auth = ""
            
        # Build path part
        path = self.path if self.path.startswith('/') else f"/{self.path}" if self.path else ""
        
        # Build URL based on protocol
        if self.protocol == "rtsp":
            return f"rtsp://{auth}{self.ip_address}:{self.port}{path}"
        elif self.protocol == "mjpeg":
            return f"http://{auth}{self.ip_address}:{self.port}{path}"
        else:  # default http
            return f"http://{auth}{self.ip_address}:{self.port}{path}"
            
    def get_protocol_info(self):
        """Get information about common protocol configurations"""
        return {
            "http": {
                "name": "HTTP Stream",
                "default_port": 8081,
                "common_paths": ["", "/video", "/stream", "/cam/realmonitor?channel=1&subtype=0"]
            },
            "rtsp": {
                "name": "RTSP Stream", 
                "default_port": 554,
                "common_paths": ["", "/live", "/stream1", "/cam/realmonitor?channel=1&subtype=0", "/user=admin&password=&channel=1&stream=0.sdp"]
            },
            "mjpeg": {
                "name": "MJPEG Stream",
                "default_port": 8080,
                "common_paths": ["", "/video.mjpg", "/mjpeg", "/cgi-bin/mjpg/video.cgi"]
            }
        }
        
    def initialize(self):
        """Initialize IP camera connection"""
        try:
            print(f"Connecting to IP camera: {self.url}")
            self.cap = cv2.VideoCapture(self.url)
            
            if not self.cap.isOpened():
                print(f"Unable to connect to IP camera: {self.url}")
                return False
                
            # Set camera properties
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self.cap.set(cv2.CAP_PROP_FPS, self.fps)
            
            # Read and display actual settings
            actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = int(self.cap.get(cv2.CAP_PROP_FPS))
            
            print(f"IP camera connection successful:")
            print(f"URL: {self.url}")
            print(f"Resolution: {actual_width}x{actual_height}")
            print(f"FPS: {actual_fps}")
            
            return True
            
        except Exception as e:
            print(f"IP camera connection failed: {str(e)}")
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
            print(f"IP camera connection closed: {self.url}") 