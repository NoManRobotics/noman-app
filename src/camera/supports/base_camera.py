from abc import ABC, abstractmethod

class BaseCamera(ABC):
    """Base Camera Class"""
    
    @abstractmethod
    def initialize(self):
        """Initialize the camera
        Returns:
            bool: True if initialization is successful, False otherwise
        """
        pass
        
    @abstractmethod
    def get_frame(self):
        """Get a single frame from the camera
        Returns:
            tuple: (success, frame)
            - success: bool, True if a frame was successfully captured
            - frame: np.ndarray, Image data in BGR format
        """
        pass
        
    @abstractmethod
    def release(self):
        """Release camera resources"""
        pass 