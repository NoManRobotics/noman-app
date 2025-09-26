import os
import cv2
import numpy as np
import tempfile
import traceback
import tkinter as tk
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, A3, A5, LETTER
from reportlab.lib.units import mm

from utils.math import euler_to_rotation_matrix
from camera.supports import WebCamera, ZEDCamera, IpCamera

class CameraController:
    def __init__(self):
        # init camera list
        self.cameras = []
        
        # view mode: 'single', 'dual', 'none'
        self.view_mode = 'none'

        self.max_cameras = 2
        self.active_cameras = []
        self.max_active_cameras = 2
        
        # video stream status
        self.is_running = False
        
        # camera status changed callback function
        self.on_camera_status_changed = None
        self.on_frame_update = None

        # initialise charuco board parameters
        self.aruco_dict = None
        self.calibration_board = None
        self.board_img_bgr = None
        self.board_corners = 0

        # intrinsic calibration
        self.calibration_corners_all = []  # corners in each image
        self.calibration_ids_all = []  # corners id in each image
        self.calibration_img_size = None  # image size
        self.calibration_frames = []  # calibration images for preview
        self.camera_matrix = None  # camera intrinsic matrix
        self.dist_coeffs = None  # distortion coefficients
        self.rvecs = []  # rotation vectors
        self.tvecs = []  # translation vectors
        
        # handeye calibration
        self.handeye_mode = 'eye_in_hand'  # calibration mode: 'eye_in_hand' or 'eye_to_hand'
        self.robot_rotations = []  # robot pose rotation matrix (directly store rotation matrix)
        self.robot_translations = []  # robot pose translation vectors
        self.handeye_transform = None  # handeye transformation matrix
        
        # board to end effector offset (used in Eye-to-Hand)
        self.board_to_ee_offset = [32.0, 0.0, 2.0, 0.0, 0.0, 0.0]  # 6DOF offset [x, y, z, rx, ry, rz]
        self.board_to_ee_transform = None  # offset transformation matrix
        
        # camera parameters setting
        self.focal_length_mm = 3.6  # default focal length (mm)
        
        # 2D localization offset setting
        self.x_offset_mm = 0.0  # X-offset (mm)
        self.y_offset_mm = 0.0  # Y-offset (mm)
        self.z_height_mm = 0.0  # Z-height (mm)
    
    def get_max_cameras(self):
        """get maximum camera number"""
        return self.max_cameras
    
    def get_camera_count(self):
        """get current camera number"""
        return len(self.cameras)
    
    def get_active_cameras(self):
        """get current active camera index list"""
        return self.active_cameras.copy()
    
    def get_view_mode(self):
        """get current view mode"""
        return self.view_mode
    
    def set_callbacks(self, on_camera_status_changed=None, on_frame_update=None):
        """set callback functions"""
        self.on_camera_status_changed = on_camera_status_changed
        self.on_frame_update = on_frame_update
    
    def list_available_cameras(self, max_cameras=10):
        """list available cameras in the system
        
        Args:
            max_cameras: maximum number of cameras to detect, default is 10
            
        Returns:
            list: list of available cameras, each element is a dictionary, contains:
                 - id: camera ID
                 - name: camera name(if available)
                 - available: whether available
        """
        available_cameras = []
        
        # try to open each camera ID to check its availability
        for i in range(max_cameras):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                # try to get camera name
                camera_name = f"Camera {i}"
                try:
                    # on some systems, camera name can be retrieved
                    backend_name = cap.getBackendName()
                    if backend_name:
                        camera_name = f"Camera {i} ({backend_name})"
                except:
                    pass
                
                available_cameras.append({
                    "id": i,
                    "name": camera_name,
                    "available": True
                })
                
                # release camera
                cap.release()
            else:
                available_cameras.append({
                    "id": i,
                    "name": f"Camera {i}",
                    "available": False
                })
        
        # filter and return only available cameras
        return [cam for cam in available_cameras if cam["available"]]
    
    def create_webcam(self, camera_id, width=640, height=480):
        """create webcam"""
        if len(self.cameras) >= self.max_cameras:
            return False, "maximum camera number reached"
            
        try:
            camera = WebCamera(camera_id=camera_id, width=width, height=height)
            success = camera.initialize()
            
            if success:
                self.cameras.append(camera)
                camera_info = {
                    "type": "WebCamera",
                    "id": camera_id,
                    "status": "connected",
                    "index": len(self.cameras) - 1,
                    "active": False
                }
                
                # notify status change
                if self.on_camera_status_changed:
                    self.on_camera_status_changed("add", camera_info)
                
                return True, camera_info
            else:
                return False, "camera initialization failed"
                
        except Exception as e:
            return False, f"failed to create webcam: {str(e)}"
    
    def create_ip_camera(self, ip_address, port, username, password, protocol="http", path="", width=640, height=480):
        """create IP camera"""
        if len(self.cameras) >= self.max_cameras:
            return False, "maximum camera number reached"
            
        try:
            camera = IpCamera(ip_address=ip_address, port=port, username=username, password=password, protocol=protocol, path=path, width=width, height=height)
            success = camera.initialize()
            
            if success:
                self.cameras.append(camera)
                camera_info = {
                    "type": "IpCamera",
                    "address": f"{protocol}://{ip_address}:{port}{path}",
                    "status": "connected",
                    "index": len(self.cameras) - 1,
                    "active": False
                }
                
                # notify status change
                if self.on_camera_status_changed:
                    self.on_camera_status_changed("add", camera_info)
                
                return True, camera_info
            else:
                return False, "camera initialization failed"
                
        except Exception as e:
            return False, f"failed to create IP camera: {str(e)}"
    
    def create_zed_camera(self):
        """create ZED camera"""
        if len(self.cameras) >= self.max_cameras:
            return False, "maximum camera number reached"
            
        try:
            camera = ZEDCamera()
            success = camera.initialize()
            
            if success:
                self.cameras.append(camera)
                camera_info = {
                    "type": "ZEDCamera",
                    "status": "connected",
                    "index": len(self.cameras) - 1,
                    "active": False
                }
                
                # notify status change
                if self.on_camera_status_changed:
                    self.on_camera_status_changed("add", camera_info)
                
                return True, camera_info
            else:
                return False, "camera initialization failed"
                
        except Exception as e:
            return False, f"failed to create ZED camera: {str(e)}"
    
    def activate_camera(self, index):
        """activate specified camera"""
        if 0 <= index < len(self.cameras):
            # check if already activated
            if index in self.active_cameras:
                return False
                
            # check if maximum active number reached
            if len(self.active_cameras) >= self.max_active_cameras:
                return False
                
            # activate camera
            self.active_cameras.append(index)
            
            # update camera status
            if self.on_camera_status_changed:
                self.on_camera_status_changed("update", {
                    "index": index,
                    "status": "activated",
                    "active": True
                })
            
            # automatically set view mode based on active camera count
            if len(self.active_cameras) == 1:
                self.view_mode = 'single'
            elif len(self.active_cameras) == 2:
                self.view_mode = 'dual'
            
            # if video stream is not running, start it
            if not self.is_running:
                self.start_video_stream()
            
            return True
        return False
    
    def deactivate_camera(self, index):
        """deactivate specified camera"""
        if 0 <= index < len(self.cameras) and index in self.active_cameras:
            # remove from active list
            self.active_cameras.remove(index)
            
            # update camera status
            if self.on_camera_status_changed:
                self.on_camera_status_changed("update", {
                    "index": index,
                    "status": "connected",
                    "active": False
                })
            
            # if no active cameras, stop video stream
            if not self.active_cameras:
                self.is_running = False
                self.view_mode = 'none'
            # if only one active camera remains, switch to single view mode
            elif len(self.active_cameras) == 1 and self.view_mode == 'dual':
                self.view_mode = 'single'
            
            return True
        return False
    
    def remove_camera(self, index):
        """remove specified camera"""
        if 0 <= index < len(self.cameras):
            # if camera is activated, deactivate it first
            if index in self.active_cameras:
                self.deactivate_camera(index)
            
            # release camera resources
            self.cameras[index].release()
            
            # notify UI to remove this camera
            if self.on_camera_status_changed:
                self.on_camera_status_changed("remove", {"index": index})
            
            # remove camera object
            self.cameras.pop(index)
            
            # update indices of other cameras
            new_active_cameras = []
            for active_index in self.active_cameras:
                if active_index > index:
                    new_active_cameras.append(active_index - 1)
                elif active_index < index:
                    new_active_cameras.append(active_index)
            self.active_cameras = new_active_cameras
            
            # update indices of other cameras with index greater than removed camera
            for i in range(index, len(self.cameras)):
                if self.on_camera_status_changed:
                    self.on_camera_status_changed("update_index", {
                        "old_index": i + 1,
                        "new_index": i
                    })
            
            return True
        return False
    
    def start_video_stream(self):
        """start video stream"""
        if not self.active_cameras:
            return False
            
        self.is_running = True
        self._process_next_frame()
        return True
    
    def stop_video_stream(self):
        """stop video stream"""
        self.is_running = False
        return True
    
    def _process_next_frame(self):
        """process next frame"""
        if not self.is_running or not self.active_cameras:
            return
            
        frames = []
        
        # get frames from all active cameras
        for camera_index in self.active_cameras:
            camera = self.cameras[camera_index]
            success, frame = camera.get_frame()
            
            if success and frame is not None:    
                frames.append(frame)
            else:
                frames.append(None)
                # if frame acquisition fails, notify status change
                if self.on_camera_status_changed:
                    self.on_camera_status_changed("update", {
                        "index": camera_index,
                        "status": "failed to get video frame"
                    })
        
        # prepare frames based on view mode and active camera count
        if frames:
            if self.on_frame_update:
                self.on_frame_update(frames)
        
        # if still running, schedule next frame processing
        if self.is_running:
            # use external scheduler, notify through callback that this method needs to be called again
            if self.on_frame_update:
                self.on_frame_update(None, schedule_next=True)

    def get_charuco_board(self):
        """get current calibration board parameter information
        
        Returns:
            dict: dictionary containing calibration board information, returns None if board not generated
            contains following keys:
                - board_rows: calibration board rows
                - board_cols: calibration board columns
                - square_size: square size (mm)
                - marker_size: marker ratio
                - dictionary_str: ArUco dictionary type name
        """
        if self.calibration_board is None:
            return None
            
        # get parameters from calibration board object
        board_rows, board_cols = self.calibration_board.getChessboardSize()
        square_size = self.calibration_board.getSquareLength()
        marker_size = self.calibration_board.getMarkerLength() / square_size  # calculate ratio
        
        # determine dictionary type used
        dictionary_str = "DICT_4X4_50"  # default value
        aruco_dict_map = {
            cv2.aruco.DICT_4X4_50: "DICT_4X4_50",
            cv2.aruco.DICT_5X5_50: "DICT_5X5_50",
            cv2.aruco.DICT_6X6_50: "DICT_6X6_50",
            cv2.aruco.DICT_7X7_50: "DICT_7X7_50"
        }
        
        # get dictionary used by calibration board
        board_dict = self.calibration_board.getDictionary()
        
        # try to match dictionary type
        for dict_id, dict_name in aruco_dict_map.items():
            if board_dict.bytesList.shape == cv2.aruco.getPredefinedDictionary(dict_id).bytesList.shape:
                dictionary_str = dict_name
                break
        
        return {
            "board_rows": board_rows,
            "board_cols": board_cols,
            "square_size": square_size,
            "marker_size": marker_size,
            "dictionary_str": dictionary_str
        }
    
    def generate_charuco_board(self, board_rows, board_cols, square_size, marker_size, dictionary_str):
        """generate Charuco calibration board
        
        Args:
            board_rows: calibration board rows
            board_cols: calibration board columns
            square_size: square size (mm)
            marker_size: marker ratio
            dictionary_str: ArUco dictionary type name
            
        Returns:
            tuple: (success, result info, generated image)
        """
        try:

            self.board_corners = (board_rows-1) * (board_cols-1)
            
            # get ArUco dictionary
            aruco_dict_map = {
                "DICT_4X4_50": cv2.aruco.DICT_4X4_50,
                "DICT_5X5_50": cv2.aruco.DICT_5X5_50,
                "DICT_6X6_50": cv2.aruco.DICT_6X6_50,
                "DICT_7X7_50": cv2.aruco.DICT_7X7_50
            }
            
            # check if dictionary is supported
            if dictionary_str not in aruco_dict_map:
                return False, f"unsupported ArUco dictionary: {dictionary_str}", None
                
            # get dictionary
            self.aruco_dict = cv2.aruco.getPredefinedDictionary(aruco_dict_map[dictionary_str])
            
            self.calibration_board = cv2.aruco.CharucoBoard(
                size=(board_cols, board_rows),
                squareLength=float(square_size),
                markerLength=float(square_size * marker_size),
                dictionary=self.aruco_dict
            )
            
            # calculate physical size of calibration board (mm)
            board_width_mm = board_cols * square_size
            board_height_mm = board_rows * square_size
            
            # get system real DPI (cross-platform method)
            dpi = self._get_system_dpi()
            
            # convert mm to pixels
            pixels_per_mm = dpi / 25.4
            
            # calculate image size (pixels)
            img_width = int(board_width_mm * pixels_per_mm)
            img_height = int(board_height_mm * pixels_per_mm)
            
            # add margin (10%)
            margin_pixels = 0
            
            # generate image
            board_img = self.calibration_board.generateImage((img_width, img_height), marginSize=margin_pixels)
            
            # convert grayscale image to BGR format
            self.board_img_bgr = cv2.cvtColor(board_img, cv2.COLOR_GRAY2BGR)
            
            return True, "calibration board generated successfully", self.board_img_bgr
            
        except Exception as e:
            traceback.print_exc()
            return False, f"failed to generate calibration board: {str(e)}", None
        
    def save_charuco_board(self, file_path, save_option="png", print_size="A4"):
        """save Charuco calibration board to file
        
        Args:
            file_path: save path
            save_option: save format, "png" or "pdf"
            print_size: print paper size, supports "A4", "A3", "A5", "LETTER"
            
        Returns:
            tuple: (success, result info)
        """
        try:
            if self.calibration_board is None or self.board_img_bgr is None:
                return False, "please generate calibration board first"
                
            if save_option.lower() == "png":
                # save as PNG
                cv2.imwrite(file_path, self.board_img_bgr)
                return True, f"calibration board saved as PNG: {file_path}"
                
            elif save_option.lower() == "pdf":
                # save as PDF, ensure precise physical dimensions
                try:
                    # get calibration board parameters
                    board_rows, board_cols = self.calibration_board.getChessboardSize()
                    square_size = self.calibration_board.getSquareLength()
                    
                    # calculate calibration board physical size (mm)
                    board_width_mm = board_cols * square_size
                    board_height_mm = board_rows * square_size
                    
                    # set paper size
                    page_sizes = {
                        "A4": (210, 297),
                        "A3": (297, 420),
                        "A5": (148, 210),
                        "LETTER": (216, 279),
                    }
                    
                    # use predefined paper size
                    if print_size in page_sizes:
                        page_width_mm, page_height_mm = page_sizes[print_size]
                    else:
                        return False, f"unsupported paper size: {print_size}, supported sizes: {', '.join(page_sizes.keys())}"
                    
                    # check if calibration board exceeds paper size
                    if board_width_mm > page_width_mm or board_height_mm > page_height_mm:
                        return False, f"calibration board size ({board_width_mm}mm x {board_height_mm}mm) exceeds paper size ({page_width_mm}mm x {page_height_mm}mm)"
                    
                    # convert OpenCV image to PIL format
                    img_rgb = cv2.cvtColor(self.board_img_bgr, cv2.COLOR_BGR2RGB)
                    pil_img = Image.fromarray(img_rgb)
                    
                    # create PDF and set paper size
                    page_size_map = {
                        "A4": A4,
                        "A3": A3,
                        "A5": A5,
                        "LETTER": LETTER
                    }
                    c = canvas.Canvas(file_path, pagesize=page_size_map[print_size])
                    
                    # calculate centered position
                    x_offset = (page_width_mm - board_width_mm) / 2
                    y_offset = (page_height_mm - board_height_mm) / 2
                    
                    # save as temporary file
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp:
                        temp_path = temp.name
                        pil_img.save(temp_path)
                    
                    # insert image and set precise dimensions, ensure 1:1 ratio
                    c.drawImage(temp_path, x_offset*mm, y_offset*mm,
                                width=board_width_mm*mm, height=board_height_mm*mm)
                    
                    # add ruler (optional) draw scale lines around page
                    c.setStrokeColorRGB(0, 0, 0)
                    c.setLineWidth(0.2)
                    
                    c.save()
                    
                    # delete temporary file
                    os.unlink(temp_path)
                    
                    return True, f"calibration board saved as {print_size} PDF: {file_path}, please print at 1:1 scale"
                    
                except ImportError:
                    return False, "saving PDF requires reportlab library installation, please use pip install reportlab"
            else:
                return False, f"unsupported save format: {save_option}, please use 'png' or 'pdf'"
            
        except Exception as e:
            traceback.print_exc()
            return False, f"failed to save calibration board: {str(e)}"

    def _get_system_dpi(self):
        """get system real DPI value (cross-platform)"""
        try:
            # create temporary Tkinter window to get DPI
            root = tk.Tk()
            root.withdraw()  # hide window
            
            # use tkinter to get DPI (cross-platform method)
            # 1 inch = 72 points, calculate corresponding pixel count
            screen_dpi_x = root.winfo_fpixels('1i')
            screen_dpi_y = root.winfo_fpixels('1i')
            
            root.destroy()
            
            # return average DPI value
            dpi = (screen_dpi_x + screen_dpi_y) / 2
            
            # if acquisition fails or value is abnormal, use standard print DPI
            if dpi < 72 or dpi > 600:
                return 300  # standard print DPI
            
            return dpi
            
        except Exception as e:
            print(f"failed to get system DPI: {str(e)}, using default value 300")
            return 300

    def capture_calibration_sample(self, camera_index, robot_pose=None):
        """capture one frame for calibration (supports intrinsic calibration and hand-eye calibration integration)
        
        Args:
            camera_index: camera index
            robot_pose: robot pose [x,y,z,roll,pitch,yaw], if None then only intrinsic calibration
            
        Returns:
            tuple: (success, result info, preview image, detected corner count)
        """
        if self.calibration_board is None:
            return False, "please initialize calibration board first", None, 0
            
        if camera_index not in self.active_cameras:
            return False, "specified camera is not activated", None, 0
            
        try:
            camera = self.cameras[camera_index]
            success, frame = camera.get_frame()
            
            if not success or frame is None:
                return False, "failed to get image", None, 0
                
            # convert to grayscale image
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # record image size (only once)
            if self.calibration_img_size is None:
                self.calibration_img_size = gray.shape[::-1]
                
            # detect Charuco corners
            corners, ids, rejected = cv2.aruco.detectMarkers(
                gray, 
                self.calibration_board.getDictionary()
            )
            
            # if markers detected
            if ids is not None and len(ids) > 0:
                # draw detected markers on image
                cv2.aruco.drawDetectedMarkers(frame, corners, ids)
                
                # interpolate Charuco corners
                ret, charuco_corners, charuco_ids = cv2.aruco.interpolateCornersCharuco(
                    corners, ids, gray, self.calibration_board
                )
                
                # if enough corners detected
                if ret > int(0.8*self.board_corners):
                    # draw Charuco corners on image
                    cv2.aruco.drawDetectedCornersCharuco(frame, charuco_corners, charuco_ids)
                    
                    # add results to collected data
                    self.calibration_corners_all.append(charuco_corners)
                    self.calibration_ids_all.append(charuco_ids)
                    self.calibration_frames.append(frame.copy())
                    
                    # if robot pose provided, save hand-eye calibration data
                    if robot_pose is not None:
                        # convert robot pose to rotation matrix and translation vector
                        robot_tvec = np.array(robot_pose[:3]).reshape(3, 1)
                        roll, pitch, yaw = robot_pose[3:6]
                        robot_rot_matrix = euler_to_rotation_matrix(roll, pitch, yaw)
                        
                        # process offset in Eye-to-Hand mode
                        if self.handeye_mode == 'eye_to_hand':
                            if self.board_to_ee_transform is not None:
                                # create robot end effector transformation matrix
                                robot_transform = np.eye(4, dtype=np.float32)
                                robot_transform[:3, :3] = robot_rot_matrix
                                robot_transform[:3, 3] = robot_tvec.flatten()
                                
                                # calculate real pose of calibration board
                                board_transform = robot_transform @ self.board_to_ee_transform
                                
                                # extract rotation matrix and translation vector
                                actual_rot_matrix = board_transform[:3, :3]
                                actual_tvec = board_transform[:3, 3].reshape(3, 1)
                            else:
                                actual_rot_matrix = robot_rot_matrix
                                actual_tvec = robot_tvec
                        else:
                            # directly use robot pose for Eye-in-Hand or no offset
                            actual_rot_matrix = robot_rot_matrix
                            actual_tvec = robot_tvec
                        
                        # save hand-eye calibration data
                        self.robot_rotations.append(actual_rot_matrix)
                        self.robot_translations.append(actual_tvec)
                    
                    return True, f"captured {len(self.calibration_frames)} samples", frame, len(charuco_corners)
                else:
                    return False, "insufficient corners detected", frame, 0
            else:
                return False, "calibration board not detected", frame, 0
                
        except Exception as e:
            return False, f"failed to capture calibration sample: {str(e)}", None, 0
    
    def calibrate(self):
        """execute camera calibration (intrinsic calibration or intrinsic + hand-eye calibration integration)
        
        Returns:
            tuple: (success, result info, calibration result dictionary)
                   calibration result dictionary contains:
                   - camera_matrix: camera intrinsic matrix
                   - dist_coeffs: distortion coefficients
                   - reprojection_error: intrinsic calibration reprojection error
                   - handeye_transform: hand-eye transformation matrix (if hand-eye calibration performed)
                   - handeye_method: hand-eye calibration method used (if hand-eye calibration performed)
        """
        if self.calibration_board is None or len(self.calibration_corners_all) < 9:
            return False, "insufficient calibration data", {}
            
        try:
            # Intrinsic calibration
            # initialize camera matrix guess value
            if self.calibration_img_size:
                w, h = self.calibration_img_size
                
                # calculate initial focal length pixel value based on known focal length
                # if camera physical focal length is known, more accurate initial value can be used
                focal_length_mm = self.focal_length_mm  # use set focal length

                # estimate sensor type based on image resolution
                if w <= 640:  # small resolution, possibly 1/4 inch sensor
                    sensor_width_mm = 3.2   # 1/4 inch sensor about 3.2mm wide
                elif w <= 1280:  # medium resolution, possibly 1/3 inch sensor 
                    sensor_width_mm = 4.8   # 1/3 inch sensor about 4.8mm wide
                elif w <= 1920:  # Full HD resolution, possibly 1/2.5 inch sensor
                    sensor_width_mm = 5.76  # 1/2.5 inch sensor about 5.76mm wide
                else:  # high resolution, possibly larger sensor
                    sensor_width_mm = 6.4   # 1/2 inch sensor about 6.4mm wide
                
                # calculate focal length pixel value
                fx = (focal_length_mm * w) / sensor_width_mm
                fy = fx  # assume pixels are square
                
                # principal point usually at image center
                cx = w / 2
                cy = h / 2
                
                camera_matrix_init = np.array([
                    [fx, 0, cx],
                    [0, fy, cy],
                    [0, 0, 1]
                ], dtype=np.float32)
                dist_coeffs_init = np.zeros((5, 1), dtype=np.float32)
                
            else:
                return False, "unknown image size", {}
            
            # execute intrinsic calibration
            flags = (
                cv2.CALIB_USE_INTRINSIC_GUESS + 
                cv2.CALIB_RATIONAL_MODEL
            )
            
            ret, self.camera_matrix, self.dist_coeffs, self.rvecs, self.tvecs = cv2.aruco.calibrateCameraCharuco(
                self.calibration_corners_all,
                self.calibration_ids_all,
                self.calibration_board,
                self.calibration_img_size,
                camera_matrix_init,
                dist_coeffs_init,
                flags=flags
            )
            
            # calculate reprojection error of intrinsic calibration
            mean_error = self._calculate_reprojection_error()
            
            # create result dictionary
            result = {
                "camera_matrix": self.camera_matrix,
                "dist_coeffs": self.dist_coeffs,
                "reprojection_error": mean_error
            }

            # Hand-eye calibration
            # prepare hand-eye calibration data
            R_gripper2base = self.robot_rotations
            t_gripper2base = self.robot_translations
            R_target2cam = []
            t_target2cam = []
            
            # use rvecs and tvecs obtained from intrinsic calibration
            for i in range(min(len(self.robot_rotations), len(self.rvecs))):
                R_target2cam.append(self._rotation_vector_to_matrix(self.rvecs[i]))
                t_target2cam.append(self.tvecs[i])
            
            # try using multiple calibration methods
            methods = {
                "TSAI": cv2.CALIB_HAND_EYE_TSAI,
                "PARK": cv2.CALIB_HAND_EYE_PARK,
                "HORAUD": cv2.CALIB_HAND_EYE_HORAUD,
                "ANDREFF": cv2.CALIB_HAND_EYE_ANDREFF
            }
            
            all_results = {}
            horaud_result = None
            
            for method_name, method in methods.items():
                try:
                    if self.handeye_mode == 'eye_in_hand':
                        R_result, t_result = cv2.calibrateHandEye(
                            R_gripper2base, t_gripper2base,
                            R_target2cam, t_target2cam,
                            method=method
                        )
                    else:  # 'eye_to_hand'
                        # calculate inverse transformation
                        R_base2gripper = []
                        t_base2gripper = []
                        
                        for R, t in zip(R_gripper2base, t_gripper2base):
                            R_b2g = R.T
                            t_b2g = -R_b2g @ t
                            R_base2gripper.append(R_b2g)
                            t_base2gripper.append(t_b2g)
                        
                        R_result, t_result = cv2.calibrateHandEye(
                            R_gripper2base=R_base2gripper, 
                            t_gripper2base=t_base2gripper,
                            R_target2cam=R_target2cam, 
                            t_target2cam=t_target2cam,
                            method=method
                        )
                    
                    # create transformation matrix
                    transform = np.eye(4)
                    transform[:3, :3] = R_result
                    transform[:3, 3] = t_result.flatten()
                    
                    # save result
                    all_results[method_name] = transform
                    
                    # save HORAUD method result
                    if method_name == "HORAUD":
                        horaud_result = transform
                        
                except Exception as e:
                    print(f"method {method_name} failed: {str(e)}")
                    all_results[method_name] = None
                    continue
            
            # check if any method succeeded
            successful_methods = [method for method, result in all_results.items() if result is not None]
            if not successful_methods:
                return False, "hand-eye calibration failed", result
                
            # set hand-eye transform to HORAUD method result, if HORAUD fails use first successful method
            if horaud_result is not None:
                self.handeye_transform = horaud_result
            else:
                # if HORAUD fails, use first successful method
                first_successful_method = successful_methods[0]
                self.handeye_transform = all_results[first_successful_method]
                print(f"HORAUD method failed, using {first_successful_method} method result as default")
                
            result["handeye_transform"] = self.handeye_transform
            result["all_handeye_results"] = all_results
            
            return True, "calibration successful", result
                
        except Exception as e:
            traceback.print_exc()
            return False, f"calibration failed: {str(e)}", {}
        
    def set_handeye_mode(self, mode):
        """set hand-eye calibration mode
        
        Args:
            mode: 'eye_in_hand' camera mounted on robot end, 'eye_to_hand' camera fixed observing robot
            
        Returns:
            bool: whether setting successful
        """
        if mode in ['eye_in_hand', 'eye_to_hand']:
            self.handeye_mode = mode
            return True
        return False
    
    def set_board_to_ee_offset(self, offset):
        """set offset from calibration board to end effector
        
        Args:
            offset: 6DOF offset [x, y, z, roll, pitch, yaw]
                   - x, y, z: position offset (mm)
                   - roll, pitch, yaw: rotation offset (Euler angles, radians)
                   
        Returns:
            bool: whether setting successful
        """
        if offset is None:
            # clear offset
            self.board_to_ee_offset = None
            self.board_to_ee_transform = None
            return True
        
        if len(offset) != 6:
            print("offset must contain 6 values: [x, y, z, roll, pitch, yaw]")
            return False
            
        # save offset values
        self.board_to_ee_offset = np.array(offset, dtype=np.float32)
        
        # create offset transformation matrix
        offset_tvec = np.array(offset[0:3], dtype=np.float32).reshape(3, 1)
        # offset[3:6] is [roll, pitch, yaw] Euler angles
        offset_euler = offset[3:6]
        self.board_to_ee_transform = self._create_transform_matrix_from_euler(offset_euler, offset_tvec)
        
        return True
    
    def get_board_to_ee_offset(self):
        """get offset value from calibration board to end effector
        
        Returns:
            np.ndarray: 6DOF offset [x, y, z, roll, pitch, yaw], returns None if not set
                       - x, y, z: position offset (mm)
                       - roll, pitch, yaw: rotation offset (Euler angles, radians)
        """
        if self.board_to_ee_offset is not None:
            return self.board_to_ee_offset.copy()
        else:
            return None
    
    def _rotation_vector_to_matrix(self, rvec):
        """convert rotation vector to rotation matrix"""
        rot_mat, _ = cv2.Rodrigues(rvec)
        return rot_mat
        
    
    def _create_transform_matrix_from_euler(self, euler_angles, tvec):
        """create transformation matrix from Euler angles and translation vector
        
        Args:
            euler_angles: [roll, pitch, yaw] Euler angles (radians)
            tvec: translation vector (3,1) or (3,)
            
        Returns:
            np.ndarray: 4x4 transformation matrix
        """
        roll, pitch, yaw = euler_angles
        rot_mat = euler_to_rotation_matrix(roll, pitch, yaw)
        transform = np.eye(4, dtype=np.float32)
        transform[:3, :3] = rot_mat
        transform[:3, 3] = tvec.flatten()
        return transform
    
    def calculate_camera_pose(self, target_position, target_orientation):
        """calculate camera position and orientation in world coordinate system
        
        Args:
            target_position: robot end position [x, y, z] (mm)
            target_orientation: robot end pose [roll, pitch, yaw] (Euler angles, radians)
        
        Returns:
            tuple: (camera_pos_mm, camera_rot) camera position (mm) and rotation matrix
        """
        if self.handeye_transform is None:
            return None, None
            
        try:
            if self.handeye_mode == 'eye_in_hand':  
                # create robot end transformation matrix in base coordinate system
                roll, pitch, yaw = target_orientation
                robot_rot = euler_to_rotation_matrix(roll, pitch, yaw)
                robot_trans = np.eye(4)
                robot_trans[:3, :3] = robot_rot
                robot_trans[:3, 3] = target_position
                
                # calculate camera transformation matrix in base coordinate system
                camera_transform = robot_trans @ self.handeye_transform
                
                # extract camera position and orientation
                camera_pos_mm = camera_transform[:3, 3]
                camera_rot = camera_transform[:3, :3]
            else:  # 'eye_to_hand'
                camera_pos_mm = self.handeye_transform[:3, 3]
                camera_rot = self.handeye_transform[:3, :3]
                
            return camera_pos_mm, camera_rot
            
        except Exception as e:
            print(f"failed to calculate camera pose: {str(e)}")
            return None, None
    
    def project_to_plane(self, target_position, target_orientation, pixel_x=None, pixel_y=None, image_size=None):
        """project pixel coordinates to world coordinate system plane at specified Z depth
        
        Args:
            target_position: robot end position [x, y, z] (meters)
            target_orientation: robot end pose [roll, pitch, yaw] (Euler angles, radians)
            pixel_x: pixel X coordinate, if None use image center
            pixel_y: pixel Y coordinate, if None use image center
            image_size: image size (width, height), if None use default value
        
        Returns:
            tuple: (success, world_x_mm, world_y_mm, world_z_mm) 
                   success flag and world coordinate system coordinates (mm), returns (False, None, None, None) on failure
        """
        if self.handeye_transform is None:
            return False, None, None, None
            
        try:
            # calculate camera position and orientation
            camera_pos_mm, camera_rot = self.calculate_camera_pose(target_position, target_orientation)
            
            if camera_pos_mm is None or camera_rot is None:
                return False, None, None, None
            
            # if no pixel coordinates specified, use image center
            if pixel_x is None or pixel_y is None:
                if image_size is not None:
                    # use provided image size
                    pixel_x = image_size[0] / 2  # image width center
                    pixel_y = image_size[1] / 2  # image height center
                else:
                    # use default image center
                    pixel_x = 320  # default 640x480 image center
                    pixel_y = 240
            
            # if camera intrinsics available, use precise pixel projection
            if self.camera_matrix is not None and self.dist_coeffs is not None:
                # convert pixel coordinates to normalized camera coordinates
                # consider distortion correction
                pixel_points = np.array([[pixel_x, pixel_y]], dtype=np.float32)
                undistorted_points = cv2.undistortPoints(
                    pixel_points, self.camera_matrix, self.dist_coeffs
                ).reshape(-1, 2)
                
                # normalized coordinates (camera coordinate system, point on Z=1 plane)
                norm_x, norm_y = undistorted_points[0]
                
                # ray direction in camera coordinate system (normalized)
                ray_direction = np.array([norm_x, norm_y, 1.0])
                ray_direction = ray_direction / np.linalg.norm(ray_direction)
            else:
                # if no camera intrinsics, use optical axis direction (camera center point)
                center_x = image_size[0] / 2 if image_size is not None else 320
                center_y = image_size[1] / 2 if image_size is not None else 240
                
                if pixel_x != center_x or pixel_y != center_y:
                    # if not center point but no intrinsics, cannot calculate
                    return False, None, None, None
                
                # camera optical axis direction (Z-axis direction, pointing forward)
                ray_direction = np.array([0, 0, 1])
            
            # convert ray direction from camera coordinate system to world coordinate system
            world_ray_direction = camera_rot @ ray_direction
            
            # calculate intersection of ray with specified Z plane
            # ray equation: P = camera_pos_mm + t * world_ray_direction
            # plane equation: z = self.z_height_mm
            # solve: camera_pos_mm[2] + t * world_ray_direction[2] = self.z_height_mm
            
            if abs(world_ray_direction[2]) < 1e-6:
                # ray almost parallel to Z plane, cannot calculate intersection
                return False, None, None, None
            
            # calculate parameter t
            t = (self.z_height_mm - camera_pos_mm[2]) / world_ray_direction[2]
            
            # calculate intersection coordinates
            intersection_point = camera_pos_mm + t * world_ray_direction
            
            # apply X and Y offsets (if non-zero)
            final_x = intersection_point[0] + self.x_offset_mm
            final_y = intersection_point[1] + self.y_offset_mm
            final_z = intersection_point[2]  # Z coordinate remains unchanged, already on specified plane
            
            return True, final_x, final_y, final_z
            
        except Exception as e:
            print(f"failed to project to plane: {str(e)}")
            return False, None, None, None
    
    def set_localisation_offsets(self, x_offset_mm=0.0, y_offset_mm=0.0, z_height_mm=0.0):
        """set 2D localization offset amounts
        
        Args:
            x_offset_mm: X-axis offset (mm)
            y_offset_mm: Y-axis offset (mm)
            z_height_mm: Z-axis height (mm)
        """
        self.x_offset_mm = float(x_offset_mm)
        self.y_offset_mm = float(y_offset_mm)
        self.z_height_mm = float(z_height_mm)
    
    def get_localisation_offsets(self):
        """get current 2D localization offset amounts
        
        Returns:
            tuple: (x_offset_mm, y_offset_mm, z_height_mm)
        """
        return self.x_offset_mm, self.y_offset_mm, self.z_height_mm

    def reset_calibration(self):
        """reset all calibration data (intrinsic and hand-eye calibration)"""
        # reset intrinsic calibration data
        self.calibration_corners_all = []
        self.calibration_ids_all = []
        self.calibration_img_size = None
        self.calibration_frames = []
        self.camera_matrix = None
        self.dist_coeffs = None
        self.rvecs = []
        self.tvecs = []
        
        # reset hand-eye calibration data
        self.robot_rotations = []
        self.robot_translations = []
        self.handeye_transform = None

    def release_all(self):
        """release all camera resources"""
        self.is_running = False
        for camera in self.cameras:
            camera.release()
        self.cameras = []
        self.active_cameras = []
        self.view_mode = 'none'

    def _calculate_reprojection_error(self):
        """calculate reprojection error of camera calibration
        
        Returns:
            float: average reprojection error, returns 0 if cannot calculate
        """
        total_error = 0
        total_points = 0
        
        for i in range(len(self.calibration_corners_all)):
            charuco_corners = self.calibration_corners_all[i]
            charuco_ids = self.calibration_ids_all[i]
            
            # recalculate projection points
            image_points, _ = cv2.projectPoints(
                self.calibration_board.getChessboardCorners(), 
                self.rvecs[i], self.tvecs[i], 
                self.camera_matrix, self.dist_coeffs
            )
            
            # get corresponding actual detected points
            detected_points = []
            projected_points = []
            
            for j in range(len(charuco_ids)):
                point_id = charuco_ids[j][0]
                if 0 <= point_id < len(image_points):
                    detected_points.append(charuco_corners[j])
                    projected_points.append(image_points[point_id])
                    
            # calculate root mean square error
            if detected_points and projected_points:
                detected_points = np.array(detected_points).reshape(-1, 2)
                projected_points = np.array(projected_points).reshape(-1, 2)
                
                error = cv2.norm(detected_points, projected_points, cv2.NORM_L2) / len(detected_points)
                total_error += error
                total_points += 1
        
        # calculate average error
        return total_error / total_points if total_points > 0 else 0