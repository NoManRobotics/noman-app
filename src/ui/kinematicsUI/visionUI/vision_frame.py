import os
import cv2
import numpy as np
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk
from tkinter import messagebox, filedialog, colorchooser
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from camera.camera_controller import CameraController
from noman.detection import DetectionManager
from utils.config import Config
from utils.range_slider import RangeSlider
from utils.resource_loader import ResourceLoader
from utils.color_utils import rgb_to_hsv, hsv_to_rgb
from utils.tooltip import ToolTip
from ui.kinematicsUI.visionUI.camera_setup import CameraSetup
from ui.kinematicsUI.visionUI.color_capture_dialog import ColorCaptureDialog
from ui.kinematicsUI.visionUI.camera_3d_visualizer import Camera3DVisualizer
from ui.kinematicsUI.visionUI.blockly_editor import BlocklyEditor

class VisionFrame:
    def __init__(self, kinematics_frame):
        self.kinematics_frame = kinematics_frame

        # initialise backend
        self.controller = CameraController()
        self.detection_manager = DetectionManager()
        self.detectors = self.detection_manager.get_available_detectors()
        self.detection_enabled = False
        
        self.current_frame = None
        self.current_frame_image = None
        self.camera_status_frames = []
        self.camera_setup = None # camera setup window

        # Calibration variables
        self.sample_count = 0  # 已采集样本数量
        self.calibration_result = None
        
        # Camera center cross display state
        self.show_camera_center_cross = False  # 用于跟踪相机中心十字标记的显示状态
        
        # Detection results storage
        self.detection_results = [[] for _ in range(self.controller.get_max_cameras())]
        
        self.load_icons()
    
    def load_icons(self):
        """加载图标资源"""
        # Load icon paths
        activate_path = ResourceLoader.get_asset_path(os.path.join("icons", "activate.png"))
        deactivate_path = ResourceLoader.get_asset_path(os.path.join("icons", "deactivate.png"))
        bin_path = ResourceLoader.get_asset_path(os.path.join("icons", "bin.png"))
        plus_path = ResourceLoader.get_asset_path(os.path.join("icons", "plus.png"))
        downarrow_path = ResourceLoader.get_asset_path(os.path.join("icons", "downarrow.png"))
        perspective_path = ResourceLoader.get_asset_path(os.path.join("icons", "perspective_rectangles.png"))
        reset_path = ResourceLoader.get_asset_path(os.path.join("icons", "reset.png"))
        question_path = ResourceLoader.get_asset_path(os.path.join("icons", "question.png"))
        
        self.activate_icon = ctk.CTkImage(Image.open(activate_path).convert("RGBA"), size=(20, 20))
        self.deactivate_icon = ctk.CTkImage(Image.open(deactivate_path).convert("RGBA"), size=(20, 20))
        self.bin_icon = ctk.CTkImage(Image.open(bin_path).convert("RGBA"), size=(20, 20))
        self.plus_icon = ctk.CTkImage(Image.open(plus_path).convert("RGBA"), size=(15, 15))
        self.downarrow_icon = ctk.CTkImage(Image.open(downarrow_path).convert("RGBA"), size=(15, 15))
        self.perspective_image = ctk.CTkImage(Image.open(perspective_path).convert("RGBA"), size=(135, 135))
        self.reset_icon = ctk.CTkImage(Image.open(reset_path).convert("RGBA"), size=(20, 20))
        self.question_icon = ctk.CTkImage(Image.open(question_path).convert("RGBA"), size=(18, 18))
    
    def create_window(self):
        """创建相机控制器窗口"""
        self.dialog = ctk.CTkToplevel()
        self.dialog.title("Vision Controller")
        
        # set up window location
        dialog_x = self.kinematics_frame.winfo_rootx() + self.kinematics_frame.winfo_width() + 10
        dialog_y = self.kinematics_frame.winfo_rooty() - 30
        
        self.dialog.geometry(f"900x925+{dialog_x}+{dialog_y}")
        self.dialog.grid_rowconfigure(0, weight=1)
        self.dialog.grid_columnconfigure(0, weight=1)

        self.main_frame = ctk.CTkFrame(self.dialog, fg_color="transparent")
        self.main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        # view frame
        self.view_frame = ctk.CTkFrame(self.main_frame,fg_color="transparent")
        self.view_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=5)
        self.view_frame.grid_rowconfigure(0, weight=1)
        self.view_frame.grid_columnconfigure(0, weight=1)

        self.preview_container = ctk.CTkFrame(self.view_frame, bg_color="transparent")
        self.preview_container.grid(row=0, column=0, sticky="nsew")
        self.preview_container.grid_propagate(False)
        
        # preview label
        self.preview_label = ctk.CTkLabel(self.preview_container, bg_color='black', text="", height=300)
        self.preview_label.grid(row=0, column=0, sticky="nsew")
        self.preview_container.grid_rowconfigure(0, weight=1)
        self.preview_container.grid_columnconfigure(0, weight=1)
        
        # camera setup area
        self.utiliy_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.utiliy_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=5)

        self.setup_control_frame()
        self.setup_camera_status_frame()

        self.main_frame.grid_rowconfigure(0, weight=15)
        self.main_frame.grid_rowconfigure(1, weight=4)
        self.main_frame.grid_columnconfigure(0, weight=1)

        self.utiliy_frame.grid_columnconfigure(0, weight=3)
        self.utiliy_frame.grid_columnconfigure(1, weight=1)
        self.utiliy_frame.grid_rowconfigure(0, weight=1)

        # set up controller callbacks
        self.controller.set_callbacks(
            on_camera_status_changed=self.on_camera_status_changed,
            on_frame_update=self.on_frame_update
        )

        # clean up when window is closed
        self.dialog.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 初始化相机设置类
        self.camera_setup = CameraSetup(self.dialog, self.controller)

    def setup_control_frame(self):
        self.control_frame = ctk.CTkFrame(self.utiliy_frame)
        self.control_frame.grid(row=0, column=0, padx=10, pady=5, sticky="nsew")

        self.control_frame.grid_rowconfigure(0, weight=1)
        self.control_frame.grid_rowconfigure(1, weight=4)
        self.control_frame.grid_columnconfigure(0, weight=1)
        
        self.tab_frame = ctk.CTkFrame(self.control_frame, fg_color="#DBDBDB")
        self.tab_frame.grid(row=0, column=0, padx=10, pady=5, sticky="nsew")
        self.tab_frame.grid_columnconfigure(0, weight=1, uniform="col")
        self.tab_frame.grid_columnconfigure(1, weight=1, uniform="col")
        self.tab_frame.grid_rowconfigure(0, weight=1)

        self.calibration_tab_frame = ctk.CTkFrame(self.tab_frame, fg_color="#DBDBDB")
        self.calibration_tab_frame.grid(row=0, column=0, sticky="ew")
        self.calibration_tab_frame.grid_columnconfigure(0, weight=1)

        self.detection_tab_frame = ctk.CTkFrame(self.tab_frame, fg_color="#DBDBDB")
        self.detection_tab_frame.grid(row=0, column=1, sticky="ew")
        self.detection_tab_frame.grid_columnconfigure(0, weight=1)

        self.calibration_button = ctk.CTkButton(self.calibration_tab_frame, text=Config.current_lang["calibration"], text_color="black", fg_color="#DBDBDB", hover_color="#DBDBDB", command=self.show_calibration_content)
        self.calibration_button.grid(row=0, column=0, sticky="ew")

        self.calibration_underline = ctk.CTkFrame(self.calibration_tab_frame, height=2, fg_color="black")
        self.calibration_underline.grid(row=1, column=0, padx=15, sticky="ew")

        self.detection_button = ctk.CTkButton(self.detection_tab_frame, text=Config.current_lang["detection"], text_color="black", fg_color="#DBDBDB", hover_color="#DBDBDB", command=self.show_detection_content)
        self.detection_button.grid(row=0, column=0, sticky="ew")

        self.detection_underline = ctk.CTkFrame(self.detection_tab_frame, height=2, fg_color="black")
        self.detection_underline.grid(row=1, column=0, padx=15, sticky="ew")
        self.detection_underline.grid_remove()
        
        # content frame
        self.content_frame = ctk.CTkFrame(self.control_frame, fg_color="transparent")
        self.content_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)

        self.setup_calibration_content()
        self.setup_detection_frame()
        self.show_calibration_content()

    def setup_camera_status_frame(self):
        self.camera_status_frame = ctk.CTkFrame(self.utiliy_frame)
        self.camera_status_frame.grid(row=0, column=1, padx=10, pady=5, sticky="nsew")
        self.camera_status_frame.grid_columnconfigure(0, weight=1)
        
        self.add_camera_button = ctk.CTkButton(self.camera_status_frame, text=Config.current_lang["add_camera"], image=self.plus_icon, text_color="black", fg_color="#DBDBDB", hover_color="#DBDBDB", command=self.open_camera_setup)
        self.add_camera_button.grid(row=0, column=0, padx=10, pady=(5,0), sticky="ew")

        self.camera_underline = ctk.CTkFrame(self.camera_status_frame, height=2, fg_color="black")
        self.camera_underline.grid(row=1, column=0, padx=15, pady=(0,5), sticky="ew")

    def setup_calibration_content(self):
        """设置标定内容框架，使用按钮进行导航而不是TabView"""
        self.calibration_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.calibration_frame.grid_columnconfigure(0, weight=1)
        self.calibration_frame.grid_rowconfigure(0, weight=1) 
        self.calibration_frame.grid_rowconfigure(1, weight=0)
        
        self.calibration_content_frame = ctk.CTkFrame(self.calibration_frame, fg_color="transparent", height=290)
        self.calibration_content_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        self.calibration_content_frame.pack_propagate(False)

        self.calibration_nav_frame = ctk.CTkFrame(self.calibration_frame, fg_color="#DBDBDB")
        self.calibration_nav_frame.grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        
        self.calibration_nav_frame.grid_columnconfigure(0, weight=1)
        self.calibration_nav_frame.grid_columnconfigure(1, weight=1)
        self.calibration_nav_frame.grid_columnconfigure(2, weight=1)
        
        # Navigation buttons
        self.charuco_button = ctk.CTkButton(self.calibration_nav_frame, text=Config.current_lang["calibration_board"], text_color="black", fg_color="#DBDBDB", hover_color="#DBDBDB", command=lambda: self.show_calibration_page("charuco"))
        self.charuco_button.grid(row=0, column=0, sticky="ew")
        
        self.pose_button = ctk.CTkButton(self.calibration_nav_frame, text=Config.current_lang["pose_sampling"], text_color="black", fg_color="#DBDBDB", hover_color="#DBDBDB", command=lambda: self.show_calibration_page("pose"))
        self.pose_button.grid(row=0, column=1, sticky="ew")
        
        self.result_button = ctk.CTkButton(self.calibration_nav_frame, text=Config.current_lang["result"], text_color="black", fg_color="#DBDBDB", hover_color="#DBDBDB", command=lambda: self.show_calibration_page("result"))
        self.result_button.grid(row=0, column=2, sticky="ew")
        
        # setup pages of calibration
        self.create_charuco_page()
        self.create_pose_page()
        self.create_result_page()
        
        # page dictionary, for managing page switching
        self.calibration_pages = {
            "charuco": self.charuco_frame,
            "pose": self.hand_eye_frame,
            "result": self.result_frame
        }
        
        # hide all pages
        for page in self.calibration_pages.values():
            page.grid_forget()
        
        # show the first page
        self.show_calibration_page("charuco")

    def setup_detection_frame(self):
        """初始化检测框架"""
        self.detection_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.detection_frame.grid_columnconfigure(0, weight=1)
        self.detection_frame.grid_rowconfigure(0, weight=1)
        self.detection_frame.grid_rowconfigure(1, weight=0)
        
        self.detection_content_frame = ctk.CTkFrame(self.detection_frame, fg_color="transparent", height=290)
        self.detection_content_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        self.detection_content_frame.pack_propagate(False)

        self.detection_nav_frame = ctk.CTkFrame(self.detection_frame, fg_color="#DBDBDB")
        self.detection_nav_frame.grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        
        self.detection_nav_frame.grid_columnconfigure(0, weight=1)
        self.detection_nav_frame.grid_columnconfigure(1, weight=1)
        self.detection_nav_frame.grid_columnconfigure(2, weight=1)
        
        # Navigation buttons
        self.localisation_button = ctk.CTkButton(self.detection_nav_frame, text=Config.current_lang["localisation"], text_color="black", fg_color="#DBDBDB", hover_color="#DBDBDB", command=lambda: self.show_detection_page("localisation"))
        self.localisation_button.grid(row=0, column=0, sticky="ew")

        self.detector_options_button = ctk.CTkButton(self.detection_nav_frame, text=Config.current_lang["detector"], text_color="black", fg_color="#DBDBDB", hover_color="#DBDBDB", command=lambda: self.show_detection_page("options"))
        self.detector_options_button.grid(row=0, column=1, sticky="ew")
        
        self.interaction_button = ctk.CTkButton(self.detection_nav_frame, text=Config.current_lang["interaction"], text_color="black", fg_color="#DBDBDB", hover_color="#DBDBDB", command=lambda: self.show_detection_page("interaction"))
        self.interaction_button.grid(row=0, column=2, sticky="ew")
        
        # create detection pages
        self.create_detector_options_page()
        self.create_localisation_page()
        self.create_interaction_page()
        
        # page dictionary, for managing page switching
        self.detection_pages = {
            "options": self.detector_options_frame,
            "localisation": self.localisation_frame,
            "interaction": self.interaction_frame
        }
        
        # hide all pages
        for page in self.detection_pages.values():
            page.grid_forget()
        
        # show the first page
        self.show_detection_page("localisation")

    def show_calibration_content(self):
        """显示标定内容"""
        # 先准备好新内容
        self.calibration_frame.grid(row=0, column=0, sticky="nsew")
        self.calibration_underline.grid()

        # 配置网格权重
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.calibration_frame.grid_columnconfigure(0, weight=1)
        self.calibration_frame.grid_rowconfigure(0, weight=1)
        self.calibration_frame.grid_rowconfigure(1, weight=0)
        
        # 高亮标定按钮
        self.calibration_button.configure(text_color="#41d054", fg_color="#DBDBDB")
        self.detection_button.configure(text_color="black", fg_color="#DBDBDB")
        
        # 最后才移除旧内容
        self.detection_frame.grid_forget()
        self.detection_underline.grid_remove()
        
        # 强制更新UI
        self.calibration_frame.update_idletasks()

    def show_calibration_page(self, page_name):
        """显示指定的标定页面并隐藏其他页面"""
        # 隐藏所有页面
        for page in self.calibration_pages.values():
            page.pack_forget()
            
        # 显示选中的页面
        self.calibration_pages[page_name].pack(fill="both", expand=True)
        
        for btn, page_type in [(self.charuco_button, "charuco"),
                               (self.pose_button, "pose"),
                               (self.result_button, "result")]:
            if page_type == page_name:
                btn.configure(text_color="#41d054", fg_color="#D0D0D0")
            else:
                btn.configure(text_color="black", fg_color="#DBDBDB")

    def show_detection_content(self):
        """显示检测内容"""
        # 先准备好新内容
        self.detection_frame.grid(row=0, column=0, sticky="nsew")
        self.detection_underline.grid()
        
        # 配置网格权重
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.detection_frame.grid_rowconfigure(0, weight=1)
        self.detection_frame.grid_columnconfigure(0, weight=1)
        
        # 高亮检测按钮
        self.calibration_button.configure(text_color="black", fg_color="#DBDBDB")
        self.detection_button.configure(text_color="#41d054", fg_color="#DBDBDB")
        
        # 最后才移除旧内容
        self.calibration_frame.grid_forget()
        self.calibration_underline.grid_remove()
        
        # 强制更新UI
        self.detection_frame.update_idletasks()

    def show_detection_page(self, page_name):
        """显示指定的检测页面并隐藏其他页面"""
        # 隐藏所有页面
        for page in self.detection_pages.values():
            page.pack_forget()
            
        # 显示选中的页面
        self.detection_pages[page_name].pack(fill="both", expand=True)
        
        # 更新按钮样式
        for btn, page_type in [(self.detector_options_button, "options"), 
                               (self.localisation_button, "localisation"),
                               (self.interaction_button, "interaction")]:
            if page_type == page_name:
                btn.configure(text_color="#41d054", fg_color="#D0D0D0")
            else:
                btn.configure(text_color="black", fg_color="#DBDBDB")

    def create_charuco_page(self):
        """创建Charuco标定板页面"""
        self.charuco_frame = ctk.CTkFrame(self.calibration_content_frame, fg_color="transparent")
        self.charuco_frame.pack(fill="x", expand=True)

        self.charuco_left_frame = ctk.CTkFrame(self.charuco_frame, fg_color="transparent")
        self.charuco_left_frame.pack(side="left", fill="both", expand=True, padx=(0,10))
        self.charuco_right_frame = ctk.CTkFrame(self.charuco_frame)
        self.charuco_right_frame.pack(side="right", fill="y")
        
        self.charuco_image_label = tk.Label(self.charuco_left_frame, bg='white', text="")
        self.charuco_image_label.pack(fill="both", expand=True)
        
        self.charuco_title = ctk.CTkLabel(self.charuco_right_frame, text="标定板参数")
        self.charuco_title.pack(pady=5, padx=5, anchor="w", fill="x")
        
        charuco_rows_frame = ctk.CTkFrame(self.charuco_right_frame, fg_color="transparent")
        charuco_rows_frame.pack(fill="x", pady=2, anchor="n")
        self.board_rows_label = ctk.CTkLabel(charuco_rows_frame, text="行数:")
        self.board_rows_label.pack(side="left", padx=5)
        self.board_rows_entry = ctk.CTkEntry(charuco_rows_frame, width=50)
        self.board_rows_entry.insert(0, "5")
        self.board_rows_entry.pack(side="left", padx=(30,5))
        
        # Charuco标定板列数
        charuco_cols_frame = ctk.CTkFrame(self.charuco_right_frame, fg_color="transparent")
        charuco_cols_frame.pack(fill="x", pady=2, anchor="n")
        self.board_cols_label = ctk.CTkLabel(charuco_cols_frame, text="列数:")
        self.board_cols_label.pack(side="left", padx=5)
        self.board_cols_entry = ctk.CTkEntry(charuco_cols_frame, width=50)
        self.board_cols_entry.insert(0, "7")
        self.board_cols_entry.pack(side="left", padx=(30,5))
        
        # 正方形大小(mm)
        square_size_frame = ctk.CTkFrame(self.charuco_right_frame, fg_color="transparent")
        square_size_frame.pack(fill="x", pady=2, anchor="n")
        self.square_size_label = ctk.CTkLabel(square_size_frame, text="方格大小:")
        self.square_size_label.pack(side="left", padx=5)
        self.square_size_entry = ctk.CTkEntry(square_size_frame, width=50)
        self.square_size_entry.insert(0, "20")
        self.square_size_entry.pack(side="left", padx=5)
        
        # ArUco标记大小相对于方格的比例
        marker_size_frame = ctk.CTkFrame(self.charuco_right_frame, fg_color="transparent")
        marker_size_frame.pack(fill="x", pady=2, anchor="n")
        self.marker_size_label = ctk.CTkLabel(marker_size_frame, text="标记比例:")
        self.marker_size_label.pack(side="left", padx=5)
        self.marker_size_entry = ctk.CTkEntry(marker_size_frame, width=50)
        self.marker_size_entry.insert(0, "0.6")
        self.marker_size_entry.pack(side="left", padx=5)
        
        # ArUco字典选择
        dictionary_frame = ctk.CTkFrame(self.charuco_right_frame, fg_color="transparent")
        dictionary_frame.pack(fill="x", pady=2)
        self.dictionary_label = ctk.CTkLabel(dictionary_frame, text="字典:")
        self.dictionary_label.pack(side="left", padx=(5,15))
        
        self.dictionary_var = tk.StringVar(value="DICT_4X4_50")
        self.dictionary_menu = ctk.CTkOptionMenu(
            dictionary_frame,
            variable=self.dictionary_var,
            width=80,
            values=["DICT_4X4_50", "DICT_5X5_50", "DICT_6X6_50", "DICT_7X7_50"]
        )
        self.dictionary_menu.pack(side="left", padx=(5,0))
        
        # 按钮框架 - 集中放置两个按钮
        self.charuco_buttons_frame = ctk.CTkFrame(self.charuco_right_frame, fg_color="transparent")
        self.charuco_buttons_frame.pack(fill="x", pady=(15,0), anchor="n")
        
        # 生成标定板按钮
        self.generate_board_button = ctk.CTkButton(self.charuco_buttons_frame, text="生成标定板", command=self.generate_charuco_board, width=80)
        self.generate_board_button.pack(pady=5, fill="x", padx=(10,20))
        
        # create save button and checkbox frame
        self.save_frame = ctk.CTkFrame(self.charuco_buttons_frame, fg_color="transparent")
        self.save_frame.pack(fill="x", padx=10, pady=5)
        self.save_frame.grid_columnconfigure(0, weight=0)
        self.save_frame.grid_columnconfigure(1, weight=1)
        
        # save calibration board button
        self.save_board_button = ctk.CTkButton(self.save_frame,text=Config.current_lang["save"],command=self.save_charuco_board,width=60)
        self.save_board_button.grid(row=0, column=0, padx=(0,5), pady=0, sticky="w")
        
        # PDF格式选择复选框
        self.use_pdf_var = tk.BooleanVar(value=True)
        self.use_pdf_checkbox = ctk.CTkCheckBox(self.save_frame, text="PDF(推荐)", variable=self.use_pdf_var, onvalue=True, offvalue=False)
        self.use_pdf_checkbox.grid(row=0, column=1, padx=(5,0), pady=0, sticky="w")
    
    def create_pose_page(self):
        """创建位姿采样页面"""
        self.hand_eye_frame = ctk.CTkFrame(self.calibration_content_frame, fg_color="transparent")
        self.hand_eye_frame.pack(fill="both", expand=True)
        
        # 创建上下两个主框架
        top_frame = ctk.CTkFrame(self.hand_eye_frame, fg_color="transparent")
        top_frame.pack(fill="x", expand=True)
        top_frame.grid_columnconfigure(0, weight=1, uniform='col')
        top_frame.grid_columnconfigure(1, weight=1, uniform='col')
        
        bottom_frame = ctk.CTkFrame(self.hand_eye_frame, fg_color="transparent")
        bottom_frame.pack(fill="x", expand=True, pady=(10, 0))
        bottom_frame.grid_columnconfigure(0, weight=1, uniform='col')
        bottom_frame.grid_columnconfigure(1, weight=1, uniform='col')
        
        # 创建四个区域框架
        top_left_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        top_left_frame.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="nsew")
        
        top_right_frame = ctk.CTkFrame(top_frame)
        top_right_frame.grid(row=0, column=1, padx=(5, 0), pady=5, sticky="nsew")
        
        bottom_left_frame = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        bottom_left_frame.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="nsew")
        
        bottom_right_frame = ctk.CTkFrame(bottom_frame)
        bottom_right_frame.grid(row=0, column=1, padx=(5, 0), pady=5, sticky="nsew")
        
        # ===== 顶部左侧：标定类型选择、采样控制 =====
        self.cal_type_frame = ctk.CTkFrame(top_left_frame, fg_color="transparent")
        self.cal_type_frame.pack(fill="x", padx=5, pady=5)
        
        self.calibration_type_var = tk.StringVar(value="eye_in_hand")
        
        self.eye_in_hand_radio = ctk.CTkRadioButton(self.cal_type_frame, text="Eye-in-Hand", 
                                                   variable=self.calibration_type_var, 
                                                   value="eye_in_hand", 
                                                   command=self.change_handeye_mode)
        self.eye_in_hand_radio.pack(side="left", padx=(5, 10), pady=2)
        
        self.eye_to_hand_radio = ctk.CTkRadioButton(self.cal_type_frame, text="Eye-to-Hand", 
                                                   variable=self.calibration_type_var, 
                                                   value="eye_to_hand", 
                                                   command=self.change_handeye_mode)
        self.eye_to_hand_radio.pack(side="left", padx=5, pady=2)
        
        # 数据采集标题和工具提示
        data_collection_title_frame = ctk.CTkFrame(top_left_frame, fg_color="transparent")
        data_collection_title_frame.pack(fill="x", padx=5, pady=(10, 5))
        
        data_collection_title = ctk.CTkLabel(data_collection_title_frame, text="数据采集")
        data_collection_title.pack(side="left", padx=5)
        
        self.data_collection_question_button = ctk.CTkButton(
            data_collection_title_frame,
            text="",
            image=self.question_icon,
            width=20,
            height=20,
            fg_color="transparent",
            hover_color="#B3B3B3"
        )
        self.data_collection_question_button.pack(side="left", padx=5)
        
        # 添加工具提示
        ToolTip(self.data_collection_question_button, "Auto calibration needs pre-defined poses that can be generated from task board.\nMannual calibration needs user to send robot poses in kinematics each time.")
        
        # 文件路径输入框和浏览按钮
        file_path_frame = ctk.CTkFrame(top_left_frame, fg_color="transparent")
        file_path_frame.pack(fill="x", padx=5, pady=2)
        
        self.file_path_entry = ctk.CTkEntry(
            file_path_frame, 
            placeholder_text="选择标定数据文件路径",
            width=200,
            state="disabled"  # 默认禁用，因为auto calibrate默认未选中
        )
        self.file_path_entry.pack(side="left", padx=(0,5), fill="x", expand=True)
        
        self.browse_button = ctk.CTkButton(
            file_path_frame,
            text="浏览",
            command=self.browse_calibration_file,
            width=60,
            state="disabled"  # 默认禁用，因为auto calibrate默认未选中
        )
        self.browse_button.pack(side="right", padx=5)
        
        # 标定控制区域
        control_frame = ctk.CTkFrame(top_left_frame, fg_color="transparent")
        control_frame.pack(fill="x", padx=5, pady=5)
        
        # 采集按钮
        self.capture_button = ctk.CTkButton(control_frame,text="采集位姿",command=self.capture_current_pose,width=120)
        self.capture_button.pack(side="left", padx=(0, 10))
        
        # 自动标定选项 - 放在采集按钮右侧
        self.auto_calibrate_var = tk.BooleanVar(value=False)
        self.auto_calibrate_checkbox = ctk.CTkCheckBox(
            control_frame, 
            text="Auto Calibrate", 
            variable=self.auto_calibrate_var,
            command=self.on_auto_calibrate_changed
        )
        self.auto_calibrate_checkbox.pack(side="left", padx=5)

        
        # ===== 顶部右侧：标定板预览 =====
        # 标定板预览区域
        preview_frame = ctk.CTkFrame(top_right_frame, height=150, fg_color="transparent")
        preview_frame.pack(fill="both", padx=(0,5),expand=True)
        preview_frame.pack_propagate(False)
        
        # 标定板预览标签
        self.pose_preview_label = ctk.CTkLabel(preview_frame, bg_color='black', text="", text_color="white", image=self.perspective_image)
        self.pose_preview_label.pack(fill="both", expand=True)
        
        # ===== 底部左侧：计算手眼变换控制 =====
        # 状态信息
        self.hand_eye_status_label = ctk.CTkLabel(bottom_left_frame, text="状态: 未标定")
        self.hand_eye_status_label.pack(anchor="w", padx=5, pady=5)
        
        # 添加样本计数滑块
        slider_frame = ctk.CTkFrame(bottom_left_frame, fg_color="transparent")
        slider_frame.pack(fill="x", padx=5, pady=5)
        
        self.pose_sample_count = ctk.CTkSlider(slider_frame, from_=0, to=9, number_of_steps=9)
        self.pose_sample_count.pack(side="left")
        self.pose_sample_count.set(0)
        self.pose_sample_count.configure(state="disabled")
        
        # 显示样本数量
        self.sample_count_label = ctk.CTkLabel(slider_frame, text="0/9")
        self.sample_count_label.pack(side="left", padx=5)
        
        # 计算手眼变换按钮
        button_frame = ctk.CTkFrame(bottom_left_frame, fg_color="transparent")
        button_frame.pack(fill="x", padx=5, pady=(10, 5))
        
        self.calibrate_button = ctk.CTkButton(button_frame, text="计算手眼变换",
            command=self.calculate_hand_eye_transform,
            width=120,
            state="disabled"
        )
        self.calibrate_button.pack(side="left", padx=(0, 10))
        
        # 添加重置按钮
        self.reset_pose_button = ctk.CTkButton(
            button_frame,
            text="",
            image=self.reset_icon,
            command=self.reset_hand_eye_calibration,
            width=30,
            fg_color="transparent", 
            hover_color="#41d054"
        )
        self.reset_pose_button.pack(side="left", padx=5)
        
        self.question_button = ctk.CTkButton(
            button_frame,
            text="",
            image=self.question_icon,
            width=20,
            height=20,
            fg_color="transparent",
            hover_color="#B3B3B3"
        )
        self.question_button.pack(side="left")
        
        # 添加工具提示
        ToolTip(self.question_button, Config.current_lang["tooltip_hand_eye_calibration"])
        
        # ===== 底部右侧：偏移量设置 =====
        # # 标定板偏移信息框架
        offset_title = ctk.CTkLabel(bottom_right_frame, text="标定板到TCP偏移:")
        offset_title.pack(anchor="w", pady=(5, 5), padx=5)
        
        # 位置偏移输入框架
        position_offset_frame = ctk.CTkFrame(bottom_right_frame, fg_color="transparent")
        position_offset_frame.pack(fill="x", pady=2, padx=5)
        
        # X偏移
        x_offset_label = ctk.CTkLabel(position_offset_frame, text="X:", width=20)
        x_offset_label.pack(side="left", padx=(0, 2))
        
        self.tcp_offset_x = ctk.CTkEntry(position_offset_frame, width=50)
        self.tcp_offset_x.pack(side="left", padx=(0, 5))
        self.tcp_offset_x.insert(0, "32.0")  # 默认值
        
        # Y偏移
        y_offset_label = ctk.CTkLabel(position_offset_frame, text="Y:", width=20)
        y_offset_label.pack(side="left", padx=(0, 2))
        
        self.tcp_offset_y = ctk.CTkEntry(position_offset_frame, width=50)
        self.tcp_offset_y.pack(side="left", padx=(0, 5))
        self.tcp_offset_y.insert(0, "0.0")  # 默认值
        
        # Z偏移
        z_offset_label = ctk.CTkLabel(position_offset_frame, text="Z:", width=20)
        z_offset_label.pack(side="left", padx=(0, 2))
        
        self.tcp_offset_z = ctk.CTkEntry(position_offset_frame, width=50)
        self.tcp_offset_z.pack(side="left", padx=(0, 5))
        self.tcp_offset_z.insert(0, "2.0")  # 默认值
        
        # 方向偏移输入框架
        orientation_offset_frame = ctk.CTkFrame(bottom_right_frame, fg_color="transparent")
        orientation_offset_frame.pack(fill="x", pady=2, padx=5)
        
        # R偏移
        rx_offset_label = ctk.CTkLabel(orientation_offset_frame, text="R:", width=20)
        rx_offset_label.pack(side="left", padx=(0, 2))
        
        self.tcp_offset_rx = ctk.CTkEntry(orientation_offset_frame, width=50)
        self.tcp_offset_rx.pack(side="left", padx=(0, 5))
        self.tcp_offset_rx.insert(0, "0.0")  # 默认值
        
        # P偏移
        ry_offset_label = ctk.CTkLabel(orientation_offset_frame, text="P:", width=20)
        ry_offset_label.pack(side="left", padx=(0, 2))
        
        self.tcp_offset_ry = ctk.CTkEntry(orientation_offset_frame, width=50)
        self.tcp_offset_ry.pack(side="left", padx=(0, 5))
        self.tcp_offset_ry.insert(0, "0.0")  # 默认值
        
        # Y偏移
        rz_offset_label = ctk.CTkLabel(orientation_offset_frame, text="Y:", width=20)
        rz_offset_label.pack(side="left", padx=(0, 2))
        
        self.tcp_offset_rz = ctk.CTkEntry(orientation_offset_frame, width=50)
        self.tcp_offset_rz.pack(side="left", padx=(0, 5))
        self.tcp_offset_rz.insert(0, "0.0")  # 默认值
        
        # 设置偏移按钮框架
        set_offset_frame = ctk.CTkFrame(bottom_right_frame, fg_color="transparent")
        set_offset_frame.pack(fill="x", pady=(10, 0), padx=5)
        
        self.set_offset_button = ctk.CTkButton(
            set_offset_frame,
            text="设置偏移",
            command=self.set_board_to_ee_offset,
            width=100
        )
        self.set_offset_button.pack(side="left", padx=(0, 10))
        
        # 显示当前偏移状态
        self.offset_status_label = ctk.CTkLabel(set_offset_frame, text="(未设置偏移)")
        self.offset_status_label.pack(side="left")

    def create_result_page(self):
        """创建标定结果页面"""
        self.result_frame = ctk.CTkFrame(self.calibration_content_frame)
        self.result_frame.pack(fill="both", expand=True)
        self.result_frame.grid_columnconfigure(0, weight=1, uniform="col")
        self.result_frame.grid_columnconfigure(1, weight=1, uniform="col")

        self.result_left_frame = ctk.CTkFrame(self.result_frame, fg_color="transparent")
        self.result_left_frame.pack(side="left", fill="both", expand=True, padx=(2, 0))
        
        self.result_right_frame = ctk.CTkFrame(self.result_frame, fg_color="transparent")
        self.result_right_frame.pack(side="right", fill="both", expand=True, padx=(0, 2))

        # 方法选择区域
        method_selection_frame = ctk.CTkFrame(self.result_left_frame, fg_color="transparent")
        method_selection_frame.pack(fill="x", padx=5, pady=5)
        
        method_label = ctk.CTkLabel(method_selection_frame, text="标定方法:")
        method_label.pack(side="left", padx=(0, 10))
        
        # 方法选择下拉菜单
        self.selected_method_var = tk.StringVar(value="HORAUD")
        self.method_selector = ctk.CTkOptionMenu(
            method_selection_frame,
            variable=self.selected_method_var,
            values=["HORAUD"],  # 初始值，会在标定完成后更新
            command=self._on_method_selection_changed,
            width=95
        )
        self.method_selector.pack(side="left", padx=(0, 10))
        
        # 设置为当前变换按钮
        self.set_transform_button = ctk.CTkButton(
            method_selection_frame,
            text="应用",
            command=self._set_selected_transform,
            state="disabled",
            width=80
        )
        self.set_transform_button.pack(side="right")
        
        self.result_text = ctk.CTkTextbox(self.result_left_frame)
        self.result_text.pack(fill="both", expand=True, padx=5, pady=5)
        self.result_text.insert("1.0", "标定结果将显示在这里...")
        self.result_text.configure(state="disabled")

        # 按钮区域
        button_frame = ctk.CTkFrame(self.result_left_frame, fg_color="transparent")
        button_frame.pack(fill="x", padx=5, pady=5)

        self.save_button = ctk.CTkButton(
            button_frame,
            text=Config.current_lang["save"],
            command=self.save_calibration_result,
            width=100
        )
        self.save_button.pack(side="left")
        
        self.load_button = ctk.CTkButton(
            button_frame,
            text=Config.current_lang["load"],
            command=self.load_calibration_result,
            width=100
        )
        self.load_button.pack(side="right")

        self.result_visual_frame = ctk.CTkFrame(self.result_right_frame, fg_color="transparent")
        self.result_visual_frame.pack(fill="both", expand=True)
        
        # 创建Matplotlib图形和3D轴
        self.fig = Figure(figsize=(4, 3), dpi=100, facecolor='#DBDBDB')
        self.ax_3d = self.fig.add_subplot(111, projection='3d')
        self.ax_3d.set_facecolor('#DBDBDB')
        
        # 在框架中嵌入Matplotlib画布
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.result_visual_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        
        # 初始化3D可视化器
        self.camera_3d_visualizer = Camera3DVisualizer(self.ax_3d, self.canvas)
        
        # 初始化3D视图
        self._init_3d_viewer()
    
    def _init_3d_viewer(self):
        """准备数据并初始化3D视图"""
        try:
            # 获取基座位置和方向
            rad_angles = np.radians(self.kinematics_frame.joint_angles)
            base_pos, base_orn, _ = self.kinematics_frame.planner.getPoseGlobal(rad_angles, 0)
            
            # 获取工作空间边界
            workspace_bounds = None
            if self.kinematics_frame.workspace.get('analyzed', False):
                workspace_bounds = self.kinematics_frame.workspace['bounds']
            
            # 调用可视化器的初始化方法
            self.camera_3d_visualizer.init_3d_viewer(
                base_pos=base_pos,
                base_orn=base_orn,
                workspace_bounds=workspace_bounds
            )
            
        except Exception as e:
            self.show_error(f"初始化3D视图失败: {str(e)}")
    
    def _visualize_camera_3d(self):
        """准备数据并调用3D相机可视化器"""
            
        try:
            # 获取当前机器人位置和姿态
            target_position = self.kinematics_frame.target_position
            target_orientation = np.radians(self.kinematics_frame.target_orientation)
            
            # 计算相机位姿
            camera_pos_mm, camera_rot = self.controller.calculate_camera_pose(
                target_position*1000, target_orientation
            )
            
            # 获取机器人基座位置和姿态
            rad_angles = np.radians(self.kinematics_frame.joint_angles)
            base_pos, base_orn, _ = self.kinematics_frame.planner.getPoseGlobal(rad_angles, 0)
            
            # 获取工作空间边界
            workspace_bounds = None
            if self.kinematics_frame.workspace.get('analyzed', False):
                workspace_bounds = self.kinematics_frame.workspace['bounds']
            
            # 调用可视化器
            self.camera_3d_visualizer.visualize_camera_in_3d(
                camera_pos=camera_pos_mm/1000,
                camera_rot=camera_rot,
                target_position=target_position,
                base_pos=base_pos,
                base_orn=base_orn,
                workspace_bounds=workspace_bounds,
                show_error_callback=self.show_error
            )
            
        except Exception as e:
            self.show_error(f"准备3D可视化数据失败: {str(e)}")

    def create_localisation_page(self):
        """创建定位页面"""
        self.localisation_frame = ctk.CTkFrame(self.detection_content_frame)
        self.localisation_frame.pack(fill="both", expand=True)
        
        # 顶部相机选择区域
        self.camera_selection_frame = ctk.CTkFrame(self.localisation_frame, fg_color="transparent")
        self.camera_selection_frame.pack(fill="x", padx=0, pady=5)
        
        # 相机选择标签和下拉菜单
        camera_label = ctk.CTkLabel(self.camera_selection_frame, text="选择相机:")
        camera_label.pack(side="left", padx=(5, 10))
        
        # 初始化相机选择变量
        self.selected_localisation_camera_var = tk.StringVar(value="无可用相机")
        
        # 相机选择下拉菜单
        self.localisation_camera_selector = ctk.CTkOptionMenu(
            self.camera_selection_frame,
            values=["无可用相机"],
            variable=self.selected_localisation_camera_var,
            command=self.on_localisation_camera_changed,
            width=150
        )
        self.localisation_camera_selector.pack(side="left", padx=0)
        
        # 内容区域 - 用于显示不同类型相机的配置
        self.localisation_content_frame = ctk.CTkFrame(self.localisation_frame)
        self.localisation_content_frame.pack(fill="both", expand=True, padx=5, pady=10)
        
        self.create_2d_camera_content()
        self.create_3d_camera_content()
        
        # 默认隐藏所有内容框架
        self.localisation_2d_frame.pack_forget()
        self.localisation_3d_frame.pack_forget()
        
        # 显示无相机提示
        self.no_camera_label = ctk.CTkLabel(
            self.localisation_content_frame, 
            text="Please add and select a camera"
        )
        self.no_camera_label.pack(expand=True)
        
        # 更新相机列表
        self.update_localisation_camera_list()

    def create_detector_options_page(self):
        """创建检测器选项页面"""
        self.detector_options_frame = ctk.CTkFrame(self.detection_content_frame)
        self.detector_options_frame.pack(fill="both", expand=True)
        
        # 顶部框架
        self.detector_top_frame = ctk.CTkFrame(self.detector_options_frame, fg_color="transparent")
        self.detector_top_frame.pack(fill="x", padx=5, pady=(0,5))
        
        # 顶部框架标题和下拉菜单区域
        self.detector_selector_frame = ctk.CTkFrame(self.detector_top_frame, fg_color="transparent")
        self.detector_selector_frame.pack(side="left", fill="x", expand=True)
        
        # 检测器选择标签
        self.detector_select_label = ctk.CTkLabel(self.detector_selector_frame, text="选择检测器:")
        self.detector_select_label.pack(side="left", padx=(0, 10))
        
        # 获取可用检测器列表
        detector_names = self.detection_manager.get_available_detectors()
        detector_display_names = []
        
        # 创建检测器显示名称和内部名称的映射
        self.detector_name_mapping = {}
        
        # 准备下拉菜单的显示名称列表
        for detector_name in detector_names:
            if detector_name in self.detection_manager.available_detectors:
                display_name = self.detection_manager.available_detectors[detector_name]['name']
                detector_display_names.append(display_name)
                self.detector_name_mapping[display_name] = detector_name
        
        # 默认选择第一个检测器
        self.selected_detector_var = tk.StringVar(value=detector_display_names[0] if detector_display_names else "无可用检测器")
        
        # 检测器选择下拉菜单
        self.detector_selector = ctk.CTkOptionMenu(
            self.detector_selector_frame,
            values=detector_display_names,
            variable=self.selected_detector_var,
            command=self.on_detector_changed,
            width=150
        )
        self.detector_selector.pack(side="left", padx=5)
        
        # 检测开关区域
        self.detector_toggle_frame = ctk.CTkFrame(self.detector_top_frame, fg_color="transparent")
        self.detector_toggle_frame.pack(side="right", padx=10, pady=5)
        
        # 开关标签
        self.detector_toggle_label = ctk.CTkLabel(self.detector_toggle_frame, text="启用检测:")
        self.detector_toggle_label.pack(side="left", padx=5)
        
        # 检测开关
        self.detection_enabled_var = tk.BooleanVar(value=self.detection_manager.is_detection_enabled())
        self.detection_switch = ctk.CTkSwitch(
            self.detector_toggle_frame,
            text="",
            variable=self.detection_enabled_var,
            command=self.toggle_detection,
            onvalue=True,
            offvalue=False
        )
        self.detection_switch.pack(side="left", padx=5)
        
        # 主要内容区域
        self.detector_bottom_frame = ctk.CTkFrame(self.detector_options_frame, fg_color="transparent")
        self.detector_bottom_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 默认显示颜色轮廓配置面板
        for display_name, detector_name in self.detector_name_mapping.items():
            if detector_name == "ColorContour":
                # 设置下拉菜单选中颜色轮廓检测器
                self.selected_detector_var.set(display_name)
                # 触发显示颜色轮廓配置面板
                self.on_detector_changed(display_name)
                break

    def create_interaction_page(self):
        """创建交互页面"""
        self.interaction_frame = ctk.CTkFrame(self.detection_content_frame)
        self.interaction_frame.pack(fill="both", expand=True)
        
        # 使用独立的Blockly编辑器模块
        self.blockly_editor = BlocklyEditor(self.interaction_frame, self)

    def open_camera_setup(self):
        """打开相机设置窗口"""
        self.camera_setup.open_camera_setup()

    def on_camera_status_changed(self, action, data):
        """处理相机状态变化"""
        if action == "add":
            self.add_camera_status_frame(data)
            # 更新定位页面的相机列表
            if hasattr(self, 'localisation_camera_selector'):
                self.update_localisation_camera_list()
        elif action == "update":
            for status_frame in self.camera_status_frames:
                if status_frame["camera_index"] == data["index"]:
                    status_frame["status_label"].configure(text=f"状态: {data['status']}")
                    # 如果更新了激活状态
                    if "active" in data:
                        is_active = data["active"]
                        status_frame["active_indicator"].configure(
                            fg_color="green" if is_active else "gray",
                            hover_color="green" if is_active else "gray"
                        )
                        # 更新切换按钮的图标和悬停颜色
                        status_frame["toggle_button"].configure(
                            image=self.deactivate_icon if is_active else self.activate_icon,
                            hover_color="#B3B3B3" if is_active else "#41d054"
                        )
                    break
                    
        elif action == "remove":
            # 移除相机
            for i, status_frame in enumerate(self.camera_status_frames):
                if status_frame["camera_index"] == data["index"]:
                    status_frame["frame"].destroy()
                    self.camera_status_frames.pop(i)
                    break
            
            # 清空被移除相机的检测结果
            removed_index = data["index"]
            if removed_index < len(self.detection_results):
                self.detection_results[removed_index] = []
            
            # 更新定位页面的相机列表
            if hasattr(self, 'localisation_camera_selector'):
                self.update_localisation_camera_list()
                    
        elif action == "update_index":
            # 更新相机索引
            for status_frame in self.camera_status_frames:
                if status_frame["camera_index"] == data["old_index"]:
                    status_frame["camera_index"] = data["new_index"]
                    
                    # 更新按钮的命令
                    new_idx = data["new_index"]
                    is_active = status_frame["active_indicator"].cget("fg_color") == "green"
                    
                    status_frame["toggle_button"].configure(
                        command=lambda idx=new_idx, active=is_active: self.toggle_camera_state(idx, active)
                    )
                    status_frame["remove_button"].configure(
                        command=lambda idx=new_idx: self.remove_camera(idx)
                    )
                    break
            # 更新定位页面的相机列表
            if hasattr(self, 'localisation_camera_selector'):
                self.update_localisation_camera_list()
    
    def on_frame_update(self, frame, schedule_next=False):
        """处理相机帧更新"""
        if schedule_next:
            # 安排下一次帧处理
            if self.controller:
                self.dialog.after(50, self.controller._process_next_frame)
            return

        if frame is None:
            return

        try:
            if isinstance(frame, list) and len(frame) > 1:
                # 处理多个帧并进行拼接
                frames_to_combine = []
                # 找出所有帧中的最小高度
                min_height = min([f.shape[0] for f in frame if f is not None])
                
                # 调整所有帧的大小并保持纵横比
                for i, f in enumerate(frame):
                    if f is None:
                        continue
                        
                    # 获取对应的相机索引
                    camera_index = self.controller.active_cameras[i] if i < len(self.controller.active_cameras) else i
                    
                    # 应用目标检测（如果启用）
                    if self.detection_enabled:
                        # 获取当前选中的检测器名称
                        detector_name = self.detector_name_mapping[self.selected_detector_var.get()]
                        f, detection_results = self.detection_manager.process_frame(f, detector_name)
                        
                        # 保存检测结果到对应相机的结果列表
                        if camera_index < len(self.detection_results):
                            self.detection_results[camera_index] = detection_results
                    else:
                        # 如果检测未启用，清空检测结果
                        if camera_index < len(self.detection_results):
                            self.detection_results[camera_index] = []
                    
                    # 应用相机中心十字标记（如果启用）
                    if self.show_camera_center_cross:
                        f = self._draw_camera_center_cross(f)
                    
                    h, w = f.shape[:2]
                    # 计算调整后的宽度，保持纵横比
                    new_w = int(w * (min_height / h))
                    # 调整大小
                    resized_frame = cv2.resize(f, (new_w, min_height))
                    frames_to_combine.append(resized_frame)
                
                # 水平拼接所有帧
                combined_frame = np.hstack(frames_to_combine)
                # 将OpenCV BGR格式转换为PIL RGB格式
                image = cv2.cvtColor(combined_frame, cv2.COLOR_BGR2RGB)
                
                # 存储当前帧（存储拼接后的帧）
                self.current_frame = combined_frame
            else:
                # 处理单个帧的情况
                if isinstance(frame, list) and len(frame) == 1:
                    frame = frame[0]  # 如果是只有一个元素的列表，取第一个元素
                
                # 获取当前激活的相机索引
                active_cameras = self.controller.get_active_cameras()
                camera_index = active_cameras[0] if active_cameras else 0
                    
                # 应用目标检测（如果启用）
                if self.detection_enabled:
                    # 获取当前选中的检测器名称
                    detector_name = self.detector_name_mapping[self.selected_detector_var.get()]
                    frame, detection_results = self.detection_manager.process_frame(frame, detector_name)
                    
                    # 保存检测结果到对应相机的结果列表
                    if camera_index < len(self.detection_results):
                        self.detection_results[camera_index] = detection_results
                else:
                    # 如果检测未启用，清空检测结果
                    if camera_index < len(self.detection_results):
                        self.detection_results[camera_index] = []
                    
                # 应用相机中心十字标记（如果启用）
                if self.show_camera_center_cross:
                    frame = self._draw_camera_center_cross(frame)
                    
                # 将OpenCV BGR格式转换为PIL RGB格式
                image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # 存储当前帧（存储原始帧）
                self.current_frame = frame.copy()
            
            pil_image = Image.fromarray(image)
            
            scale = 0.8

            if Config.operating_system != "Windows":
                scale = 0.98

            new_width = int(self.preview_container.winfo_width()*scale)
            new_height = int(self.preview_container.winfo_height()*scale)
            
            # 缩放图像
            resized_image = pil_image.resize((new_width, new_height), Image.LANCZOS)
            
            # 转换为CTk图像对象
            ctk_image = ctk.CTkImage(resized_image, size=(new_width, new_height))
            
            # 存储当前帧图像
            self.current_frame_image = ctk_image
            self.preview_label.configure(image=ctk_image)
            self.preview_label.image = ctk_image
                
        except Exception as e:
            print(f"更新帧失败: {str(e)}")
    
    def add_camera_status_frame(self, camera_info):
        """添加相机状态面板"""
        status_frame = ctk.CTkFrame(self.camera_status_frame)
        
        row_index = len(self.camera_status_frames) + 2
        status_frame.grid(row=row_index, column=0, padx=5, pady=5, sticky="ew")
        
        # 配置网格布局
        status_frame.grid_columnconfigure(0, weight=1)
        
        # 标题和状态指示器行
        title_frame = ctk.CTkFrame(status_frame, fg_color="transparent")
        title_frame.grid(row=0, column=0, padx=5, pady=2, sticky="ew")
        
        title_frame.grid_columnconfigure(0, weight=1)  # 标题标签
        title_frame.grid_columnconfigure(1, weight=0)  # 状态指示器
        
        # 标题标签
        title_label = ctk.CTkLabel(title_frame, text=f"相机 {camera_info['index']+1}")
        title_label.grid(row=0, column=0, padx=5, pady=2, sticky="w")
        
        # 激活状态指示器
        active_indicator = ctk.CTkButton(
            title_frame,
            text="",
            width=10,
            height=10,
            corner_radius=7,
            fg_color="gray" if not camera_info.get("active", False) else "green",
            hover_color="gray" if not camera_info.get("active", False) else "green",
            border_width=0,
            state="disabled"
        )
        active_indicator.grid(row=0, column=1, padx=5, pady=2)
        
        # 信息行框架
        info_frame = ctk.CTkFrame(status_frame, fg_color="transparent")
        info_frame.grid(row=1, column=0, padx=5, pady=2, sticky="ew")
        info_frame.grid_columnconfigure(0, weight=1)
        
        # 类型标签
        type_label = ctk.CTkLabel(info_frame, text=f"类型: {camera_info['type']}")
        type_label.grid(row=0, column=0, padx=5, pady=1, sticky="w")
        
        # 信息标签
        if camera_info['type'] == "WebCamera":
            info_label = ctk.CTkLabel(info_frame, text=f"ID: {camera_info['id']}")
        elif camera_info['type'] == "IpCamera":
            info_label = ctk.CTkLabel(info_frame, text=f"地址: {camera_info['address']}")
        else:
            info_label = ctk.CTkLabel(info_frame, text="")
        info_label.grid(row=1, column=0, padx=5, pady=1, sticky="w")
        
        # 状态标签
        status_label = ctk.CTkLabel(
            info_frame, 
            text=f"状态: {camera_info['status']}"
        )
        status_label.grid(row=2, column=0, padx=5, pady=1, sticky="w")
        
        # 控制按钮框架
        control_buttons = ctk.CTkFrame(status_frame)
        control_buttons.grid(row=2, column=0, padx=5, pady=5, sticky="ew")
        
        # 配置控制按钮的网格布局
        control_buttons.grid_columnconfigure(0, weight=1)  # 使按钮均匀分布
        control_buttons.grid_columnconfigure(1, weight=1)
        
        # 相机索引
        camera_index = camera_info["index"]
        is_active = camera_info.get("active", False)
        
        # 激活/禁用按钮 - 根据当前状态显示不同图标
        toggle_button = ctk.CTkButton(
            control_buttons,
            text="",
            image=self.deactivate_icon if is_active else self.activate_icon,
            width=30,
            command=lambda idx=camera_index, active=is_active: self.toggle_camera_state(idx, active),
            fg_color="transparent",
            hover_color="#41d054" if not is_active else "#B3B3B3"
        )
        toggle_button.grid(row=0, column=0, padx=2, pady=2)
        
        # 移除按钮 - 使用图标
        remove_button = ctk.CTkButton(
            control_buttons,
            text="",
            image=self.bin_icon,
            width=30,
            command=lambda idx=camera_index: self.remove_camera(idx),
            fg_color="transparent",
            hover_color="#FF6B6B"
        )
        remove_button.grid(row=0, column=1, padx=2, pady=2)
        
        # 保存状态面板的引用
        self.camera_status_frames.append({
            "frame": status_frame,
            "title_label": title_label,
            "active_indicator": active_indicator,
            "type_label": type_label,
            "info_label": info_label,
            "status_label": status_label,
            "toggle_button": toggle_button,
            "remove_button": remove_button,
            "camera_index": camera_index  # 对应的相机索引
        })
    
    def toggle_camera_state(self, camera_index, is_currently_active):
        """切换相机激活状态"""
        if is_currently_active:
            success = self.deactivate_camera(camera_index)
        else:
            success = self.activate_camera(camera_index)
        
        # 如果状态切换成功，更新对应的状态框架
        if success:
            for status_frame in self.camera_status_frames:
                if status_frame["camera_index"] == camera_index:
                    # 更新激活状态
                    new_active_state = not is_currently_active
                    status_frame["active_indicator"].configure(
                        fg_color="green" if new_active_state else "gray",
                        hover_color="green" if new_active_state else "gray"
                    )
                    # 更新切换按钮的图标和悬停颜色
                    status_frame["toggle_button"].configure(
                        image=self.deactivate_icon if new_active_state else self.activate_icon,
                        hover_color="#B3B3B3" if new_active_state else "#41d054",
                        command=lambda idx=camera_index, active=new_active_state: self.toggle_camera_state(idx, active)
                    )
                    break
    
    def activate_camera(self, index):
        """激活指定相机"""
        return self.controller.activate_camera(index)
        
    def deactivate_camera(self, index):
        """禁用指定相机"""
        success = self.controller.deactivate_camera(index)
        if success:
            if self.controller.get_view_mode() == 'none':
                if self.current_frame_image:
                    width, height = self.current_frame_image._size
                else:
                    width, height = 640, 480
                
                # 创建黑色图像
                black_img = Image.new('RGB', (width, height), color='black')
                black_ctk_img = ctk.CTkImage(black_img, size=(width, height))
                
                # 设置黑色图像
                self.preview_label.configure(image=black_ctk_img)
                self.preview_label.image = black_ctk_img
        return success
    
    def remove_camera(self, index):
        """移除指定相机"""
        if self.controller.remove_camera(index):
            if self.controller.get_view_mode() == 'none':
                if self.current_frame_image:
                    width, height = self.current_frame_image._size
                else:
                    width, height = 640, 480
                
                # 创建黑色图像
                black_img = Image.new('RGB', (width, height), color='black')
                black_ctk_img = ctk.CTkImage(black_img, size=(width, height))
                
                # 设置黑色图像
                self.preview_label.configure(image=black_ctk_img)
                self.preview_label.image = black_ctk_img
    
    def show_error(self, message):
        """显示错误对话框"""
        error_window = ctk.CTkToplevel(self.dialog)
        error_window.title("错误")
        error_window.geometry("300x180")
        error_window.transient(self.dialog)
        error_window.grab_set()
        
        ctk.CTkLabel(
            error_window, 
            text=message,
            wraplength=280
        ).pack(padx=20, pady=20)
        
        ctk.CTkButton(
            error_window, 
            text="确定", 
            command=error_window.destroy
        ).pack(pady=10)

    def generate_charuco_board(self):
        """生成并显示Charuco标定板图像"""
        try:
            # 获取Charuco参数
            board_rows = int(self.board_rows_entry.get())
            board_cols = int(self.board_cols_entry.get())
            square_size = float(self.square_size_entry.get())
            marker_size = float(self.marker_size_entry.get())
            dictionary_str = self.dictionary_var.get()
            
            # 调用controller方法生成标定板
            success, message, board_img = self.controller.generate_charuco_board(
                board_rows, board_cols, square_size, marker_size, dictionary_str
            )
            
            if success and board_img is not None:
                # 将OpenCV图像转换为PIL格式
                board_img_rgb = cv2.cvtColor(board_img, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(board_img_rgb)
                
                # 调整图像大小以适应左侧框架
                frame_width = self.charuco_left_frame.winfo_width()
                frame_height = self.charuco_left_frame.winfo_height()
                
                # 如果框架尚未完全渲染，使用默认尺寸
                if frame_width <= 1 or frame_height <= 1:
                    frame_width = 500
                    frame_height = 500
                
                # 设置最小尺寸，防止图像过小导致布局问题
                min_width = 300
                min_height = 300
                frame_width = max(frame_width, min_width)
                frame_height = max(frame_height, min_height)
                
                # 保持纵横比
                img_width, img_height = pil_img.size
                aspect_ratio = img_width / img_height
                
                if frame_width / frame_height > aspect_ratio:
                    # 以高度为基准
                    new_height = frame_height
                    new_width = int(new_height * aspect_ratio)
                else:
                    # 以宽度为基准
                    new_width = frame_width
                    new_height = int(new_width / aspect_ratio)
                
                # 调整图像大小
                pil_img = pil_img.resize((new_width, new_height), Image.LANCZOS)
                
                tk_image = ImageTk.PhotoImage(pil_img)
                
                # 更新左侧框架中的图像标签
                # 设置固定最小尺寸，确保布局稳定
                self.charuco_image_label.configure(image=tk_image, width=min_width, height=min_height)
                self.charuco_image_label.image = tk_image
            else:
                self.show_error(message)
        except Exception as e:
            self.show_error(f"生成标定板失败: {str(e)}")
            
    def save_charuco_board(self):
        """保存Charuco标定板图像到用户选择的位置"""
        try:       
            # 获取保存格式
            save_format = "pdf" if self.use_pdf_var.get() else "png"
            
            # 根据选择的格式确定文件类型和扩展名
            if save_format == "pdf":
                file_types = [("PDF 文件", "*.pdf"), ("所有文件", "*.*")]
                default_ext = ".pdf"
            else:
                file_types = [("PNG 图像", "*.png"), ("所有文件", "*.*")]
                default_ext = ".png"
                
            # 获取标定板参数
            board_info = self.controller.get_charuco_board()
            if not board_info:
                self.show_error("无法获取标定板信息, 请尝试生成标定板")
                return
                
            # 默认文件名
            default_filename = f"charuco_board_{board_info['board_rows']}x{board_info['board_cols']}_{board_info['marker_size']}_{board_info['square_size']}_{board_info['dictionary_str']}{default_ext}"

            file_path = filedialog.asksaveasfilename(
                defaultextension=default_ext,
                filetypes=file_types,
                initialfile=default_filename
            )
            
            # 如果用户选择了文件路径
            if file_path:
                # 调用controller的保存函数
                success, message = self.controller.save_charuco_board(
                    file_path, save_format)
                
                if success:
                    messagebox.showinfo("成功", message)
                else:
                    self.show_error(message)
                
        except Exception as e:
            self.show_error(f"保存标定板失败: {str(e)}")

    def change_handeye_mode(self):
        """切换手眼标定模式"""
        mode = self.calibration_type_var.get()
        self.controller.set_handeye_mode(mode)
    
    def on_auto_calibrate_changed(self):
        """处理自动标定复选框状态变化"""
        is_auto = self.auto_calibrate_var.get()
        
        # 根据自动标定状态启用/禁用文件选择控件
        if is_auto:
            # 自动标定模式：启用文件选择控件
            self.file_path_entry.configure(state="normal")
            self.browse_button.configure(state="normal")
        else:
            # 手动标定模式：禁用文件选择控件
            self.file_path_entry.configure(state="disabled")
            self.browse_button.configure(state="disabled")
        
        # 采集按钮始终保持启用状态
    
    def browse_calibration_file(self):
        """浏览标定数据文件"""
        file_path = filedialog.askopenfilename(
            title="选择标定数据文件",
            filetypes=[
                ("所有支持的文件", "*.json *.yaml *.yml"),
                ("JSON 文件", "*.json"),
                ("YAML 文件", "*.yaml *.yml"),
                ("所有文件", "*.*")
            ]
        )
        
        if file_path:
            self.file_path_entry.delete(0, tk.END)
            self.file_path_entry.insert(0, file_path)
    
    def capture_current_pose(self):
        """捕获当前机器人位姿和相机图像"""
        try:
            # 检查是否为自动标定模式
            is_auto_mode = self.auto_calibrate_var.get()
            
            if is_auto_mode:
                # 自动标定模式：处理JSON文件
                self._process_auto_calibration()
            else:
                # 手动标定模式：捕获当前位姿
                self._capture_single_pose()
                
        except Exception as e:
            self.show_error(f"捕获位姿失败: {str(e)}")
    
    def _capture_single_pose(self):
        """手动标定模式：捕获单个位姿"""
        # 获取当前机器人位姿
        target_position = self.kinematics_frame.target_position.copy()
        target_orientation = self.kinematics_frame.target_orientation.copy()
        
        # 获取活动的相机
        active_cameras = self.controller.get_active_cameras()
        if not active_cameras:
            self.show_error("没有可用的相机，请先激活一个相机")
            return
        
        camera_index = active_cameras[0]
        
        # 组合机器人位姿为旋转向量和平移向量
        target_position = 1000*target_position
        target_orientation = np.radians(target_orientation)
        robot_pose = [
            target_position[0], target_position[1], target_position[2],
            target_orientation[0], target_orientation[1], target_orientation[2]
        ]
        
        # 调用控制器捕获手眼标定样本
        success, message, preview_image, num_corner = self.controller.capture_calibration_sample(
            camera_index, robot_pose
        )
        
        if success:
            # 更新预览图像
            if preview_image is not None:
                self._update_preview_image(preview_image)
            
            # 更新样本计数
            sample_count = len(self.controller.robot_rotations)
            self.pose_sample_count.set(sample_count)
            self.sample_count_label.configure(text=f"{sample_count}/9")
            
            # 更新状态
            self.hand_eye_status_label.configure(text=f"状态: {message}")
            
            # 如果样本数量足够，启用计算按钮
            if sample_count >= 9:
                self.calibrate_button.configure(state="normal")
        else:
            # 显示错误
            self.show_error(message)
            # 更新状态但不增加样本计数
            self.hand_eye_status_label.configure(text=f"状态: {message}")
    
    def _process_auto_calibration(self):
        """自动标定模式：处理JSON文件中的预定义位姿"""
        import json
        import time
        
        # 获取文件路径
        file_path = self.file_path_entry.get().strip()
        if not file_path:
            self.show_error("请先选择标定数据文件")
            return
        
        try:
            # 读取JSON文件
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 验证JSON格式
            if 'sequence' not in data:
                self.show_error("JSON文件格式错误：缺少'sequence'字段")
                return
            
            sequence = data['sequence']
            if not isinstance(sequence, list) or len(sequence) == 0:
                self.show_error("JSON文件格式错误：'sequence'必须是非空数组")
                return
            
            # 获取活动的相机
            active_cameras = self.controller.get_active_cameras()
            if not active_cameras:
                self.show_error("没有可用的相机，请先激活一个相机")
                return
            
            camera_index = active_cameras[0]
            
            # 更新状态
            self.hand_eye_status_label.configure(text=f"状态: 开始自动标定，共{len(sequence)}个位姿")
            
            # 用于收集错误信息
            failed_poses = []
            successful_poses = 0
            
            # 循环处理每个位姿
            for i, pose_data in enumerate(sequence):
                try:
                    # 验证位姿数据格式
                    if not all(key in pose_data for key in ['joints', 'position', 'orientation']):
                        failed_poses.append(f"位姿{i+1}: 数据格式错误，缺少必要字段")
                        continue
                    
                    
                    # 获取关节角度和位姿
                    joints = pose_data['joints']
                    position = pose_data['position']
                    orientation = pose_data['orientation']
                    
                    # 直接发送到机器人（不更新UI）
                    success, error_msg = self._send_to_robot(joint_angles=joints)
                    if not success:
                        failed_poses.append(f"位姿{i+1}: 机器人移动失败 - {error_msg}")
                        continue
                    
                    # 等待机器人稳定（机器人已经移动到位，现在等待稳定）
                    time.sleep(1)  # 短暂等待确保机器人完全稳定
                    
                    # 捕获当前位姿
                    target_position_mm = np.array(position) * 1000  # 转换为毫米
                    target_orientation_rad = np.radians(np.array(orientation))  # 转换为弧度
                    robot_pose = [
                        target_position_mm[0], target_position_mm[1], target_position_mm[2],
                        target_orientation_rad[0], target_orientation_rad[1], target_orientation_rad[2]
                    ]
                    
                    # 调用控制器捕获手眼标定样本
                    success, message, preview_image, num_corner = self.controller.capture_calibration_sample(
                        camera_index, robot_pose
                    )
                    
                    if success:
                        successful_poses += 1
                        # 更新预览图像（只显示最后一个成功的图像）
                        if preview_image is not None:
                            self._update_preview_image(preview_image)
                        
                        # 更新样本计数
                        sample_count = len(self.controller.robot_rotations)
                        self.pose_sample_count.set(sample_count)
                        self.sample_count_label.configure(text=f"{sample_count}/9")
                        
                        
                    else:
                        failed_poses.append(f"位姿{i+1}: 捕获失败 - {message}")
                        # 继续处理下一个位姿，不中断整个流程
                        continue
                    
                    # 强制更新UI
                    self.dialog.update()
                    
                except Exception as e:
                    failed_poses.append(f"位姿{i+1}: 处理错误 - {str(e)}")
                    continue
            
            # 完成自动标定
            final_sample_count = len(self.controller.robot_rotations)
            
            # 显示标定结果摘要
            if failed_poses:
                # 如果有失败的位姿，显示摘要错误信息
                error_summary = f"失败详情:\n" + "\n".join(failed_poses)
                self.show_error(error_summary)
                self.hand_eye_status_label.configure(text=f"状态: 共采集{final_sample_count}个样本 ({len(failed_poses)}个失败)")
            else:
                self.hand_eye_status_label.configure(text=f"状态: 共采集{final_sample_count}个样本")
            
            # 如果样本数量足够，启用计算按钮
            if final_sample_count >= 9:
                self.calibrate_button.configure(state="normal")
            
        except FileNotFoundError:
            self.show_error(f"找不到文件: {file_path}")
        except json.JSONDecodeError as e:
            self.show_error(f"JSON文件解析错误: {str(e)}")
        except Exception as e:
            self.show_error(f"处理自动标定文件时发生错误: {str(e)}")
    
    def _update_preview_image(self, preview_image):
        """更新预览图像的通用方法"""
        try:
            # 转换为PIL格式
            frame_rgb = cv2.cvtColor(preview_image, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(frame_rgb)
            
            # 调整图像大小
            preview_width = self.pose_preview_label.winfo_width()
            preview_height = self.pose_preview_label.winfo_height()
            
            if preview_width > 1 and preview_height > 1:
                # 保持纵横比
                img_width, img_height = pil_img.size
                aspect_ratio = img_width / img_height
                
                if preview_width / preview_height > aspect_ratio:
                    new_height = preview_height
                    new_width = int(new_height * aspect_ratio)
                else:
                    new_width = preview_width
                    new_height = int(new_width / aspect_ratio)
                    
                pil_img = pil_img.resize((new_width, new_height), Image.LANCZOS)
            
            ctk_image = ctk.CTkImage(pil_img, size=(new_width, new_height))
            
            # 更新预览标签
            self.pose_preview_label.configure(image=ctk_image)
            self.pose_preview_label.image = ctk_image
            
        except Exception as e:
            print(f"更新预览图像失败: {str(e)}")
    
    def _send_to_robot(self, joint_angles=None):
        """发送机器人运动命令并等待执行完成
        
        Args:
            joint_angles: 关节角度列表 (度)，如果为None则使用kinematics frame的值
        
        Returns:
            tuple: (success, error_message)
        """
        try:
            # 获取关节角度和工具值
            if joint_angles is None:
                joint_angles = [angle for angle in self.kinematics_frame.joint_angles]
            
            # 检查协议连接
            if not self.kinematics_frame.protocol_class.is_connected():
                return False, "机器人未连接"
            
            # 发送执行命令
            self.kinematics_frame.protocol_class.send("EXEC\n")
            
            # 发送关节角度命令
            joint_command = ",".join(f"{angle:.2f}" for angle in joint_angles) + "\n"
            self.kinematics_frame.protocol_class.send(joint_command)
            
            # 等待关节运动完成 - 等待 CP0 信号
            _, isReplied = self.kinematics_frame.protocol_class.receive(timeout=5, expected_signal="CP0")
            if not isReplied:
                return False, "关节运动执行超时"
            
            # 更新终端显示
            self.kinematics_frame.update_terminal(
                f"关节角度: {[f'{angle:.2f}°' for angle in joint_angles]}\n"
            )
            
            return True, ""
            
        except Exception as e:
            return False, f"发送命令时发生异常: {str(e)}"

    def set_board_to_ee_offset(self):
        """设置标定板到末端执行器的偏移"""
        try:
            # 获取位置偏移值（毫米）
            x_offset = float(self.tcp_offset_x.get())
            y_offset = float(self.tcp_offset_y.get())
            z_offset = float(self.tcp_offset_z.get())
            
            # 获取方向偏移值（度转弧度）
            rx_offset = np.radians(float(self.tcp_offset_rx.get()))
            ry_offset = np.radians(float(self.tcp_offset_ry.get()))
            rz_offset = np.radians(float(self.tcp_offset_rz.get()))
            
            # 组合偏移值 [X, Y, Z, R, P, Y]
            offset = [x_offset, y_offset, z_offset, rx_offset, ry_offset, rz_offset]
            
            # 调用控制器设置偏移
            success = self.controller.set_board_to_ee_offset(offset)
            
            if success:
                # 更新状态标签
                self.offset_status_label.configure(text=f"(offset: {x_offset:.1f}, {y_offset:.1f}, {z_offset:.1f}mm)")
            else:
                self.show_error("设置偏移失败")
                
        except ValueError as e:
            self.show_error(f"输入值无效: {str(e)}")
        except Exception as e:
            self.show_error(f"设置偏移失败: {str(e)}")
    
    def reset_hand_eye_calibration(self):
        """重置手眼标定"""
        self.controller.reset_calibration()
        self.calibration_result = None
        
        # 重置UI状态
        self.pose_sample_count.set(0)
        self.sample_count_label.configure(text="0/10")
        self.calibrate_button.configure(state="disabled")
        self.hand_eye_status_label.configure(text="状态: 未标定")
    
    def calculate_hand_eye_transform(self):
        """计算手眼变换矩阵"""
        try:
            # 检查是否有足够的样本
            sample_count = len(self.controller.robot_rotations)
            if sample_count < 9:
                self.show_error("需要至少9组样本才能计算手眼变换")
                return
            
            # 获取标定类型
            calibration_type = self.calibration_type_var.get()
            
            # 调用控制器计算手眼变换
            success, message, self.calibration_result = self.controller.calibrate()
            
            if success:
                # 更新状态
                self.hand_eye_status_label.configure(text=f"状态: {message}")
                self.show_calibration_page("result")
                
                # 更新方法选择选项
                self._update_method_selection_options()
                
                # 显示默认方法（HORAUD）的结果
                self.selected_method_var.set("HORAUD")
                self._display_selected_method_result("HORAUD")
                
                # 成功后显示通知
                messagebox.showinfo("标定完成", "手眼标定计算完成，请查看结果页面")
                
                # 在3D图中可视化相机位置和视场
                self._visualize_camera_3d()
            else:
                self.show_error(f"计算手眼变换失败: {message}")
                self.hand_eye_status_label.configure(text="状态: 计算失败")
        except Exception as e:
            self.show_error(f"计算手眼变换失败: {str(e)}")
            self.hand_eye_status_label.configure(text="状态: 计算异常")
    
    def save_calibration_result(self):
        """保存标定结果"""
        if self.calibration_result is None:
            self.show_error("没有可保存的标定结果")
            return
            
        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".yaml",
                filetypes=[("YAML 文件", "*.yaml"), ("所有文件", "*.*")],
                initialfile="handeye_calibration.yaml"
            )
            
            if file_path:
                # 保存到文件
                fs = cv2.FileStorage(file_path, cv2.FILE_STORAGE_WRITE)

                # 保存标定类型
                calibration_type = self.calibration_type_var.get()
                fs.write("calibration_type", calibration_type)
                
                # 保存当前选择的方法
                selected_method = self.selected_method_var.get()
                fs.write("selected_method", selected_method)
                
                # 保存手眼变换矩阵（当前控制器中的）
                fs.write("handeye_transform", self.calibration_result['handeye_transform'])
                
                # 保存所有方法的结果
                if 'all_handeye_results' in self.calibration_result:
                    for method_name, transform in self.calibration_result['all_handeye_results'].items():
                        if transform is not None:
                            fs.write(f"handeye_{method_name}", transform)
                        else:
                            # 对于失败的方法，写入一个标记
                            fs.write(f"handeye_{method_name}_failed", 1)
                
                # 保存相机内参
                fs.write("camera_matrix", self.calibration_result['camera_matrix'])
                
                # 保存畸变系数
                fs.write("dist_coeffs", self.calibration_result['dist_coeffs'])
                
                # 保存重投影误差
                fs.write("reprojection_error", self.calibration_result['reprojection_error'])
                
                fs.release()
                
                messagebox.showinfo("保存成功", f"手眼标定结果已保存到: {file_path}")
                
        except Exception as e:
            self.show_error(f"保存标定结果失败: {str(e)}")

    def load_calibration_result(self):
        """从文件加载标定结果"""
        try:
            file_path = filedialog.askopenfilename(
                filetypes=[("YAML 文件", "*.yaml"), ("所有文件", "*.*")],
                title="选择标定结果文件"
            )
            
            if not file_path:
                return
                
            # 读取文件
            fs = cv2.FileStorage(file_path, cv2.FILE_STORAGE_READ)
            
            if not fs.isOpened():
                self.show_error(f"无法打开文件: {file_path}")
                return

            # 读取基本标定数据
            calibration_type = fs.getNode("calibration_type").string()
            handeye_transform = fs.getNode("handeye_transform").mat()
            camera_matrix = fs.getNode("camera_matrix").mat()
            dist_coeffs = fs.getNode("dist_coeffs").mat()
            reprojection_error = fs.getNode("reprojection_error").real()
            
            # 尝试读取选择的方法（新格式）
            selected_method = fs.getNode("selected_method").string()
            if not selected_method:
                # 兼容旧格式
                selected_method = fs.getNode("handeye_method").string()
                if not selected_method:
                    selected_method = "HORAUD"  # 默认方法
            
            # 读取所有方法的结果
            all_handeye_results = {}
            methods = ["TSAI", "PARK", "HORAUD", "ANDREFF"]
            
            for method in methods:
                method_transform = fs.getNode(f"handeye_{method}").mat()
                method_failed = fs.getNode(f"handeye_{method}_failed").real()
                
                if method_transform is not None:
                    all_handeye_results[method] = method_transform
                elif method_failed is not None:
                    all_handeye_results[method] = None
                # 如果都没有，则该方法不存在于文件中
            
            fs.release()
            
            # 确保所有必要的数据都已读取
            if any(x is None for x in [calibration_type, handeye_transform, 
                                     camera_matrix, dist_coeffs, reprojection_error]):
                self.show_error("文件中缺少必要的标定数据")
                return
            
            # 保存到类变量
            self.calibration_result = {
                'calibration_type': calibration_type,
                'handeye_transform': handeye_transform,
                'camera_matrix': camera_matrix,
                'dist_coeffs': dist_coeffs,
                'reprojection_error': reprojection_error
            }
            
            # 如果有多个方法的结果，添加到标定结果中
            if all_handeye_results:
                self.calibration_result['all_handeye_results'] = all_handeye_results
            
            # 设置标定类型
            self.calibration_type_var.set(calibration_type)
            
            # 更新控制器中的变换矩阵和模式
            self.controller.handeye_transform = handeye_transform
            self.controller.handeye_mode = calibration_type
            self.controller.camera_matrix = camera_matrix
            self.controller.dist_coeffs = dist_coeffs
            
            # 切换到结果页面
            self.show_calibration_page("result")
            
            # 更新方法选择选项
            self._update_method_selection_options()
            
            # 设置选择的方法并显示结果
            if all_handeye_results and selected_method in all_handeye_results:
                self.selected_method_var.set(selected_method)
                self._display_selected_method_result(selected_method)
            else:
                # 兼容旧格式，显示加载的变换
                result_text = f"{'手眼标定 (Eye-in-Hand)' if calibration_type == 'eye_in_hand' else '手眼外标定 (Eye-to-Hand)'}结果:\n\n"
                result_text += f"标定方法: {selected_method}\n\n"
                result_text += "变换矩阵:\n"
                
                # 格式化变换矩阵
                for i in range(4):
                    for j in range(4):
                        result_text += f"{float(handeye_transform[i, j]):.4f}\t"
                    result_text += "\n"
                
                # 提取旋转矩阵和平移向量
                rotation_matrix = handeye_transform[:3, :3]
                translation_vector = handeye_transform[:3, 3]
                
                result_text += "\n旋转矩阵:\n"
                for i in range(3):
                    for j in range(3):
                        result_text += f"{float(rotation_matrix[i, j]):.4f}\t"
                    result_text += "\n"
                
                result_text += "\n平移向量:\n"
                result_text += f"X: {float(translation_vector[0]):.4f}\n"
                result_text += f"Y: {float(translation_vector[1]):.4f}\n"
                result_text += f"Z: {float(translation_vector[2]):.4f}\n"

                # 添加相机内参矩阵
                result_text += "\n相机内参矩阵:\n"
                for i in range(3):
                    for j in range(3):
                        result_text += f"{float(camera_matrix[i, j]):.4f}\t"
                    result_text += "\n"

                # 添加畸变系数
                result_text += "\n畸变系数:\n"
                for i in range(len(dist_coeffs)):
                    result_text += f"{float(dist_coeffs[i]):.4f}\t"
                result_text += "\n"

                # 添加重投影误差
                result_text += f"\n重投影误差: {reprojection_error:.4f}\n"

                self.result_text.configure(state="normal")
                self.result_text.delete("1.0", tk.END)
                self.result_text.insert("1.0", result_text)
                self.result_text.configure(state="disabled")
            
            # 更新状态
            self.hand_eye_status_label.configure(text=f"状态: 已加载标定结果")
            
            # 在3D图中可视化相机位置和视场
            self._visualize_camera_3d()
            
        except Exception as e:
            self.show_error(f"加载标定结果失败: {str(e)}")
            import traceback
            traceback.print_exc()

    def _update_method_selection_options(self):
        """更新方法选择选项"""
        if self.calibration_result and 'all_handeye_results' in self.calibration_result:
            available_methods = []
            for method_name, result in self.calibration_result['all_handeye_results'].items():
                if result is not None:
                    available_methods.append(method_name)
            
            if available_methods:
                self.method_selector.configure(values=available_methods)
                self.set_transform_button.configure(state="normal")
            else:
                self.method_selector.configure(values=["无可用方法"])
                self.set_transform_button.configure(state="disabled")
        else:
            self.method_selector.configure(values=["无可用方法"])
            self.set_transform_button.configure(state="disabled")

    def _on_method_selection_changed(self, selected_method):
        """处理方法选择变化"""
        if self.calibration_result and 'all_handeye_results' in self.calibration_result:
            self._display_selected_method_result(selected_method)
            self._update_3d_visualization_with_method(selected_method)

    def _display_selected_method_result(self, method_name):
        """显示选定方法的结果"""
        if not self.calibration_result or 'all_handeye_results' not in self.calibration_result:
            return
            
        all_results = self.calibration_result['all_handeye_results']
        if method_name not in all_results or all_results[method_name] is None:
            self.result_text.configure(state="normal")
            self.result_text.delete("1.0", tk.END)
            self.result_text.insert("1.0", f"方法 {method_name} 计算失败")
            self.result_text.configure(state="disabled")
            return
        
        transform_matrix = all_results[method_name]
        calibration_type = self.calibration_type_var.get()
        
        # 生成结果文本
        result_text = f"{'手眼标定 (Eye-in-Hand)' if calibration_type == 'eye_in_hand' else '手眼外标定 (Eye-to-Hand)'}结果:\n\n"
        result_text += f"标定方法: {method_name}\n\n"
        result_text += "变换矩阵:\n"

        # 格式化变换矩阵
        for i in range(4):
            for j in range(4):
                result_text += f"{transform_matrix[i, j]:.4f}\t"
            result_text += "\n"

        # 提取旋转矩阵和平移向量
        rotation_matrix = transform_matrix[:3, :3]
        translation_vector = transform_matrix[:3, 3]

        result_text += "\n旋转矩阵:\n"
        for i in range(3):
            for j in range(3):
                result_text += f"{rotation_matrix[i, j]:.4f}\t"
            result_text += "\n"

        result_text += "\n平移向量:\n"
        result_text += f"X: {translation_vector[0]:.4f}\n"
        result_text += f"Y: {translation_vector[1]:.4f}\n"
        result_text += f"Z: {translation_vector[2]:.4f}\n"

        # 添加相机内参矩阵
        if 'camera_matrix' in self.calibration_result:
            result_text += "\n相机内参矩阵:\n"
            camera_matrix = self.calibration_result["camera_matrix"]
            for i in range(3):
                for j in range(3):
                    result_text += f"{camera_matrix[i, j]:.4f}\t"
                result_text += "\n"

        # 添加畸变系数
        if 'dist_coeffs' in self.calibration_result:
            result_text += "\n畸变系数:\n"
            dist_coeffs = np.array(self.calibration_result["dist_coeffs"]).flatten()
            for coeff in dist_coeffs:
                result_text += f"{float(coeff):.4f}\t"
            result_text += "\n"

        # 添加重投影误差
        if 'reprojection_error' in self.calibration_result:
            result_text += f"\n重投影误差: {self.calibration_result['reprojection_error']:.4f}\n"

        # 显示结果
        self.result_text.configure(state="normal")
        self.result_text.delete("1.0", tk.END)
        self.result_text.insert("1.0", result_text)
        self.result_text.configure(state="disabled")

    def _update_3d_visualization_with_method(self, method_name):
        """使用指定方法的结果更新3D可视化"""
        if not self.calibration_result or 'all_handeye_results' not in self.calibration_result:
            return
            
        all_results = self.calibration_result['all_handeye_results']
        if method_name not in all_results or all_results[method_name] is None:
            return
        
        try:
            # 临时设置控制器的手眼变换为选定方法的结果
            original_transform = self.controller.handeye_transform
            self.controller.handeye_transform = all_results[method_name]
            
            # 更新3D可视化
            self._visualize_camera_3d()
            
            # 恢复原始变换（只是为了可视化，不改变控制器的实际设置）
            self.controller.handeye_transform = original_transform
            
        except Exception as e:
            print(f"更新3D可视化失败: {str(e)}")

    def _set_selected_transform(self):
        """将选定的变换设置为控制器的当前变换"""
        selected_method = self.selected_method_var.get()
        
        if not self.calibration_result or 'all_handeye_results' not in self.calibration_result:
            self.show_error("没有可用的标定结果")
            return
            
        all_results = self.calibration_result['all_handeye_results']
        if selected_method not in all_results or all_results[selected_method] is None:
            self.show_error(f"方法 {selected_method} 的结果不可用")
            return
        
        try:
            # 设置控制器的手眼变换
            self.controller.handeye_transform = all_results[selected_method]
            
            # 更新3D可视化
            self._visualize_camera_3d()
            
            # 显示成功消息
            messagebox.showinfo("设置成功", f"已将 {selected_method} 方法的结果设置为当前手眼变换")
            
        except Exception as e:
            self.show_error(f"设置变换失败: {str(e)}")

    def on_detector_changed(self, selected_display_name):
        """处理检测器选择变化，显示相应的配置界面"""
        # 清除当前配置面板内容
        for widget in self.detector_bottom_frame.winfo_children():
            widget.destroy()
        
        # 根据显示名称获取检测器的内部名称
        if selected_display_name in self.detector_name_mapping:
            detector_name = self.detector_name_mapping[selected_display_name]
            detector = self.detection_manager.get_detector(detector_name)
            
            # 创建配置界面
            if detector_name == "ColorContour":
                self._create_color_contour_config_panel(detector)
            elif detector_name == "FrequencyDomain":
                self._create_frequency_domain_config_panel(detector)
            
        # 更新配置面板高度
        self.detector_bottom_frame.update_idletasks()

    def toggle_detection(self):
        """切换检测功能的开启/关闭状态"""
        if self.detection_enabled_var.get():
            # 获取选定的检测器
            detector_name = self.detector_name_mapping[self.selected_detector_var.get()]
            self.detection_manager.enable_detection()
            self.detection_enabled = True
        else:
            self.detection_manager.disable_detection()
            self.detection_enabled = False
            # 当检测被禁用时，清空所有检测结果
            self.clear_detection_results()
    
    def clear_detection_results(self, camera_index=None):
        """清空检测结果
        
        Args:
            camera_index: 相机索引，如果为None则清空所有相机的检测结果
        """
        if camera_index is not None:
            if 0 <= camera_index < len(self.detection_results):
                self.detection_results[camera_index] = []
        else:
            # 清空所有相机的检测结果
            for i in range(len(self.detection_results)):
                self.detection_results[i] = []

    def on_closing(self):
        """窗口关闭时的处理"""
        if self.camera_setup:
            self.camera_setup.cleanup_setup_window()

        # 停止坐标更新
        if hasattr(self, 'coordinate_update_job') and self.coordinate_update_job:
            self.dialog.after_cancel(self.coordinate_update_job)

        self.controller.release_all()
        self.detection_manager.release_all()
        self.dialog.destroy()

    def create_2d_camera_content(self):
        """创建2D相机内容区域"""
        self.localisation_2d_frame = ctk.CTkFrame(self.localisation_content_frame)
        self.localisation_2d_frame.pack(fill="both", expand=True)
        
        # 左侧框架 - 包含参数设置
        left_frame = ctk.CTkFrame(self.localisation_2d_frame, fg_color="#B3B3B3")
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        # 右侧框架 - 包含可视化控制和坐标显示
        right_frame = ctk.CTkFrame(self.localisation_2d_frame, fg_color="transparent")
        right_frame.pack(side="right", fill="y")
        
        # === 左侧内容：2D定位参数区域 ===
        params_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        params_frame.pack(fill="x", pady=10)
        
        params_title = ctk.CTkLabel(params_frame, text="定位参数")
        params_title.pack(anchor="w", pady=5, padx=5)
        
        # 坐标系原点偏移容器
        offset_container = ctk.CTkFrame(params_frame, fg_color="transparent")
        offset_container.pack(fill="x", pady=5)
        
        # 坐标系原点偏移
        offset_frame = ctk.CTkFrame(offset_container, fg_color="transparent")
        offset_frame.pack(fill="x", pady=5)
        
        # Z高度设置
        z_height_subframe = ctk.CTkFrame(offset_frame, fg_color="transparent")
        z_height_subframe.pack(fill="x", pady=2)
        
        z_height_label = ctk.CTkLabel(z_height_subframe, text="Z轴高度 (mm):")
        z_height_label.pack(side="left", padx=(20, 10))
        
        self.z_height_entry = ctk.CTkEntry(
            z_height_subframe, 
            placeholder_text="输入Z轴高度",
            width=100
        )
        self.z_height_entry.pack(side="left")
        self.z_height_entry.insert(0, "0.0")  # 默认值
        
        # X偏移
        x_offset_subframe = ctk.CTkFrame(offset_frame, fg_color="transparent")
        x_offset_subframe.pack(fill="x", pady=2)
        
        x_offset_label = ctk.CTkLabel(x_offset_subframe, text="X偏移 (mm):")
        x_offset_label.pack(side="left", padx=(20, 10))
        
        self.x_offset_entry = ctk.CTkEntry(x_offset_subframe, width=100)
        self.x_offset_entry.pack(side="left")
        self.x_offset_entry.insert(0, "0.0")
        
        # Y偏移
        y_offset_subframe = ctk.CTkFrame(offset_frame, fg_color="transparent")
        y_offset_subframe.pack(fill="x", pady=2)
        
        y_offset_label = ctk.CTkLabel(y_offset_subframe, text="Y偏移 (mm):")
        y_offset_label.pack(side="left", padx=(20, 10))
        
        self.y_offset_entry = ctk.CTkEntry(y_offset_subframe, width=100)
        self.y_offset_entry.pack(side="left")
        self.y_offset_entry.insert(0, "0.0")
        
        # 应用按钮 - 放在offset_frame的最后一行
        apply_button_subframe = ctk.CTkFrame(offset_frame, fg_color="transparent")
        apply_button_subframe.pack(fill="x", pady=(10, 2))
        
        apply_localisation_button = ctk.CTkButton(
            apply_button_subframe,
            text="应用设置",
            command=self.on_apply_localisation,
            width=120
        )
        apply_localisation_button.pack(side="left", padx=(20, 0))
        
        # === 右侧内容：控制按钮和坐标显示 ===
        # 捕获相机中心坐标按钮
        self.capture_center_button = ctk.CTkButton(
            right_frame,
            text="显示投影中心坐标",
            command=self.on_capture_camera_center,
            width=120
        )
        self.capture_center_button.pack(pady=(10,5), padx=10)
        
        # 验证机器人位姿按钮
        self.validate_robot_pose_button = ctk.CTkButton(
            right_frame,
            text="验证机器人位姿",
            command=self.on_validate_robot_pose,
            width=120
        )
        self.validate_robot_pose_button.pack(pady=5, padx=10)
        
        # 世界坐标显示框架
        world_coords_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        world_coords_frame.pack(fill="x", padx=10, pady=10)
        
        world_coords_title = ctk.CTkLabel(world_coords_frame, text="世界坐标:")
        world_coords_title.pack(anchor="w", pady=(5, 5), padx=5)
        
        # X坐标
        x_coord_frame = ctk.CTkFrame(world_coords_frame, fg_color="transparent")
        x_coord_frame.pack(fill="x", pady=2, padx=5)
        
        x_coord_label = ctk.CTkLabel(x_coord_frame, text="X:", width=20)
        x_coord_label.pack(side="left")
        
        self.x_coord_value = ctk.CTkLabel(x_coord_frame, text="0.000 mm")
        self.x_coord_value.pack(side="left", padx=(5, 0))
        
        # Y坐标
        y_coord_frame = ctk.CTkFrame(world_coords_frame, fg_color="transparent")
        y_coord_frame.pack(fill="x", pady=2, padx=5)
        
        y_coord_label = ctk.CTkLabel(y_coord_frame, text="Y:", width=20)
        y_coord_label.pack(side="left")
        
        self.y_coord_value = ctk.CTkLabel(y_coord_frame, text="0.000 mm")
        self.y_coord_value.pack(side="left", padx=(5, 0))
        
        # Z坐标
        z_coord_frame = ctk.CTkFrame(world_coords_frame, fg_color="transparent")
        z_coord_frame.pack(fill="x", pady=2, padx=5)
        
        z_coord_label = ctk.CTkLabel(z_coord_frame, text="Z:", width=20)
        z_coord_label.pack(side="left")
        
        self.z_coord_value = ctk.CTkLabel(z_coord_frame, text="0.000 mm")
        self.z_coord_value.pack(side="left", padx=(5, 0))

    def create_3d_camera_content(self):
        """创建3D相机内容区域"""
        self.localisation_3d_frame = ctk.CTkFrame(self.localisation_content_frame)
        
        # 3D相机不支持消息
        unsupported_label = ctk.CTkLabel(
            self.localisation_3d_frame,
            text="不支持，等待新版本发布",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        unsupported_label.pack(expand=True, pady=50)

    def update_localisation_camera_list(self):
        """更新定位页面的相机列表"""
        camera_options = []
        
        # 从相机状态框架中获取相机信息
        for status_frame in self.camera_status_frames:
            camera_index = status_frame["camera_index"]
            camera_type = None
            
            # 从类型标签中提取相机类型
            type_text = status_frame["type_label"].cget("text")
            if "WebCamera" in type_text:
                camera_type = "WebCamera"
            elif "IpCamera" in type_text:
                camera_type = "IpCamera"  
            elif "ZEDCamera" in type_text:
                camera_type = "ZEDCamera"
            
            if camera_type:
                display_name = f"相机 {camera_index + 1} ({camera_type})"
                camera_options.append(display_name)
        
        # 更新下拉菜单选项
        if camera_options:
            self.localisation_camera_selector.configure(values=camera_options)
            if self.selected_localisation_camera_var.get() == "无可用相机":
                self.selected_localisation_camera_var.set(camera_options[0])
                self.on_localisation_camera_changed(camera_options[0])
        else:
            self.localisation_camera_selector.configure(values=["无可用相机"])
            self.selected_localisation_camera_var.set("无可用相机")
            self.on_localisation_camera_changed("无可用相机")
            
    def on_localisation_camera_changed(self, selected_camera):
        """处理定位页面相机选择变化"""
        # 隐藏所有内容框架
        self.localisation_2d_frame.pack_forget()
        self.localisation_3d_frame.pack_forget()
        self.no_camera_label.pack_forget()
        
        if selected_camera == "无可用相机":
            # 显示无相机提示
            self.no_camera_label.pack(expand=True)
            return
        
        # 解析相机类型
        if "WebCamera" in selected_camera or "IpCamera" in selected_camera:
            # 显示2D相机内容
            self.localisation_2d_frame.pack(fill="both", expand=True)
        elif "ZEDCamera" in selected_camera:
            # 显示3D相机内容
            self.localisation_3d_frame.pack(fill="both", expand=True)

    def on_apply_localisation(self):
        """应用本地化设置"""
        try:
            z_height = float(self.z_height_entry.get())
            x_offset = float(self.x_offset_entry.get())
            y_offset = float(self.y_offset_entry.get())
            
            # 设置到相机控制器
            self.controller.set_localisation_offsets(x_offset, y_offset, z_height)
            
            # 立即更新相机中心坐标显示以反映新的偏移设置
            self.update_camera_center_coordinates()
            
            messagebox.showinfo("success", f"z offset: {z_height} mm\nX offset: {x_offset} mm\nY offset: {y_offset} mm")
        except ValueError as e:
            self.show_error(f"输入值无效: {str(e)}")
        except Exception as e:
            self.show_error(f"应用设置失败: {str(e)}")

    def update_camera_center_coordinates(self):
        """更新相机光轴与指定平面的交点坐标"""
        try:
            # 获取当前机器人位置和姿态
            target_position = self.kinematics_frame.target_position
            target_orientation = np.radians(self.kinematics_frame.target_orientation)
            
            # 获取当前帧的图像尺寸
            image_size = None
            if self.current_frame is not None:
                height, width = self.current_frame.shape[:2]
                image_size = (width, height)
            
            success, x_mm, y_mm, z_mm = self.controller.project_to_plane(
                target_position, target_orientation, 
                pixel_x=None, pixel_y=None, 
                image_size=image_size
            )
            
            if success:
                # 更新显示
                self.x_coord_value.configure(text=f"{x_mm:.3f} mm")
                self.y_coord_value.configure(text=f"{y_mm:.3f} mm")
                self.z_coord_value.configure(text=f"{z_mm:.3f} mm")
            else:
                # 计算失败，显示默认值
                self.x_coord_value.configure(text="--- mm")
                self.y_coord_value.configure(text="--- mm")
                self.z_coord_value.configure(text="--- mm")
            
        except Exception as e:
            # 发生错误时显示默认值
            self.x_coord_value.configure(text="--- mm")
            self.y_coord_value.configure(text="--- mm")
            self.z_coord_value.configure(text="--- mm")

    def _create_color_contour_config_panel(self, detector):
        """为颜色轮廓检测器创建配置面板"""
        config = detector.config
        
        # 创建滚动框架以容纳所有控件
        config_frame = ctk.CTkScrollableFrame(self.detector_bottom_frame, fg_color="#B3B3B3")
        config_frame.pack(fill="both", expand=True)
        
        # 当前颜色选择区域
        color_selection_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        color_selection_frame.pack(fill="x", pady=10)
        
        color_label = ctk.CTkLabel(color_selection_frame, text="目标颜色:")
        color_label.pack(side="left", padx=(0, 10))
        
        # 当前颜色按钮
        self.current_color_button = ctk.CTkButton(
            color_selection_frame,
            text="选择目标颜色",
            command=self._choose_target_color,
            width=120,
            height=30
        )
        self.current_color_button.pack(side="left", padx=(0, 10))
        
        # 从帧捕获颜色按钮
        self.capture_color_button = ctk.CTkButton(
            color_selection_frame,
            text="从帧捕获颜色",
            command=self._capture_color_from_frame,
            width=120,
            height=30
        )
        self.capture_color_button.pack(side="left", padx=(0, 10))
        
        # 当前颜色预览
        self.current_color_preview = ctk.CTkLabel(
            color_selection_frame,
            text="",
            width=25,
            height=25,
            corner_radius=5
        )
        self.current_color_preview.pack(side="left", padx=(0, 10))
        
        # 存储当前目标颜色的HSV值
        current_lower = config['color_lower']
        current_upper = config['color_upper']
        # 计算中心颜色作为目标颜色
        self.target_color_hsv = [
            (current_lower[0] + current_upper[0]) // 2,
            (current_lower[1] + current_upper[1]) // 2,
            (current_lower[2] + current_upper[2]) // 2
        ]
        
        # HSV范围调节区域
        hsv_ranges_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        hsv_ranges_frame.pack(fill="x", pady=5)
        
        # H通道范围滑块
        h_frame = ctk.CTkFrame(hsv_ranges_frame, fg_color="transparent")
        h_frame.pack(fill="x", pady=2)
        
        h_label = ctk.CTkLabel(h_frame, text="色调(H):")
        h_label.pack(side="left", padx=(0, 10))
        
        # 计算当前H通道的范围
        h_center = self.target_color_hsv[0]
        h_lower_diff = h_center - current_lower[0]
        h_upper_diff = current_upper[0] - h_center
        h_tolerance = max(h_lower_diff, h_upper_diff)
        
        self.h_range_slider = RangeSlider(
            h_frame,
            from_=0,
            to=179,
            home=h_center,
            canvas_bg='#B3B3B3',
            slider_width=180
        )
        self.h_range_slider.pack(side="left", fill="x", padx=(0, 10))
        self.h_range_slider.set_values(
            max(0, h_center - h_tolerance),
            min(179, h_center + h_tolerance),
            h_center
        )
        self.h_range_slider.set_callback(self._on_hsv_range_changed)
        
        # S通道范围滑块
        s_frame = ctk.CTkFrame(hsv_ranges_frame, fg_color="transparent")
        s_frame.pack(fill="x", pady=2)
        
        s_label = ctk.CTkLabel(s_frame, text="饱和(S):")
        s_label.pack(side="left", padx=(0, 10))
        
        # 计算当前S通道的范围
        s_center = self.target_color_hsv[1]
        s_lower_diff = s_center - current_lower[1]
        s_upper_diff = current_upper[1] - s_center
        s_tolerance = max(s_lower_diff, s_upper_diff)
        
        self.s_range_slider = RangeSlider(
            s_frame,
            from_=0,
            to=255,
            home=s_center,
            canvas_bg='#B3B3B3',
            slider_width=180
        )
        self.s_range_slider.pack(side="left", fill="x", padx=(0, 10))
        self.s_range_slider.set_values(
            max(0, s_center - s_tolerance),
            min(255, s_center + s_tolerance),
            s_center
        )
        self.s_range_slider.set_callback(self._on_hsv_range_changed)
        
        # V通道范围滑块
        v_frame = ctk.CTkFrame(hsv_ranges_frame, fg_color="transparent")
        v_frame.pack(fill="x", pady=2)
        
        v_label = ctk.CTkLabel(v_frame, text="亮度(V):")
        v_label.pack(side="left", padx=(0, 10))
        
        # 计算当前V通道的范围
        v_center = self.target_color_hsv[2]
        v_lower_diff = v_center - current_lower[2]
        v_upper_diff = current_upper[2] - v_center
        v_tolerance = max(v_lower_diff, v_upper_diff)
        
        self.v_range_slider = RangeSlider(
            v_frame,
            from_=0,
            to=255,
            home=v_center,
            canvas_bg='#B3B3B3',
            slider_width=180
        )
        self.v_range_slider.pack(side="left", fill="x", padx=(0, 10))
        self.v_range_slider.set_values(
            max(0, v_center - v_tolerance),
            min(255, v_center + v_tolerance),
            v_center
        )
        self.v_range_slider.set_callback(self._on_hsv_range_changed)
        
        # 最小面积
        min_area_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        min_area_frame.pack(fill="x")
        
        min_area_label = ctk.CTkLabel(min_area_frame, text="最小面积:", width=80)
        min_area_label.pack(side="left")
        
        self.min_area_var = tk.IntVar(value=config['min_contour_area'])
        
        # 创建回调函数来更新标签
        def update_min_area_label(value):
            self.min_area_value_label.configure(text=str(int(value)))

        min_area_slider = ctk.CTkSlider(
            min_area_frame, 
            from_=1, 
            to=1000, 
            number_of_steps=100, 
            variable=self.min_area_var, 
            width=200,
            command=update_min_area_label
        )
        min_area_slider.pack(side="left", padx=5, fill="x")

        self.min_area_value_label = ctk.CTkLabel(min_area_frame, text=str(self.min_area_var.get()), width=50)
        self.min_area_value_label.pack(side="left", padx=5)
        
        # 预览和应用按钮区域
        button_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        button_frame.pack(fill="x", pady=10)
        
        # 实时预览按钮
        preview_button = ctk.CTkButton(
            button_frame,
            text="实时预览",
            command=self._preview_color_mask,
            width=100
        )
        preview_button.pack(side="left", padx=(0, 10))
        
        # 应用按钮
        apply_button = ctk.CTkButton(
            button_frame, 
            text="应用配置", 
            command=self._apply_color_contour_config,
            width=100
        )
        apply_button.pack(side="right")
        
        # 初始化显示
        self._update_current_color_preview()

    def _choose_target_color(self):
        """选择目标颜色"""
        # 将当前HSV转换为RGB用于颜色选择器的初始颜色
        initial_rgb = hsv_to_rgb(self.target_color_hsv)
        initial_color = f"#{initial_rgb[0]:02x}{initial_rgb[1]:02x}{initial_rgb[2]:02x}"
        
        # 打开颜色选择对话框
        color_code = colorchooser.askcolor(
            title="选择目标颜色",
            initialcolor=initial_color
        )
        
        if color_code[0]:  # 如果用户选择了颜色
            rgb = color_code[0]
            # 将RGB转换为HSV
            hsv = rgb_to_hsv(rgb)
            self.target_color_hsv = [int(hsv[0]), int(hsv[1]), int(hsv[2])]

            self._update_range_sliders_center()
            self._update_current_color_preview()

    def _capture_color_from_frame(self):
        """从当前帧捕获颜色"""
        if self.current_frame is None:
            messagebox.showwarning("警告", "没有可用的相机帧进行颜色捕获")
            return
            
        capture_dialog = ColorCaptureDialog(
            self.dialog, 
            self.current_frame,
            on_color_selected=self._on_color_captured
        )
        capture_dialog.show()
    
    def _on_color_captured(self, hsv_color):
        """处理捕获的颜色"""
        # 更新目标颜色
        self.target_color_hsv = hsv_color
        
        self._update_range_sliders_center()
        self._update_current_color_preview()

    def _update_range_sliders_center(self):
        """更新range slider的中心值"""
        # 获取当前的容差值
        h_values = self.h_range_slider.get_values()
        s_values = self.s_range_slider.get_values()
        v_values = self.v_range_slider.get_values()
        
        # 计算当前的容差
        h_tolerance = (h_values["upper"] - h_values["lower"]) // 2
        s_tolerance = (s_values["upper"] - s_values["lower"]) // 2
        v_tolerance = (v_values["upper"] - v_values["lower"]) // 2
        
        # 更新H通道
        h_center = self.target_color_hsv[0]
        self.h_range_slider.set_values(
            max(0, h_center - h_tolerance),
            min(179, h_center + h_tolerance),
            h_center
        )
        
        # 更新S通道
        s_center = self.target_color_hsv[1]
        self.s_range_slider.set_values(
            max(0, s_center - s_tolerance),
            min(255, s_center + s_tolerance),
            s_center
        )
        
        # 更新V通道
        v_center = self.target_color_hsv[2]
        self.v_range_slider.set_values(
            max(0, v_center - v_tolerance),
            min(255, v_center + v_tolerance),
            v_center
        )

    def _on_hsv_range_changed(self, lower, upper, home):
        """当HSV范围滑块值改变时的回调"""
        # 更新目标颜色的HSV值（使用home值）
        sender = None
        if hasattr(self, 'h_range_slider') and self.h_range_slider.home_val == home:
            self.target_color_hsv[0] = home
            sender = 'h'
        elif hasattr(self, 's_range_slider') and self.s_range_slider.home_val == home:
            self.target_color_hsv[1] = home
            sender = 's'
        elif hasattr(self, 'v_range_slider') and self.v_range_slider.home_val == home:
            self.target_color_hsv[2] = home
            sender = 'v'
        
        # 更新显示
        self._update_current_color_preview()

    def _update_current_color_preview(self):
        """更新当前颜色预览"""
        # 更新目标颜色预览
        target_rgb = hsv_to_rgb(self.target_color_hsv)
        target_color_hex = f"#{target_rgb[0]:02x}{target_rgb[1]:02x}{target_rgb[2]:02x}"
        self.current_color_preview.configure(fg_color=target_color_hex)

    def _preview_color_mask(self):
        """预览当前颜色设置的掩码效果"""
        if self.current_frame is None:
            messagebox.showwarning("警告", "没有可用的相机帧进行预览")
            return
        
        try:
            # 获取当前选择的检测器
            detector_name = self.detector_name_mapping[self.selected_detector_var.get()]
            detector = self.detection_manager.get_detector(detector_name)
            
            # 获取当前range slider的值
            h_values = self.h_range_slider.get_values()
            s_values = self.s_range_slider.get_values()
            v_values = self.v_range_slider.get_values()
            
            # 临时更新检测器配置以进行预览
            temp_config = detector.config.copy()
            temp_config['color_lower'] = [h_values['lower'], s_values['lower'], v_values['lower']]
            temp_config['color_upper'] = [h_values['upper'], s_values['upper'], v_values['upper']]
            
            # 创建临时检测器实例进行预览
            from noman.camera_controller.detection.color_contour_detector import ColorContourDetector
            temp_detector = ColorContourDetector()
            temp_detector.update_config(temp_config)
            
            # 获取掩码
            mask = temp_detector.get_mask_for_color(self.current_frame)
            
            # 创建预览窗口
            preview_window = ctk.CTkToplevel(self.dialog)
            preview_window.title("颜色掩码预览")
            preview_window.attributes('-topmost', True)
            
            # 设置窗口大小
            frame_height, frame_width = self.current_frame.shape[:2]
            max_display_width = 800
            max_display_height = 600
            
            scale = min(max_display_width / frame_width, max_display_height / frame_height)
            display_width = int(frame_width * scale)
            display_height = int(frame_height * scale)
            
            preview_window.geometry(f"{display_width * 2 + 40}x{display_height + 100}")
            
            # 窗口中心化
            preview_window.update_idletasks()
            x = (preview_window.winfo_screenwidth() - preview_window.winfo_width()) // 2
            y = (preview_window.winfo_screenheight() - preview_window.winfo_height()) // 2
            preview_window.geometry("+{}+{}".format(x, y))
            
            # 创建图像显示区域
            image_frame = ctk.CTkFrame(preview_window, fg_color="transparent")
            image_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            # 原始图像
            original_frame = ctk.CTkFrame(image_frame, fg_color="transparent")
            original_frame.pack(side="left", padx=(0, 10))
            
            original_label = ctk.CTkLabel(original_frame, text="原始图像")
            original_label.pack(pady=5)
            
            # 转换原始图像
            frame_rgb = cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2RGB)
            frame_pil = Image.fromarray(frame_rgb)
            frame_pil = frame_pil.resize((display_width, display_height), Image.LANCZOS)
            frame_tk = ImageTk.PhotoImage(frame_pil)
            
            original_canvas = tk.Label(original_frame, image=frame_tk)
            original_canvas.pack()
            original_canvas.image = frame_tk  # 保持引用
            
            # 掩码图像
            mask_frame = ctk.CTkFrame(image_frame, fg_color="transparent")
            mask_frame.pack(side="right", padx=(10, 0))
            
            mask_label = ctk.CTkLabel(mask_frame, text="颜色掩码")
            mask_label.pack(pady=5)
            
            # 转换掩码图像
            mask_rgb = cv2.cvtColor(mask, cv2.COLOR_GRAY2RGB)
            mask_pil = Image.fromarray(mask_rgb)
            mask_pil = mask_pil.resize((display_width, display_height), Image.LANCZOS)
            mask_tk = ImageTk.PhotoImage(mask_pil)
            
            mask_canvas = tk.Label(mask_frame, image=mask_tk)
            mask_canvas.pack()
            mask_canvas.image = mask_tk  # 保持引用
            
            # 关闭按钮
            close_button = ctk.CTkButton(
                preview_window,
                text="关闭",
                command=preview_window.destroy,
                width=100
            )
            close_button.pack(pady=10)
            
            # 设置模态对话框
            preview_window.transient(self.dialog)
            preview_window.grab_set()
            
        except Exception as e:
            messagebox.showerror("错误", f"预览失败: {str(e)}")

    def _apply_color_contour_config(self):
        """应用颜色轮廓检测器配置"""
        detector_name = self.detector_name_mapping[self.selected_detector_var.get()]
        detector = self.detection_manager.get_detector(detector_name)
        
        # 获取当前range slider的值
        h_values = self.h_range_slider.get_values()
        s_values = self.s_range_slider.get_values()
        v_values = self.v_range_slider.get_values()
        
        # 更新配置
        config = detector.config.copy()
        
        # 更新颜色范围
        config['color_lower'] = [h_values['lower'], s_values['lower'], v_values['lower']]
        config['color_upper'] = [h_values['upper'], s_values['upper'], v_values['upper']]
        
        config['min_contour_area'] = self.min_area_var.get()
        
        # 更新检测器配置
        self.detection_manager.update_detector_config(detector_name, config)

    def _create_frequency_domain_config_panel(self, detector):
        """为频域检测器创建配置面板"""
        config = detector.config
        
        config_frame = ctk.CTkScrollableFrame(self.detector_bottom_frame, fg_color="#B3B3B3")
        config_frame.pack(fill="both", expand=True)
        
        # 模板设置区域 - 与模板匹配检测器类似
        template_top_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        template_top_frame.pack(fill="x", padx=10, pady=10)
        
        template_left_frame = ctk.CTkFrame(template_top_frame, fg_color="transparent")
        template_left_frame.pack(side="left", fill="both", expand=True, padx=(0, 15))

        template_preview_frame = ctk.CTkFrame(template_left_frame, fg_color="transparent", width=120, height=120)
        template_preview_frame.pack(fill="both", expand=True)
        template_preview_frame.pack_propagate(False)
        
        # 用于显示模板图像的标签
        self.fft_template_preview_label = ctk.CTkLabel(template_preview_frame, text="", bg_color="black")
        self.fft_template_preview_label.pack(fill="both", expand=True)
        
        # 右框架：包含按钮和频域特有选项
        template_right_frame = ctk.CTkFrame(template_top_frame, fg_color="transparent")
        template_right_frame.pack(side="right")
        
        # 按钮区域
        template_buttons_frame = ctk.CTkFrame(template_right_frame, fg_color="transparent")
        template_buttons_frame.pack()
        
        load_fft_template_button = ctk.CTkButton(
            template_buttons_frame, 
            text="加载模板", 
            command=self._load_template_image,
            width=120
        )
        load_fft_template_button.pack(padx=10, side="left")
        
        capture_fft_template_button = ctk.CTkButton(
            template_buttons_frame, 
            text="从相机捕获", 
            command=self._capture_template,
            width=120
        )
        capture_fft_template_button.pack(padx=10, side="right")

        visual_image_frame = ctk.CTkFrame(template_right_frame, fg_color="transparent")
        visual_image_frame.pack(fill="x", padx=10, pady=(10,0))

        visualise_type_label = ctk.CTkLabel(visual_image_frame, text="图像:")
        visualise_type_label.pack(side="left", padx=(0, 10))
        
        self.fft_visualise_type_var = tk.StringVar(value=config['visualise_type'])
        visualise_type_menu = ctk.CTkOptionMenu(
            visual_image_frame,
            variable=self.fft_visualise_type_var,
            values=["original", "edge", "correlation"],
            width=120
        )
        visualise_type_menu.pack(side="left")

        visual_orientation_frame = ctk.CTkFrame(template_right_frame, fg_color="transparent")
        visual_orientation_frame.pack(fill="x", padx=10, pady=(10,0))
        
        # 创建两个子框架，使用左右布局
        orient_div_frame = ctk.CTkFrame(visual_orientation_frame, fg_color="transparent")
        orient_div_frame.pack(side="left", fill="x", expand=True)
        
        oriented_box_frame = ctk.CTkFrame(visual_orientation_frame, fg_color="transparent")
        oriented_box_frame.pack(side="right", fill="x", expand=True)
        
        # 将方向选项放在左侧框架
        orientation_divisions_label = ctk.CTkLabel(orient_div_frame, text="方向:")
        orientation_divisions_label.pack(side="left")
        
        default_option = "7-division"
        
        self.fft_orientation_divisions_var = tk.StringVar(value=default_option)
        orientation_divisions_menu = ctk.CTkOptionMenu(
            orient_div_frame,
            variable=self.fft_orientation_divisions_var,
            values=["0-division", "7-division", "9-division", "13-division"],
            width=120
        )
        orientation_divisions_menu.pack(side="left", padx=10)
        
        # 将角度检测控件放在右侧框架
        oriented_boxes_label = ctk.CTkLabel(oriented_box_frame, text="角度检测:")
        oriented_boxes_label.pack(side="left", padx=15)
        
        # 移除开关的文本
        self.fft_oriented_boxes_var = tk.BooleanVar(value=config['show_oriented_boxes'])
        oriented_boxes_switch = ctk.CTkSwitch(
            oriented_box_frame, 
            text="",
            variable=self.fft_oriented_boxes_var,
            onvalue=True,
            offvalue=False
        )
        oriented_boxes_switch.pack(side="left", padx=(0, 10))
        
        # 匹配参数区域
        params_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        params_frame.pack(fill="x", pady=10)
        
        # 匹配阈值滑块
        threshold_frame = ctk.CTkFrame(params_frame, fg_color="transparent")
        threshold_frame.pack(fill="x", pady=5)
        
        threshold_label = ctk.CTkLabel(threshold_frame, text="匹配阈值:", width=100)
        threshold_label.pack(side="left", padx=5)
        
        self.fft_threshold_var = tk.DoubleVar(value=config['match_threshold'])
        
        def update_fft_threshold_label(value):
            self.fft_threshold_value_label.configure(text=f"{value:.2f}")
        
        threshold_slider = ctk.CTkSlider(
            threshold_frame, 
            from_=0.1, 
            to=1.0, 
            number_of_steps=90, 
            variable=self.fft_threshold_var,
            command=update_fft_threshold_label
        )
        threshold_slider.pack(side="left", padx=5, fill="x")
        
        self.fft_threshold_value_label = ctk.CTkLabel(threshold_frame, text=f"{self.fft_threshold_var.get():.2f}", width=50)
        self.fft_threshold_value_label.pack(side="left", padx=5)
        
        # 最小距离滑块
        min_distance_frame = ctk.CTkFrame(params_frame, fg_color="transparent")
        min_distance_frame.pack(fill="x", pady=5)
        
        min_distance_label = ctk.CTkLabel(min_distance_frame, text="最小距离:", width=100)
        min_distance_label.pack(side="left", padx=5)
        
        self.fft_min_distance_var = tk.IntVar(value=config['min_distance'])
        
        def update_fft_min_distance_label(value):
            self.fft_min_distance_value_label.configure(text=str(int(value)))
        
        min_distance_slider = ctk.CTkSlider(
            min_distance_frame, 
            from_=5, 
            to=100, 
            number_of_steps=95, 
            variable=self.fft_min_distance_var,
            command=update_fft_min_distance_label
        )
        min_distance_slider.pack(side="left", padx=5, fill="x")
        
        self.fft_min_distance_value_label = ctk.CTkLabel(min_distance_frame, text=str(self.fft_min_distance_var.get()), width=50)
        self.fft_min_distance_value_label.pack(side="left", padx=5)
        
        # 最大检测数量滑块
        max_detections_frame = ctk.CTkFrame(params_frame, fg_color="transparent")
        max_detections_frame.pack(fill="x", pady=5)
        
        max_detections_label = ctk.CTkLabel(max_detections_frame, text="最大检测数:", width=100)
        max_detections_label.pack(side="left", padx=5)
        
        self.fft_max_detections_var = tk.IntVar(value=config['max_detections'])
        
        def update_fft_max_detections_label(value):
            self.fft_max_detections_value_label.configure(text=str(int(value)))
        
        max_detections_slider = ctk.CTkSlider(
            max_detections_frame, 
            from_=10, 
            to=200, 
            number_of_steps=190, 
            variable=self.fft_max_detections_var,
            command=update_fft_max_detections_label
        )
        max_detections_slider.pack(side="left", padx=5, fill="x")
        
        self.fft_max_detections_value_label = ctk.CTkLabel(max_detections_frame, text=str(self.fft_max_detections_var.get()), width=50)
        self.fft_max_detections_value_label.pack(side="left", padx=5)
        
        # 高级参数区域
        advanced_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        advanced_frame.pack(fill="x", pady=10)
        
        advanced_title = ctk.CTkLabel(advanced_frame, text="高级参数", font=ctk.CTkFont(weight="bold"))
        advanced_title.pack(anchor="w", padx=5, pady=(0, 5))
        
        # 相位相关阈值
        phase_threshold_frame = ctk.CTkFrame(advanced_frame, fg_color="transparent")
        phase_threshold_frame.pack(fill="x", pady=2)
        
        phase_threshold_label = ctk.CTkLabel(phase_threshold_frame, text="相位相关阈值:", width=100)
        phase_threshold_label.pack(side="left", padx=5)
        
        self.fft_phase_threshold_var = tk.DoubleVar(value=config['phase_correlation_threshold'])
        
        def update_fft_phase_threshold_label(value):
            self.fft_phase_threshold_value_label.configure(text=f"{value:.2f}")
        
        phase_threshold_slider = ctk.CTkSlider(
            phase_threshold_frame, 
            from_=0.1, 
            to=1.0, 
            number_of_steps=90, 
            variable=self.fft_phase_threshold_var,
            command=update_fft_phase_threshold_label
        )
        phase_threshold_slider.pack(side="left", padx=5, fill="x")
        
        self.fft_phase_threshold_value_label = ctk.CTkLabel(phase_threshold_frame, text=f"{self.fft_phase_threshold_var.get():.2f}", width=50)
        self.fft_phase_threshold_value_label.pack(side="left", padx=5)
        
        # 应用按钮
        apply_button = ctk.CTkButton(
            config_frame, 
            text="应用配置", 
            command=self._apply_frequency_domain_config,
            width=120
        )
        apply_button.pack(pady=10)

    def _load_template_image(self):
        """加载模板图像文件"""
        file_path = filedialog.askopenfilename(
            title="选择模板图像",
            filetypes=[
                ("图像文件", "*.png *.jpg *.jpeg *.bmp"),
                ("所有文件", "*.*")
            ]
        )
        
        if file_path:
            try:
                # 读取图像
                template_image = cv2.imread(file_path)
                
                # 获取当前选择的检测器
                detector_name = self.detector_name_mapping[self.selected_detector_var.get()]
                detector = self.detection_manager.get_detector(detector_name)
                
                # 设置模板图像
                if detector.set_template_image(template_image):
                    messagebox.showinfo("成功", "模板图像已加载")
                    
                    # 更新预览
                    self._update_template_preview(template_image)
                else:
                    messagebox.showerror("错误", "加载模板图像失败")
            except Exception as e:
                messagebox.showerror("错误", f"加载模板图像出错: {str(e)}")

    def _capture_template(self):
        """从相机捕获模板图像并允许裁剪"""
        if self.current_frame is None:
            messagebox.showerror("错误", "没有可用的相机帧")
            return
        
        try:
            # 复制当前帧
            frame = self.current_frame.copy()
            
            # 创建裁剪窗口
            crop_window = ctk.CTkToplevel(self.dialog)
            crop_window.title("裁剪模板")
            crop_window.attributes('-topmost', True)
            
            # 设置窗口大小和位置
            frame_height, frame_width = frame.shape[:2]
            max_display_width = 640
            max_display_height = 480
            
            scale = min(max_display_width / frame_width, max_display_height / frame_height)
            display_width = int(frame_width * scale)
            display_height = int(frame_height * scale)
            
            crop_window.geometry(f"{display_width + 20}x{display_height + 120}")
            
            # 窗口中心化
            crop_window.update_idletasks()
            x = (crop_window.winfo_screenwidth() - crop_window.winfo_width()) // 2
            y = (crop_window.winfo_screenheight() - crop_window.winfo_height()) // 2
            crop_window.geometry("+{}+{}".format(x, y))
            
            # 转换图像为RGB并调整大小用于显示
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_pil = Image.fromarray(frame_rgb)
            frame_pil = frame_pil.resize((display_width, display_height), Image.LANCZOS)
            
            # 创建画布用于显示图像和选择区域
            canvas = tk.Canvas(crop_window, width=display_width, height=display_height, bg='black')
            canvas.pack(pady=10)
            
            # 显示图像
            frame_tk = ImageTk.PhotoImage(frame_pil)
            canvas.create_image(0, 0, anchor=tk.NW, image=frame_tk)
            canvas.image = frame_tk  # 保持引用
            
            # 用于存储矩形选择坐标
            rect_coords = {'start_x': 0, 'start_y': 0, 'end_x': 0, 'end_y': 0, 'drawn': None}
            
            instruction_label = ctk.CTkLabel(crop_window, text="拖动鼠标选择模板区域")
            instruction_label.pack(pady=5)
            
            # 鼠标事件处理函数
            def on_mouse_down(event):
                rect_coords['start_x'] = event.x
                rect_coords['start_y'] = event.y
                
                # 如果已有矩形，删除它
                if rect_coords['drawn']:
                    canvas.delete(rect_coords['drawn'])
                
                # 创建新矩形
                rect_coords['drawn'] = canvas.create_rectangle(
                    rect_coords['start_x'], rect_coords['start_y'],
                    rect_coords['start_x'], rect_coords['start_y'],
                    outline='green', width=2
                )
            
            def on_mouse_move(event):
                if rect_coords['drawn']:
                    # 更新矩形结束坐标
                    rect_coords['end_x'] = event.x
                    rect_coords['end_y'] = event.y
                    
                    # 更新矩形位置
                    canvas.coords(
                        rect_coords['drawn'],
                        rect_coords['start_x'], rect_coords['start_y'],
                        rect_coords['end_x'], rect_coords['end_y']
                    )
            
            def on_mouse_up(event):
                rect_coords['end_x'] = event.x
                rect_coords['end_y'] = event.y
                
                # 确保矩形坐标合理（起点在左上角，终点在右下角）
                start_x = min(rect_coords['start_x'], rect_coords['end_x'])
                start_y = min(rect_coords['start_y'], rect_coords['end_y'])
                end_x = max(rect_coords['start_x'], rect_coords['end_x'])
                end_y = max(rect_coords['start_y'], rect_coords['end_y'])
                
                # 更新矩形位置 - 确保图形对象存在
                if rect_coords['drawn']:
                    canvas.coords(rect_coords['drawn'], start_x, start_y, end_x, end_y)
                
                # 更新坐标
                rect_coords['start_x'] = start_x
                rect_coords['start_y'] = start_y
                rect_coords['end_x'] = end_x
                rect_coords['end_y'] = end_y
            
            # 绑定鼠标事件
            canvas.bind("<ButtonPress-1>", on_mouse_down)
            canvas.bind("<B1-Motion>", on_mouse_move)
            canvas.bind("<ButtonRelease-1>", on_mouse_up)
            
            # 裁剪和取消按钮
            button_frame = ctk.CTkFrame(crop_window, fg_color="transparent")
            button_frame.pack(fill="x", pady=10)
            
            def apply_crop():
                if rect_coords['drawn'] and rect_coords['end_x'] > rect_coords['start_x'] and rect_coords['end_y'] > rect_coords['start_y']:
                    # 计算原始图像中的裁剪坐标
                    original_start_x = int(rect_coords['start_x'] / scale)
                    original_start_y = int(rect_coords['start_y'] / scale)
                    original_end_x = int(rect_coords['end_x'] / scale)
                    original_end_y = int(rect_coords['end_y'] / scale)
                    
                    # 确保坐标在原始图像范围内
                    original_start_x = max(0, min(original_start_x, frame_width - 1))
                    original_start_y = max(0, min(original_start_y, frame_height - 1))
                    original_end_x = max(0, min(original_end_x, frame_width))
                    original_end_y = max(0, min(original_end_y, frame_height))
                    
                    # 裁剪图像
                    cropped_image = frame[original_start_y:original_end_y, original_start_x:original_end_x]
                    
                    if cropped_image.size > 0:
                        # 获取当前选择的检测器
                        detector_name = self.detector_name_mapping[self.selected_detector_var.get()]
                        detector = self.detection_manager.get_detector(detector_name)
                        
                        # 设置模板图像
                        if detector.set_template_image(cropped_image):
                            # 更新模板预览
                            self._update_template_preview(cropped_image)
                        else:
                            messagebox.showerror("错误", "设置模板图像失败")
                    else:
                        messagebox.showerror("错误", "裁剪区域无效")
                else:
                    messagebox.showerror("错误", "请先选择一个有效的裁剪区域")
                
                # 关闭窗口
                crop_window.destroy()
            
            def cancel_crop():
                crop_window.destroy()
            
            apply_button = ctk.CTkButton(button_frame, text="应用裁剪", command=apply_crop)
            apply_button.pack(side="left", padx=10, expand=True)
            
            cancel_button = ctk.CTkButton(button_frame, text="取消", command=cancel_crop)
            cancel_button.pack(side="right", padx=10, expand=True)
            
            # 设置模态对话框
            crop_window.transient(self.dialog)
            crop_window.grab_set()
            
        except Exception as e:
            messagebox.showerror("错误", f"捕获模板图像出错: {str(e)}")

    def _update_template_preview(self, template_image):
        """更新模板图像预览
        
        Args:
            template_image: 模板图像
        """
        if template_image is None:
            return
            
        # 确定要更新哪个预览标签
        preview_label = None
        if hasattr(self, 'template_preview_label'):
            preview_label = self.template_preview_label
        elif hasattr(self, 'fft_template_preview_label'):
            preview_label = self.fft_template_preview_label
        
        if preview_label is None:
            return
            
        # 转换BGR为RGB
        if len(template_image.shape) == 3:
            rgb_image = cv2.cvtColor(template_image, cv2.COLOR_BGR2RGB)
        else:
            # 如果是灰度图，转换为RGB
            rgb_image = cv2.cvtColor(template_image, cv2.COLOR_GRAY2RGB)
            
        pil_image = Image.fromarray(rgb_image)
        
        # 获取预览标签的大小
        label_width = preview_label.winfo_width()
        label_height = preview_label.winfo_height()
        
        # 如果标签尚未渲染，使用默认大小
        if label_width <= 1 or label_height <= 1:
            label_width = 150
            label_height = 150
        
        # 保持纵横比调整图像大小
        w, h = pil_image.size
        if w > h:
            new_w = label_width
            new_h = int(h * label_width / w)
        else:
            new_h = label_height
            new_w = int(w * label_height / h)
        
        # 调整大小
        pil_image = pil_image.resize((new_w, new_h), Image.LANCZOS)
        
        # 创建CTkImage
        ctk_image = ctk.CTkImage(pil_image, size=(new_w, new_h))
        
        # 更新预览标签
        preview_label.configure(image=ctk_image, text="")
        preview_label.image = ctk_image  # 保持引用，防止被垃圾回收

    def _draw_camera_center_cross(self, frame):
        """绘制相机中心十字标记"""
        if frame is None:
            return frame
            
        # 创建帧的副本，避免修改原始帧
        frame_copy = frame.copy()
        
        # 获取图像尺寸
        height, width = frame_copy.shape[:2]
        
        # 计算中心点
        center_x = width // 2
        center_y = height // 2
        
        # 设置十字标记的参数
        cross_size = 8  # 十字的半径（像素）
        line_thickness = 1  # 线条粗细
        color = (0, 255, 0)  # 绿色 (BGR格式)
        
        # 绘制水平线
        cv2.line(frame_copy, 
                (center_x - cross_size, center_y), 
                (center_x + cross_size, center_y), 
                color, line_thickness)
        
        # 绘制垂直线
        cv2.line(frame_copy, 
                (center_x, center_y - cross_size), 
                (center_x, center_y + cross_size), 
                color, line_thickness)
        
        # 绘制中心点
        cv2.circle(frame_copy, (center_x, center_y), 2, color, -1)
        
        return frame_copy

    def toggle_camera_center(self):
        """切换相机中心十字标记的显示状态"""
        self.show_camera_center_cross = not self.show_camera_center_cross
        
        return self.show_camera_center_cross

    def on_capture_camera_center(self):
        """捕获相机中心坐标"""
        # 检查是否有手眼标定结果
        if self.calibration_result is None:
            self.show_error("请先完成手眼标定")
            return
            
        # 切换相机中心十字标记的显示状态
        cross_enabled = self.toggle_camera_center()
        
        # 立即更新坐标显示
        self.update_camera_center_coordinates()
        
        # 更新按钮文本以反映当前状态
        current_text = "隐藏投影中心坐标" if cross_enabled else "显示投影中心坐标"
        self.capture_center_button.configure(text=current_text)

    def on_validate_robot_pose(self):
        """验证机器人位姿 - 将机器人移动到投影的3D世界位置"""
        # 检查是否有手眼标定结果
        if self.calibration_result is None:
            self.show_error("请先完成手眼标定")
            return
            
        try:
            # 获取当前显示的世界坐标
            x_text = self.x_coord_value.cget("text")
            y_text = self.y_coord_value.cget("text")
            z_text = self.z_coord_value.cget("text")
            
            # 检查坐标是否有效
            if "---" in x_text or "---" in y_text or "---" in z_text:
                self.show_error("请先显示投影中心坐标")
                return
            
            # 解析坐标值（移除"mm"单位）
            x_mm = float(x_text.replace(" mm", ""))
            y_mm = float(y_text.replace(" mm", ""))
            z_mm = float(z_text.replace(" mm", ""))
            
            # 转换为米
            target_position = np.array([x_mm/1000, y_mm/1000, z_mm/1000])
            
            # 更新kinematics_frame的目标位置
            self.kinematics_frame.target_position = target_position
            
            # 更新UI中的位置输入框
            for i, entry in enumerate(self.kinematics_frame.target_entries):
                entry.delete(0, tk.END)
                entry.insert(0, f"{target_position[i]:.6f}")
            
            # 使用标准的on_target_change方法来处理目标位置变化
            self.kinematics_frame.on_target_change()
            self.kinematics_frame.send_to_robot()
            
        except ValueError as e:
            self.show_error(f"坐标解析失败: {str(e)}")

    def _apply_frequency_domain_config(self):
        """应用频域检测器配置"""
        detector_name = self.detector_name_mapping[self.selected_detector_var.get()]
        detector = self.detection_manager.get_detector(detector_name)
        
        # 更新配置
        config = detector.config.copy()
        
        # 基本参数
        config['match_threshold'] = self.fft_threshold_var.get()
        config['min_distance'] = self.fft_min_distance_var.get()
        config['max_detections'] = self.fft_max_detections_var.get()
        
        # 频域特有参数
        config['show_oriented_boxes'] = self.fft_oriented_boxes_var.get()
        config['visualise_type'] = self.fft_visualise_type_var.get()
        
        # 处理方向分割选项
        orientation_options = {
            "0-division": [0],
            "7-division": [-90, -60, -30, 0, 30, 60, 90],
            "9-division": [-90, -65, -40, -25, 0, 25, 40, 65, 90],
            "13-division": [-90, -75, -60, -45, -30, -15, 0, 15, 30, 45, 60, 75, 90]
        }
        
        selected_division = self.fft_orientation_divisions_var.get()
        if selected_division in orientation_options:
            config['orientations'] = orientation_options[selected_division]
        
        # 高级参数
        config['phase_correlation_threshold'] = self.fft_phase_threshold_var.get()
        
        # 更新检测器配置
        self.detection_manager.update_detector_config(detector_name, config)

    def update_texts(self):
        """更新所有文本内容"""
        self.calibration_button.configure(text=Config.current_lang["calibration"])
        self.detection_button.configure(text=Config.current_lang["detection"])
        self.add_camera_button.configure(text=Config.current_lang["add_camera"])
        self.charuco_button.configure(text=Config.current_lang["calibration_board"])
        self.pose_button.configure(text=Config.current_lang["pose_sampling"])
        self.result_button.configure(text=Config.current_lang["result"])
        self.localisation_button.configure(text=Config.current_lang["localisation"])
        self.detector_options_button.configure(text=Config.current_lang["detector"])
        self.interaction_button.configure(text=Config.current_lang["interaction"])   

        self.save_board_button.configure(text=Config.current_lang["save"])
        self.save_button.configure(text=Config.current_lang["save"])
        self.load_button.configure(text=Config.current_lang["load"])
