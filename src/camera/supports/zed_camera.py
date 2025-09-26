import cv2
import numpy as np
import logging

try:
    import pyzed.sl as sl
    ZED_AVAILABLE = True
except ImportError:
    ZED_AVAILABLE = False
    logging.warning("ZED SDK not installed, ZED camera functionality will not be available")

from .base_camera import BaseCamera

class ZEDCamera(BaseCamera):
    """ZED stereo camera implementation"""
    
    def __init__(self):
        self.zed = None
        self.runtime_params = None
        self.image = None
        self.point_cloud = None
        self.depth = None
        self._initialized = False
        
    def initialize(self):
        """Initialize ZED camera"""
        if self._initialized and self.zed and self.zed.is_opened():
            print("ZED camera already initialized")
            return True
            
        # Ensure previous instance is properly released
        self.release()
        
        try:
            # Initialize ZED camera
            init_params = sl.InitParameters()
            
            # Basic parameter settings
            init_params.depth_mode = sl.DEPTH_MODE.PERFORMANCE
            init_params.coordinate_units = sl.UNIT.METER
            init_params.camera_resolution = sl.RESOLUTION.HD720
            init_params.camera_fps = 30
            
            # Fault tolerance parameter settings
            init_params.depth_minimum_distance = 0.3
            init_params.depth_maximum_distance = 5.0
            init_params.sdk_verbose = True
            init_params.sdk_gpu_id = -1
            init_params.camera_disable_self_calib = False
            init_params.enable_image_enhancement = True
            init_params.sensors_required = False
            
            # Add configuration flags
            self.tracker_enabled = False  # Tracking disabled by default
            self.show_depth = True  # Show depth map by default
            
            logging.info("Initializing ZED camera...")
            self.zed = sl.Camera()
            status = self.zed.open(init_params)
            
            if status != sl.ERROR_CODE.SUCCESS:
                error_message = f"ZED camera initialization failed, error code: {status}"
                if status == sl.ERROR_CODE.CAMERA_NOT_DETECTED:
                    error_message += "\n- ZED camera not detected, please check USB connection"
                elif status == sl.ERROR_CODE.SENSOR_NOT_AVAILABLE:
                    error_message += "\n- Camera sensor not available"
                elif status == sl.ERROR_CODE.INVALID_RESOLUTION:
                    error_message += "\n- Invalid resolution setting"
                logging.error(error_message)
                self._initialized = False
                return False
            
            # Initialize runtime parameters
            self.runtime_params = sl.RuntimeParameters()
            try:
                self.runtime_params.sensing_mode = sl.SENSING_MODE.STANDARD
            except AttributeError:
                try:
                    self.runtime_params.enable_depth = True
                    self.runtime_params.enable_fill_mode = False
                    self.runtime_params.confidence_threshold = 50
                    self.runtime_params.texture_confidence_threshold = 100
                    self.runtime_params.remove_saturated_areas = True
                except AttributeError as e:
                    logging.warning(f"Runtime parameter setting failed: {str(e)}")
                    logging.info("Continuing with default parameters...")
            
            # Initialize image containers
            self.image = sl.Mat()
            self.point_cloud = sl.Mat()
            self.depth = sl.Mat()
            
            logging.info("ZED camera initialization successful, waiting for camera warm-up...")
            import time
            time.sleep(2)
            
            self._initialized = True
            logging.info("ZED camera ready")
            return True
            
        except Exception as e:
            logging.error(f"Exception during ZED camera initialization: {str(e)}")
            self._initialized = False
            self.release()
            return False
        
    def get_frame(self):
        """Get camera frame"""
        try:
            if not self.zed or not self.zed.is_opened():
                print("ZED camera not initialized or not open")
                return False, None
            
            # Get new frame
            if self.zed.grab(self.runtime_params) == sl.ERROR_CODE.SUCCESS:
                # Get left eye image
                self.zed.retrieve_image(self.image, sl.VIEW.LEFT)
                
                # Convert to OpenCV format
                image_ocv = self.image.get_data()
                
                # Add depth visualization if needed
                if self.show_depth:
                    # Get depth map
                    depth_mat = sl.Mat()
                    self.zed.retrieve_image(depth_mat, sl.VIEW.DEPTH)
                    
                    if depth_mat is not None:
                        # Convert to OpenCV format
                        depth_ocv = depth_mat.get_data()
                        
                        # Ensure depth map is valid
                        if depth_ocv is not None and depth_ocv.size > 0:
                            # Resize to match left eye image
                            depth_ocv = cv2.resize(depth_ocv, (image_ocv.shape[1], image_ocv.shape[0]))
                            
                            # Horizontal stack
                            image_ocv = np.hstack((image_ocv, depth_ocv))
                
                # Get point cloud data (only if tracking is enabled)
                if self.tracker_enabled:
                    self.zed.retrieve_measure(self.point_cloud, sl.MEASURE.XYZRGBA)
                
                return True, image_ocv
            else:
                print("Failed to get ZED camera frame")
                return False, None
                
        except Exception as e:
            print(f"Error getting camera frame: {str(e)}")
            if hasattr(e, '__traceback__'):
                import traceback
                traceback.print_exc()
            return False, None
        
    def release(self):
        """Release camera resources"""
        try:
            if self.zed:
                if self.zed.is_opened():
                    logging.info("Closing ZED camera...")
                    self.zed.close()
                self.zed = None
            self._initialized = False
            logging.info("ZED camera resources released")
        except Exception as e:
            logging.error(f"Error releasing ZED camera resources: {str(e)}")