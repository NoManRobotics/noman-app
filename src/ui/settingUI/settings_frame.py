import os
from PIL import Image
import customtkinter as ctk

from utils.config import Config
from utils.resource_loader import ResourceLoader
from utils.tooltip import ToolTip
from utils.range_slider import RangeSlider
from noman.profile_manager import ProfileManager
from noman.activation_core import ActivationManager, HardwareInfo
from protocol.serial_protocol import SerialProtocol
from protocol.can_protocol import CanProtocol

# Settings Frame
class SettingsFrame(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master)
        self.master = master
        self.app = app
        self.current_language = "English"  # Add current_language attribute
        
        # 脉宽范围常量 - 便于调整
        self.MIN_PULSE_WIDTH = 700
        self.MAX_PULSE_WIDTH = 2300
        self.PULSE_RANGE_MAX = 4096  # RangeSlider的最大范围值
        self.BUTTON_STEP = 10  # RangeSlider按钮每次点击的步长
        
        # 初始化协议类和变量
        self.current_profile = ProfileManager.current_profile
        self.protocol_class = SerialProtocol if self.current_profile["robot_type"] == "PWM/I2C" else CanProtocol
        
        # 初始化设置变量
        self.calibration_offsets = []  # 2D array: [[min_offset, max_offset], ...] for all main joints
        self.speed_options = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170, 180, 190]
        
        # UI配置选项
        self.position_steps_options = [0.001, 0.003, 0.005, 0.01, 0.02, 0.05]
        self.orientation_steps_options = [0.5, 1, 2, 3, 5]
        self.radius_options = [0.0003, 0.0006, 0.0009, 0.001, 0.002, 0.005]
        self.axis_length_options = [0.01, 0.02, 0.03, 0.04, 0.05]
        
        # 轨迹优化器配置选项
        self.dt_options = [0.01, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0] #s
        self.acc_options = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100] #percentage
        self.jerk_options = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100] #percentage
        self.trajectory_method_options = ["linear", "trapezoidal", "scurve", "polynomial"]
        
        # 插值配置选项
        self.interpolation_method_options = ["linear", "bspline", "blend"]
        
        # 协议配置选项
        self.baud_rate_options = [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]
        self.can_bitrate_options = [125000, 250000, 500000, 1000000]
        
        # 激活管理器
        self.activation_manager = ActivationManager()
        
        # 界面控件
        self.range_sliders = []
        self.current_pulses = []
        self.joint_speed_menus = []
        self.joint_acc_menus = []
        self.joint_jerk_menus = []
        
        # 防抖机制
        self.calibration_timers = {}  # 为每个关节维护单独的定时器
        
        # UI配置控件
        self.ui_controls = {}
        self.trajectory_controls = {}
        self.interpolation_controls = {}
        self.protocol_controls = {}
        
        # 加载图标
        self.load_icons()
        
        # 同步协议类与Config值
        SerialProtocol.SERIAL_BAUDRATE = Config.serial_baudrate
        CanProtocol.bitrate = Config.can_bitrate
        
        # Configure main grid layout similar to HelpFrame
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)  # Main tab area
        self.grid_rowconfigure(1, weight=0)  # Footer area for messages and save button
        
        self.setup_footer_frame()
        self.setup_settings_frame()
        self.load_calibration()

    def load_icons(self):
        """加载图标"""
        question_path = ResourceLoader.get_asset_path(os.path.join("icons", "question.png"))
        reset_path = ResourceLoader.get_asset_path(os.path.join("icons", "reset.png"))

        self.question_icon_black = ctk.CTkImage(Image.open(question_path).convert("RGBA"), size=(15, 15))
        self.reset_icon = ctk.CTkImage(Image.open(reset_path).convert("RGBA"), size=(16, 16))

    def setup_settings_frame(self):
        """Setup the main settings frame with tabview"""
        # Main settings frame
        self.settings_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.settings_frame.grid(row=0, column=0, padx=0, pady=(21,10), sticky="nsew")
        self.settings_frame.grid_columnconfigure(0, weight=1)
        self.settings_frame.grid_rowconfigure(0, weight=1)

        # Create tabview within the settings frame
        self.tabview = ctk.CTkTabview(self.settings_frame, fg_color="transparent", 
                                     command=self.on_tab_change)
        self.tabview.grid(row=0, column=0, padx=10, sticky="nsew")
        
        # Add tabs
        self.tab_ui = self.tabview.add(Config.current_lang["ui_settings"])
        self.tab_robot = self.tabview.add(Config.current_lang["robot_settings"]) 
        self.tab_advanced = self.tabview.add(Config.current_lang["advanced_settings"])
        self.tab_license = self.tabview.add(Config.current_lang["license"])
        
        # Set default tab
        self.tabview.set(Config.current_lang["ui_settings"])
        
        # Setup tab contents
        self.setup_ui_tab()
        self.setup_robot_tab()
        self.setup_advanced_tab()
        self.setup_license_tab()

    def on_tab_change(self):
        """处理标签页切换事件"""
            
        current_tab = self.tabview.get()
        
        # 如果是License标签页，隐藏保存按钮
        if current_tab == "License":
            self.save_button_frame.grid_forget()
        else:
            # 其他标签页显示保存按钮
            self.save_button_frame.grid(row=0, column=1, sticky="e")
    
    def setup_footer_frame(self):
        """设置底部框架，包含消息和保存按钮"""
        # 底部主框架
        self.footer_frame = ctk.CTkFrame(self, height=40, fg_color="transparent")
        self.footer_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=20)
        self.footer_frame.grid_columnconfigure(0, weight=1)  # 消息区域可扩展
        self.footer_frame.grid_columnconfigure(1, weight=0)  # 保存按钮区域固定
        
        # 左侧：消息显示框架
        self.message_frame = ctk.CTkFrame(self.footer_frame, fg_color="transparent")
        self.message_frame.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        
        # 消息标签
        self.message_label = ctk.CTkLabel(self.message_frame, text=Config.current_lang["ready"], 
                                         text_color="gray", font=ctk.CTkFont(size=11))
        self.message_label.pack(side="left", padx=5)
        
        # 右侧：保存按钮框架
        self.save_button_frame = ctk.CTkFrame(self.footer_frame, fg_color="transparent")
        self.save_button_frame.grid(row=0, column=1, sticky="e")
        
        # 统一保存按钮
        self.unified_save_button = ctk.CTkButton(self.save_button_frame, text=Config.current_lang["save"], 
                                               command=self.save_current_tab, width=80)
        self.unified_save_button.pack(side="right")
        
        # 消息自动清除的定时器ID
        self.message_timer_id = None
    
    def setup_ui_tab(self):
        """Setup UI settings tab content"""
        ui_frame = self.tab_ui
        
        # Create normal frame for UI settings
        self.ui_content_frame = ctk.CTkFrame(ui_frame, fg_color="transparent")
        self.ui_content_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Language selection section
        self.language_section = ctk.CTkFrame(self.ui_content_frame, fg_color="transparent")
        self.language_section.pack(fill="x", pady=(0, 20))
        
        self.language_title = ctk.CTkLabel(self.language_section, text=f"-- {Config.current_lang['language_settings']} --", 
                                    font=ctk.CTkFont(size=14, weight="bold"))
        self.language_title.pack(anchor="w", padx=15, pady=(15, 10))
        
        self.language_content_frame = ctk.CTkFrame(self.language_section, fg_color="transparent")
        self.language_content_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        # Language label and dropdown on the same row
        language_row_frame = ctk.CTkFrame(self.language_content_frame, fg_color="transparent")
        language_row_frame.pack(fill="x", pady=(0, 5))
        
        self.language_label = ctk.CTkLabel(language_row_frame, text=Config.current_lang["interface_language"], 
                                    font=ctk.CTkFont(size=12))
        self.language_label.pack(side="left", padx=(0, 10))
        
        # Language dropdown
        self.language_var = ctk.StringVar(value=self.current_language)
        self.language_dropdown = ctk.CTkOptionMenu(language_row_frame, 
                                                 variable=self.language_var,
                                                 values=["English", "中文", "日本語"], 
                                                 command=self.set_language,
                                                 width=150)
        self.language_dropdown.pack(side="left")
        
        # UI参数设置区域
        self.ui_params_section = ctk.CTkFrame(self.ui_content_frame, fg_color="transparent")
        self.ui_params_section.pack(fill="x", pady=(0, 20))
        
        # UI参数标题行 - 包含标题和帮助按钮
        ui_params_title_frame = ctk.CTkFrame(self.ui_params_section, fg_color="transparent")
        ui_params_title_frame.pack(fill="x", padx=15, pady=(15, 10))
        
        self.ui_params_title = ctk.CTkLabel(ui_params_title_frame, text=f"-- {Config.current_lang['display_parameters']} --", 
                                     font=ctk.CTkFont(size=14, weight="bold"))
        self.ui_params_title.pack(side="left", anchor="w")
        
        self.question_button_ui_params = ctk.CTkButton(ui_params_title_frame, text="", 
            image=self.question_icon_black, width=20, height=20, fg_color="transparent", 
            hover_color="#EBEBEB")
        self.question_button_ui_params.pack(side="left", padx=(10, 0))
        
        ToolTip(self.question_button_ui_params, 
            Config.current_lang["tooltip_display_params"])

        self.reset_ui_params_button = ctk.CTkButton(ui_params_title_frame, 
                                                    text="", 
                                                    image=self.reset_icon, 
                                                    command=self.reset_ui_settings,
                                                    fg_color="transparent",
                                                    hover_color="#41d054",
                                                    width=30, 
                                                    height=30)
        self.reset_ui_params_button.pack(side="left", padx=(50, 0))
        
        # UI参数内容框架
        self.ui_params_content_frame = ctk.CTkFrame(self.ui_params_section, fg_color="transparent")
        self.ui_params_content_frame.pack(fill="x", padx=15, pady=(0, 15))

        # 创建UI配置选项
        ui_params = [
            (Config.current_lang["position_steps_kinematics"], "position_steps", self.position_steps_options, Config.position_steps, "mm"),
            (Config.current_lang["orientation_steps_kinematics"], "orientation_steps", self.orientation_steps_options, Config.orientation_steps, Config.current_lang["degrees"]),
            (Config.current_lang["preview_point_radius"], "rcl_preview_point_radius", self.radius_options, Config.rcl_preview_point_radius, "m"),
            (Config.current_lang["preview_axis_length"], "rcl_preview_axis_length", self.axis_length_options, Config.rcl_preview_axis_length, "m")
        ]
        
        for param_name, param_key, options, current_value, unit in ui_params:
            frame, left_btn, value_label, right_btn, param_label, desc_label = self.create_option_selector(
                self.ui_params_content_frame, param_name=param_name, current_value=current_value, unit=unit
            )
            
            # 存储控件引用
            self.ui_controls[param_key] = {
                'frame': frame,
                'left_button': left_btn,
                'value_label': value_label,
                'right_button': right_btn,
                'param_label': param_label,
                'desc_label': desc_label,
                'options': options,
                'current_index': options.index(current_value) if current_value in options else 0
            }
            
            # 绑定按钮事件
            left_btn.configure(command=lambda k=param_key: self.change_ui_value(k, -1))
            right_btn.configure(command=lambda k=param_key: self.change_ui_value(k, 1))

    
    def setup_robot_tab(self):
        """Setup Robot settings tab content"""
        robot_frame = self.tab_robot

        self.robot_content_frame = ctk.CTkFrame(robot_frame, fg_color="transparent")
        self.robot_content_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 校准设置区域
        self.calibration_section = ctk.CTkFrame(self.robot_content_frame, fg_color="transparent")
        self.calibration_section.pack(fill="x", pady=(0, 20))
        
        cal_title_frame = ctk.CTkFrame(self.calibration_section, fg_color="transparent")
        cal_title_frame.pack(fill="x", padx=15, pady=(15, 10))
        
        self.calibration_title = ctk.CTkLabel(cal_title_frame, text=f"-- {Config.current_lang['calibration_settings']} --", font=ctk.CTkFont(size=14, weight="bold"))
        self.calibration_title.pack(side="left", anchor="w")
        
        self.question_button_calibration = ctk.CTkButton(cal_title_frame, text="", 
            image=self.question_icon_black, width=20, height=20, fg_color="transparent", 
            hover_color="#EBEBEB")
        self.question_button_calibration.pack(side="left", padx=(10, 0))
        
        ToolTip(self.question_button_calibration, Config.current_lang["tooltip_calibration"])

        self.reset_calibration_button = ctk.CTkButton(cal_title_frame, 
                                                      text="",
                                                      image=self.reset_icon, 
                                                      command=self.reset_calibration, 
                                                      width=30, 
                                                      height=30,
                                                      fg_color="transparent",
                                                      hover_color="#41d054")
        self.reset_calibration_button.pack(side="left", padx=(50, 0))
        
        # 校准内容框架
        self.calibration_content_frame = ctk.CTkFrame(self.calibration_section, fg_color="transparent")
        self.calibration_content_frame.pack(fill="x", padx=15, pady=(0, 15))

        # 根据需要校准的关节数量动态创建RangeSlider
        num_calibratable = len(ProfileManager.get_main_joints())
        
        # 在校准内容框架中添加RangeSlider控件
        for i in range(num_calibratable):
            # 为每个关节创建一个水平框架
            joint_frame = ctk.CTkFrame(self.calibration_content_frame, fg_color="transparent")
            joint_frame.pack(fill="x", padx=0, pady=5)
            
            # 关节标签（左侧）
            label = ctk.CTkLabel(joint_frame, text=f"{Config.current_lang['joint']}{i+1}", width=60)
            label.pack(side="left", padx=(0, 10))

            range_slider = RangeSlider(
                joint_frame,
                from_=0,
                to=self.PULSE_RANGE_MAX,
                slider_width=290,
                home=int((self.MIN_PULSE_WIDTH + self.MAX_PULSE_WIDTH) / 2),
                circle_size=4,
                button_step=self.BUTTON_STEP,
                fg_color="transparent"
            )
            range_slider.pack(side="left", padx=(0, 10))
            
            # 初始化为默认脉宽范围
            range_slider.set_values(self.MIN_PULSE_WIDTH, self.MAX_PULSE_WIDTH, int((self.MIN_PULSE_WIDTH + self.MAX_PULSE_WIDTH) / 2))
            
            # 设置回调
            range_slider.set_callback(lambda lower, upper, home, joint_id=i: self.on_range_slider_change(joint_id, lower, upper, home))
            
            self.range_sliders.append(range_slider)
            self.current_pulses.append(int((self.MIN_PULSE_WIDTH + self.MAX_PULSE_WIDTH) / 2))  # 默认当前脉冲

            # 添加获取当前脉冲按钮
            pulse_button = ctk.CTkButton(joint_frame, text="Get Current Pulse", width=120,
                command=lambda joint_id=i: self.get_current_pulse(joint_id))
            pulse_button.pack(side="right")

        # 协议设置区域
        self.protocol_section = ctk.CTkFrame(self.robot_content_frame, fg_color="transparent")
        self.protocol_section.pack(fill="x", pady=(0, 20))
        
        protocol_title_frame = ctk.CTkFrame(self.protocol_section, fg_color="transparent")
        protocol_title_frame.pack(fill="x", padx=15, pady=(15, 10))
        
        self.protocol_title = ctk.CTkLabel(protocol_title_frame, text=f"-- {Config.current_lang['protocol_settings']} --", font=ctk.CTkFont(size=14, weight="bold"))
        self.protocol_title.pack(side="left", anchor="w")
        
        self.question_button_protocol = ctk.CTkButton(protocol_title_frame, text="", 
            image=self.question_icon_black, width=20, height=20, fg_color="transparent", 
            hover_color="#EBEBEB")
        self.question_button_protocol.pack(side="left", padx=(10, 0))
        
        ToolTip(self.question_button_protocol, Config.current_lang["tooltip_protocol"])

        self.reset_protocol_button = ctk.CTkButton(protocol_title_frame, 
                                                     text="",
                                                     image=self.reset_icon, 
                                                     command=self.reset_protocol_settings, 
                                                     width=30, 
                                                     height=30,
                                                     fg_color="transparent",
                                                     hover_color="#41d054")
        self.reset_protocol_button.pack(side="left", padx=(50, 0))
        
        # 协议内容框架
        self.protocol_content_frame = ctk.CTkFrame(self.protocol_section, fg_color="transparent")
        self.protocol_content_frame.pack(fill="x", padx=15, pady=(0, 15))

        # Serial Protocol 波特率设置
        serial_frame = ctk.CTkFrame(self.protocol_content_frame, fg_color="transparent")
        serial_frame.pack(fill="x", padx=0, pady=8)
        
        serial_label = ctk.CTkLabel(serial_frame, text=Config.current_lang["serial_baud_rate"], width=120, anchor='w')
        serial_label.pack(side="left", padx=(0, 10))
        
        self.serial_baud_var = ctk.StringVar(value=str(Config.serial_baudrate))
        self.serial_baud_menu = ctk.CTkOptionMenu(
            serial_frame,
            variable=self.serial_baud_var,
            values=[str(rate) for rate in self.baud_rate_options],
            command=self.on_serial_baud_change,
            width=150
        )
        self.serial_baud_menu.pack(side="left", padx=(0, 10))
        
        baud_unit_label = ctk.CTkLabel(serial_frame, text="bps", text_color="gray", 
                                      font=("Arial", 10))
        baud_unit_label.pack(side="left", padx=(10, 0))

        # CAN Protocol 比特率设置
        can_frame = ctk.CTkFrame(self.protocol_content_frame, fg_color="transparent")
        can_frame.pack(fill="x", padx=0, pady=8)
        
        can_label = ctk.CTkLabel(can_frame, text=Config.current_lang["can_bitrate"], width=120, anchor='w')
        can_label.pack(side="left", padx=(0, 10))
        
        self.can_bitrate_var = ctk.StringVar(value=str(Config.can_bitrate))
        self.can_bitrate_menu = ctk.CTkOptionMenu(
            can_frame,
            variable=self.can_bitrate_var,
            values=[str(rate) for rate in self.can_bitrate_options],
            command=self.on_can_bitrate_change,
            width=150
        )
        self.can_bitrate_menu.pack(side="left", padx=(0, 10))
        
        bitrate_unit_label = ctk.CTkLabel(can_frame, text="bps", text_color="gray", 
                                         font=("Arial", 10))
        bitrate_unit_label.pack(side="left", padx=(10, 0))

        # 存储协议控件引用
        self.protocol_controls = {
            'serial_baud_menu': self.serial_baud_menu,
            'can_bitrate_menu': self.can_bitrate_menu,
            'serial_baud_var': self.serial_baud_var,
            'can_bitrate_var': self.can_bitrate_var
        }

    def setup_advanced_tab(self):
        """Setup Advanced settings tab content"""
        advanced_frame = self.tab_advanced
        
        self.advanced_content_frame = ctk.CTkFrame(advanced_frame, fg_color="transparent")
        self.advanced_content_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        
        
        # 轨迹优化器设置区域
        self.trajectory_section = ctk.CTkFrame(self.advanced_content_frame, fg_color="transparent")
        self.trajectory_section.pack(fill="x", pady=(0, 20))
        
        # 轨迹优化器标题行 - 包含标题和帮助按钮
        trajectory_title_frame = ctk.CTkFrame(self.trajectory_section, fg_color="transparent")
        trajectory_title_frame.pack(fill="x", padx=15, pady=(15, 10))
        
        self.trajectory_title = ctk.CTkLabel(trajectory_title_frame, text=f"-- {Config.current_lang['trajectory_optimiser']} --", font=ctk.CTkFont(size=14, weight="bold"))
        self.trajectory_title.pack(side="left", anchor="w")
        
        self.question_button_trajectory = ctk.CTkButton(trajectory_title_frame, text="", 
            image=self.question_icon_black, width=20, height=20, fg_color="transparent", 
            hover_color="#EBEBEB")
        self.question_button_trajectory.pack(side="left", padx=(10, 0))
        
        ToolTip(self.question_button_trajectory, Config.current_lang["tooltip_trajectory"])

        self.reset_trajectory_button = ctk.CTkButton(trajectory_title_frame, 
                                                     text="",
                                                     image=self.reset_icon, 
                                                     command=self.reset_trajectory_settings, 
                                                     width=30, 
                                                     height=30,
                                                     fg_color="transparent",
                                                     hover_color="#41d054")
        self.reset_trajectory_button.pack(side="left", padx=(50, 0))
        
        # 轨迹优化器内容框架
        self.trajectory_content_frame = ctk.CTkFrame(self.trajectory_section, fg_color="transparent")
        self.trajectory_content_frame.pack(fill="x", padx=15, pady=(0, 15))

        # 轨迹方法下拉菜单
        trajectory_method_frame = ctk.CTkFrame(self.trajectory_content_frame, fg_color="transparent")
        trajectory_method_frame.pack(fill="x", padx=0, pady=8)
        
        trajectory_method_label = ctk.CTkLabel(trajectory_method_frame, text=Config.current_lang["trajectory_method"], width=120, anchor='w')
        trajectory_method_label.pack(side="left", padx=(0, 10))
        
        self.trajectory_method_var = ctk.StringVar(value=Config.trajectory_method)
        self.trajectory_method_menu = ctk.CTkOptionMenu(
            trajectory_method_frame,
            variable=self.trajectory_method_var,
            values=self.trajectory_method_options,
            command=self.on_trajectory_method_change,
            width=150
        )
        self.trajectory_method_menu.pack(side="left", padx=(0, 10))
        
        # 存储轨迹方法控件引用
        self.trajectory_controls['trajectory_method'] = {
            'frame': trajectory_method_frame,
            'menu': self.trajectory_method_menu,
            'label': trajectory_method_label,
            'var': self.trajectory_method_var
        }

        # 时间步长设置
        dt_frame, dt_left_btn, dt_value_label, dt_right_btn, dt_param_label, dt_desc_label = self.create_option_selector(
            self.trajectory_content_frame, param_name=Config.current_lang["time_step_dt"], current_value=Config.dt, unit="s"
        )
        
        self.trajectory_controls['dt'] = {
            'frame': dt_frame,
            'left_button': dt_left_btn,
            'value_label': dt_value_label,
            'right_button': dt_right_btn,
            'param_label': dt_param_label,
            'desc_label': dt_desc_label,
            'options': self.dt_options,
            'current_index': self.dt_options.index(Config.dt) if Config.dt in self.dt_options else 0
        }
        
        dt_left_btn.configure(command=lambda: self.change_trajectory_value('dt', 'dt', -1))
        dt_right_btn.configure(command=lambda: self.change_trajectory_value('dt', 'dt', 1))

        # 每关节参数设置区域
        self.joint_params_section = ctk.CTkFrame(self.trajectory_content_frame, fg_color="transparent")
        self.joint_params_section.pack(fill="x", pady=(10, 0))
        
        # 表头
        header_frame = ctk.CTkFrame(self.joint_params_section, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 5))
        
        self.joint_header_label = ctk.CTkLabel(header_frame, text="Joint", width=60, anchor='w')
        self.joint_header_label.pack(side="left", padx=(0, 10))
        
        self.speed_header_label = ctk.CTkLabel(header_frame, text=Config.current_lang["speed"], width=120, anchor='center')
        self.speed_header_label.pack(side="left", padx=(0, 10))
        
        self.acc_header_label = ctk.CTkLabel(header_frame, text=Config.current_lang["acceleration"], width=120, anchor='center')
        self.acc_header_label.pack(side="left", padx=(0, 10))
        
        self.jerk_header_label = ctk.CTkLabel(header_frame, text=Config.current_lang["jerk"], width=120, anchor='center')
        self.jerk_header_label.pack(side="left", padx=(0, 10))

        # 初始化关节参数菜单列表
        self.joint_speed_menus = []
        self.joint_acc_menus = []
        self.joint_jerk_menus = []
        
        # 根据关节数量创建参数设置
        num_joints = len(ProfileManager.get_main_joints())
        
        # 初始化Config中的关节参数
        Config.init_joint_params(num_joints)
        
        # 为每个关节创建参数设置行
        for i in range(num_joints):
            joint_frame = ctk.CTkFrame(self.joint_params_section, fg_color="transparent")
            joint_frame.pack(fill="x", padx=0, pady=3)
            
            # 关节标签 - 最左对齐
            joint_label = ctk.CTkLabel(joint_frame, text=f"{Config.current_lang['joint']}{i+1}", width=60, anchor='w')
            joint_label.pack(side="left", padx=(0, 10))

            # 速度控制 - 从Config加载初始值（转换为百分比）
            speed_initial_value = Config.joint_speeds[i] if i < len(Config.joint_speeds) else 100
            speed_frame, speed_left_btn, speed_value_label, speed_right_btn, _, _ = self.create_option_selector(
                joint_frame, current_value=speed_initial_value, unit="%", auto_pack=False
            )
            speed_frame.pack(side="left", padx=(0, 10))
            
            # 绑定速度按钮事件
            speed_left_btn.configure(command=lambda i=i: self.change_trajectory_value('speed', i, -1))
            speed_right_btn.configure(command=lambda i=i: self.change_trajectory_value('speed', i, 1))
            
            self.joint_speed_menus.append({
                'frame': speed_frame,
                'left_button': speed_left_btn,
                'value_label': speed_value_label,
                'right_button': speed_right_btn,
                'options': self.speed_options,
                'current_index': self.speed_options.index(speed_initial_value) if speed_initial_value in self.speed_options else 0
            })

            # 加速度控制 - 从Config加载初始值
            acc_initial_value = Config.joint_accelerations[i] if i < len(Config.joint_accelerations) else 100
            acc_frame, acc_left_btn, acc_value_label, acc_right_btn, _, _ = self.create_option_selector(
                joint_frame, current_value=acc_initial_value, unit="%", auto_pack=False
            )
            acc_frame.pack(side="left", padx=(0, 10))
            
            # 绑定加速度按钮事件
            acc_left_btn.configure(command=lambda i=i: self.change_trajectory_value('acc', i, -1))
            acc_right_btn.configure(command=lambda i=i: self.change_trajectory_value('acc', i, 1))
            
            self.joint_acc_menus.append({
                'frame': acc_frame,
                'left_button': acc_left_btn,
                'value_label': acc_value_label,
                'right_button': acc_right_btn,
                'options': self.acc_options,
                'current_index': self.acc_options.index(acc_initial_value) if acc_initial_value in self.acc_options else 0
            })

            # 急动度控制 - 从Config加载初始值
            jerk_initial_value = Config.joint_jerks[i] if i < len(Config.joint_jerks) else 100
            jerk_frame, jerk_left_btn, jerk_value_label, jerk_right_btn, _, _ = self.create_option_selector(
                joint_frame, current_value=jerk_initial_value, unit="%", auto_pack=False
            )
            jerk_frame.pack(side="left", padx=(0, 10))
            
            # 绑定急动度按钮事件
            jerk_left_btn.configure(command=lambda i=i: self.change_trajectory_value('jerk', i, -1))
            jerk_right_btn.configure(command=lambda i=i: self.change_trajectory_value('jerk', i, 1))
            
            self.joint_jerk_menus.append({
                'frame': jerk_frame,
                'left_button': jerk_left_btn,
                'value_label': jerk_value_label,
                'right_button': jerk_right_btn,
                'options': self.jerk_options,
                'current_index': self.jerk_options.index(jerk_initial_value) if jerk_initial_value in self.jerk_options else 0
            })

        # 插值设置区域
        self.interpolation_section = ctk.CTkFrame(self.advanced_content_frame, fg_color="transparent")
        self.interpolation_section.pack(fill="x", pady=(0, 20))
        
        # 插值标题行 - 包含标题和帮助按钮
        interpolation_title_frame = ctk.CTkFrame(self.interpolation_section, fg_color="transparent")
        interpolation_title_frame.pack(fill="x", padx=15, pady=(15, 10))
        
        self.interpolation_title = ctk.CTkLabel(interpolation_title_frame, text=f"-- {Config.current_lang['interpolation_settings']} --", 
                                     font=ctk.CTkFont(size=14, weight="bold"))
        self.interpolation_title.pack(side="left", anchor="w")
        
        self.question_button_interpolation = ctk.CTkButton(interpolation_title_frame, text="", 
            image=self.question_icon_black, width=20, height=20, fg_color="transparent", 
            hover_color="#EBEBEB")
        self.question_button_interpolation.pack(side="left", padx=(10, 0))
        
        ToolTip(self.question_button_interpolation, Config.current_lang["tooltip_interpolation"])

        self.reset_interpolation_button = ctk.CTkButton(interpolation_title_frame, 
                                                     text="",
                                                     image=self.reset_icon, 
                                                     command=self.reset_interpolation_settings, 
                                                     width=30, 
                                                     height=30,
                                                     fg_color="transparent",
                                                     hover_color="#41d054")
        self.reset_interpolation_button.pack(side="left", padx=(50, 0))
        
        # 插值内容框架
        self.interpolation_content_frame = ctk.CTkFrame(self.interpolation_section, fg_color="transparent")
        self.interpolation_content_frame.pack(fill="x", padx=15, pady=(0, 15))

        # 插值方法下拉菜单
        interpolation_method_frame = ctk.CTkFrame(self.interpolation_content_frame, fg_color="transparent")
        interpolation_method_frame.pack(fill="x", padx=0, pady=8)
        
        interpolation_method_label = ctk.CTkLabel(interpolation_method_frame, text=Config.current_lang["interpolation_method"], width=120, anchor='w')
        interpolation_method_label.pack(side="left", padx=(0, 10))
        
        self.interpolation_method_var = ctk.StringVar(value=Config.interpolation_method)
        self.interpolation_method_menu = ctk.CTkOptionMenu(
            interpolation_method_frame,
            variable=self.interpolation_method_var,
            values=self.interpolation_method_options,
            command=self.on_interpolation_method_change,
            width=150
        )
        self.interpolation_method_menu.pack(side="left", padx=(0, 10))
        
        # 存储插值方法控件引用
        self.interpolation_controls['interpolation_method'] = {
            'frame': interpolation_method_frame,
            'menu': self.interpolation_method_menu,
            'label': interpolation_method_label,
            'var': self.interpolation_method_var
        }
        
    def setup_license_tab(self):
        """Setup License tab content"""
        license_frame = self.tab_license
        
        # Create normal frame for license settings
        self.license_content_frame = ctk.CTkFrame(license_frame, fg_color="transparent")
        self.license_content_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 计划描述区域
        self.plan_description_section = ctk.CTkFrame(self.license_content_frame, fg_color="transparent")
        self.plan_description_section.pack(fill="x", pady=(0, 20))
        
        # 计划描述内容
        self.plan_description_content_frame = ctk.CTkFrame(self.plan_description_section, fg_color="transparent")
        self.plan_description_content_frame.pack(fill="x", padx=15, pady=15)
        
        # 计划描述文本
        self.plan_description_label = ctk.CTkLabel(self.plan_description_content_frame, 
                                                  text=Config.current_lang["plan_description"],
                                                  text_color="gray",
                                                  font=ctk.CTkFont(size=14),
                                                  justify="left")
        self.plan_description_label.pack(anchor="w")
        
        # 激活状态区域
        self.license_status_section = ctk.CTkFrame(self.license_content_frame, fg_color="transparent")
        self.license_status_section.pack(fill="x", pady=(0, 20))
        
        # 激活状态标题行
        status_title_frame = ctk.CTkFrame(self.license_status_section, fg_color="transparent")
        status_title_frame.pack(fill="x", padx=15, pady=(15, 10))
        
        self.license_status_title = ctk.CTkLabel(status_title_frame, text=f"-- {Config.current_lang['license_status']} --", 
                                               font=ctk.CTkFont(size=14, weight="bold"))
        self.license_status_title.pack(side="left", anchor="w")
        
        # 激活状态内容框架
        self.license_status_content_frame = ctk.CTkFrame(self.license_status_section, fg_color="transparent")
        self.license_status_content_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        # 激活状态显示
        status_frame = ctk.CTkFrame(self.license_status_content_frame, fg_color="transparent")
        status_frame.pack(fill="x", pady=5)
        
        status_label = ctk.CTkLabel(status_frame, text="Status:", width=100, anchor='w')
        status_label.pack(side="left", padx=(0, 10))
        
        self.license_status_value = ctk.CTkLabel(status_frame, text="Checking...", text_color="orange")
        self.license_status_value.pack(side="left")
        
        # 许可证类型显示
        license_type_frame = ctk.CTkFrame(self.license_status_content_frame, fg_color="transparent")
        license_type_frame.pack(fill="x", pady=5)
        
        self.license_type_label = ctk.CTkLabel(license_type_frame, text=Config.current_lang["license_type"], width=100, anchor='w')
        self.license_type_label.pack(side="left", padx=(0, 10))
        
        self.license_type_value = ctk.CTkLabel(license_type_frame, text="-", text_color="gray")
        self.license_type_value.pack(side="left")
        
        # 过期日期显示
        expiry_date_frame = ctk.CTkFrame(self.license_status_content_frame, fg_color="transparent")
        expiry_date_frame.pack(fill="x", pady=5)
        
        self.expiry_date_label = ctk.CTkLabel(expiry_date_frame, text=Config.current_lang["expiry_date"], width=100, anchor='w')
        self.expiry_date_label.pack(side="left", padx=(0, 10))
        
        self.expiry_date_value = ctk.CTkLabel(expiry_date_frame, text="-", text_color="gray")
        self.expiry_date_value.pack(side="left")
        
        # 距离过期天数显示
        days_before_expiry_frame = ctk.CTkFrame(self.license_status_content_frame, fg_color="transparent")
        days_before_expiry_frame.pack(fill="x", pady=5)
        
        self.days_before_expiry_label = ctk.CTkLabel(days_before_expiry_frame, text=Config.current_lang["days_before_expiry"], width=100, anchor='w')
        self.days_before_expiry_label.pack(side="left", padx=(0, 10))
        
        self.days_before_expiry_value = ctk.CTkLabel(days_before_expiry_frame, text="-", text_color="gray")
        self.days_before_expiry_value.pack(side="left")
        
        # 最大设备数显示
        max_devices_frame = ctk.CTkFrame(self.license_status_content_frame, fg_color="transparent")
        max_devices_frame.pack(fill="x", pady=5)
        
        self.max_devices_label = ctk.CTkLabel(max_devices_frame, text=Config.current_lang["maximum_devices"], width=100, anchor='w')
        self.max_devices_label.pack(side="left", padx=(0, 10))
        
        self.max_devices_value = ctk.CTkLabel(max_devices_frame, text="-", text_color="gray")
        self.max_devices_value.pack(side="left")
        
        # 硬件ID显示
        hardware_frame = ctk.CTkFrame(self.license_status_content_frame, fg_color="transparent")
        hardware_frame.pack(fill="x", pady=5)
        
        hardware_label = ctk.CTkLabel(hardware_frame, text="Hardware ID:", width=100, anchor='w')
        hardware_label.pack(side="left", padx=(0, 10))
        
        self.hardware_id_value = ctk.CTkTextbox(hardware_frame, height=30, width=200,
                                               fg_color="white", text_color="black",
                                               corner_radius=5, wrap="word")
        self.hardware_id_value.insert("1.0", HardwareInfo.get_hardware_id())
        self.hardware_id_value.configure(state="disabled")  # 使其不可编辑
        self.hardware_id_value.pack(side="left", padx=(0, 10))
        
        # 复制按钮
        self.copy_hardware_id_button = ctk.CTkButton(hardware_frame, text=Config.current_lang["copy"], width=70,
                                                   command=self.copy_hardware_id)
        self.copy_hardware_id_button.pack(side="left")
        
        # 软件激活区域
        self.activation_section = ctk.CTkFrame(self.license_content_frame, fg_color="transparent")
        self.activation_section.pack(fill="x", pady=(0, 20))
        
        # 激活标题行
        activation_title_frame = ctk.CTkFrame(self.activation_section, fg_color="transparent")
        activation_title_frame.pack(fill="x", padx=15, pady=(15, 10))
        
        self.activation_title = ctk.CTkLabel(activation_title_frame, text=f"-- {Config.current_lang['software_activation']} --", 
                                           font=ctk.CTkFont(size=14, weight="bold"))
        self.activation_title.pack(side="left", anchor="w")
        
        # 激活内容框架
        self.activation_content_frame = ctk.CTkFrame(self.activation_section, fg_color="transparent")
        self.activation_content_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        # 激活码输入
        activation_code_frame = ctk.CTkFrame(self.activation_content_frame, fg_color="transparent")
        activation_code_frame.pack(fill="x", pady=5)
        
        self.activation_code_label = ctk.CTkLabel(activation_code_frame, text=Config.current_lang["activation_code"], width=120, anchor='w')
        self.activation_code_label.pack(side="left", padx=(0, 10))
        
        self.activation_code_entry = ctk.CTkEntry(activation_code_frame, width=300, 
                                                placeholder_text="Enter your activation code")
        self.activation_code_entry.pack(side="left", padx=(0, 10))
        
        # 激活按钮
        self.activate_button = ctk.CTkButton(activation_code_frame, text=Config.current_lang["activate"], width=80,
                                           command=self.activate_software)
        self.activate_button.pack(side="left")
        
        # 状态信息
        self.activation_status_label = ctk.CTkLabel(self.activation_content_frame, 
                                                  text="Ready for activation", 
                                                  text_color="gray", font=ctk.CTkFont(size=11))
        self.activation_status_label.pack(pady=(10, 0))
        
        # 检查激活状态
        self.check_activation_status()


    def create_option_selector(self, parent_frame, param_name=None, current_value=None, unit="", auto_pack=True):
        """创建带有<>按钮的通用选项选择器
        
        Args:
            parent_frame: 父框架
            param_name: 参数名称标签（如果为None则不创建标签）
            current_value: 当前值
            unit: 单位（如"x", "%", "s"等）
            auto_pack: 是否自动pack框架
        """
        # 为每个参数创建一个水平框架
        option_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        if auto_pack:
            pady = 3 if param_name is None else 8  # 关节参数使用更小间距
            option_frame.pack(fill="x", padx=0, pady=pady)
        
        # 参数名称标签（可选）
        param_label = None
        if param_name:
            param_label = ctk.CTkLabel(option_frame, text=param_name, width=120, anchor='w')
            param_label.pack(side="left", padx=(0, 10))
        
        # 左按钮（减少）
        left_padx = 0 if param_name is None else (0, 5)  # 关节参数使用更小间距
        left_button = ctk.CTkButton(option_frame, text="<", width=30, height=30, 
                                   fg_color="transparent", text_color="black", hover_color="#41d054")
        left_button.pack(side="left", padx=left_padx)
        
        # 当前值显示
        width = 60 if param_name is None else 80  # 关节参数使用更小宽度
        value_padx = (1, 1) if param_name is None else (0, 5)  # 关节参数使用更小间距
        value_text = f"{current_value}{unit}" if unit else str(current_value)
        value_label = ctk.CTkLabel(option_frame, text=value_text, width=width, 
                                  fg_color="white", text_color="black", corner_radius=5)
        value_label.pack(side="left", padx=value_padx)
        
        # 右按钮（增加）
        right_padx = 0 if param_name is None else (0, 10)  # 关节参数使用更小间距
        right_button = ctk.CTkButton(option_frame, text=">", width=30, height=30, 
                                    fg_color="transparent", text_color="black", hover_color="#41d054")
        right_button.pack(side="left", padx=right_padx)
        
        return option_frame, left_button, value_label, right_button, param_label, None
     
    # License相关方法
    def check_activation_status(self):
        """检查激活状态"""
        is_activated = self.activation_manager.is_activated()
        if is_activated:
            self.license_status_value.configure(text="Activated", text_color="green")
            self.activation_status_label.configure(text="Software is activated successfully")
            self.activate_button.configure(state="disabled")
            
            # 显示激活详细信息
            self.update_activation_details()
        else:
            # 检查是否有激活详情（说明曾经激活过）
            target = self.activation_manager.get_target()
            expiration_time = self.activation_manager.get_expiration_time()
            
            if target and expiration_time:
                # 有激活详情，检查是否过期
                days_until_expiry = self.activation_manager.get_days_until_expiration()
                if days_until_expiry is not None and days_until_expiry < 0:
                    # 激活已过期
                    self.license_status_value.configure(text="Expired", text_color="red")
                    self.activation_status_label.configure(text="Activation has expired. Please renew your license.")
                else:
                    # 激活失效或其他原因
                    self.license_status_value.configure(text="Inactive", text_color="red") 
                    self.activation_status_label.configure(text="Activation is inactive. Please contact support.")
                
                self.activate_button.configure(state="normal")
                # 显示激活详细信息（即使过期也要显示）
                self.update_activation_details()
            else:
                # 从未激活
                self.license_status_value.configure(text="Not Activated", text_color="red")
                self.activation_status_label.configure(text="Please enter activation code to activate")
                self.activate_button.configure(state="normal")
                
                # 清空激活详细信息
                self.clear_activation_details()
    
    def update_activation_details(self):
        """更新激活详细信息显示"""
        try:
            # 获取激活类型
            target = self.activation_manager.get_target()
            if target:
                # 格式化显示激活类型
                target_display = target.upper() if target else "-"
                self.license_type_value.configure(text=target_display, text_color="black")
            else:
                self.license_type_value.configure(text="-", text_color="gray")
            
            # 获取过期时间
            expiration_time = self.activation_manager.get_expiration_time()
            if expiration_time:
                self.expiry_date_value.configure(text=expiration_time, text_color="black")
                
                # 计算距离过期的天数
                days_until_expiry = self.activation_manager.get_days_until_expiration()
                if days_until_expiry is not None:
                    if days_until_expiry < 0:
                        # 已过期
                        self.days_before_expiry_value.configure(
                            text=Config.current_lang["expired"], 
                            text_color="red"
                        )
                    elif days_until_expiry <= 7:
                        # 即将过期（7天内）
                        days_text = f"{days_until_expiry} {Config.current_lang['days']}"
                        self.days_before_expiry_value.configure(text=days_text, text_color="orange")
                    else:
                        # 正常状态
                        days_text = f"{days_until_expiry} {Config.current_lang['days']}"
                        self.days_before_expiry_value.configure(text=days_text, text_color="green")
                else:
                    self.days_before_expiry_value.configure(text="-", text_color="gray")
            else:
                self.expiry_date_value.configure(text="-", text_color="gray")
                self.days_before_expiry_value.configure(text="-", text_color="gray")
            
            # 获取最大激活设备数
            max_activations = self.activation_manager.get_max_activations()
            if max_activations is not None:
                if max_activations >= 999:
                    max_devices_text = Config.current_lang["unlimited"]
                else:
                    max_devices_text = str(max_activations)
                self.max_devices_value.configure(text=max_devices_text, text_color="black")
            else:
                self.max_devices_value.configure(text="-", text_color="gray")
                
        except Exception as e:
            print(f"更新激活详细信息时出错: {e}")
            self.clear_activation_details()
    
    def clear_activation_details(self):
        """清空激活详细信息显示"""
        self.license_type_value.configure(text="-", text_color="gray")
        self.expiry_date_value.configure(text="-", text_color="gray")
        self.days_before_expiry_value.configure(text="-", text_color="gray")
        self.max_devices_value.configure(text="-", text_color="gray")
    
    def copy_hardware_id(self):
        """复制硬件ID到剪贴板"""
        try:
            # 从CTkTextbox获取文本内容
            hardware_id = self.hardware_id_value.get("1.0", "end-1c")
            self.clipboard_clear()
            self.clipboard_append(hardware_id)
            self.log_message("Hardware ID copied to clipboard", "success")
        except Exception as e:
            self.log_message(f"Error copying hardware ID: {e}", "error")
    
    def activate_software(self):
        """激活软件"""
        activation_code = self.activation_code_entry.get().strip()
        if not activation_code:
            self.log_message("Please enter activation code", "warning")
            return
        
        # 禁用激活按钮并显示处理状态
        self.activate_button.configure(state="disabled", text=Config.current_lang["activating"])
        self.activation_status_label.configure(text="Activating software...", text_color="orange")
        
        # 使用after方法在短暂延迟后执行激活过程
        self.after(100, lambda: self.perform_activation(activation_code))
    
    def perform_activation(self, activation_code):
        """执行激活过程"""
        try:
            success, message = self.activation_manager.activate(activation_code)
            
            if success:
                self.license_status_value.configure(text="Activated", text_color="green")
                self.activation_status_label.configure(text=message, text_color="green")
                self.activate_button.configure(state="disabled", text=Config.current_lang["activate"])
                self.activation_code_entry.delete(0, 'end')
                # 更新激活详细信息
                self.update_activation_details()
                self.log_message(message, "success")
            else:
                self.license_status_value.configure(text="Not Activated", text_color="red")
                self.activation_status_label.configure(text=message, text_color="red")
                self.activate_button.configure(state="normal", text=Config.current_lang["activate"])
                # 清空激活详细信息
                self.clear_activation_details()
                self.log_message(message, "error")
                
        except Exception as e:
            self.license_status_value.configure(text="Error", text_color="red")
            self.activation_status_label.configure(text=f"Activation failed: {str(e)}", text_color="red")
            self.activate_button.configure(state="normal", text=Config.current_lang["activate"])
            # 清空激活详细信息
            self.clear_activation_details()
            self.log_message(f"Activation error: {e}", "error")

    # 校准相关方法
    def on_range_slider_change(self, joint_id, lower, upper, home):
        """处理RangeSlider值改变"""
        # 计算偏移值: lower = MIN_PULSE_WIDTH + min_offset, upper = MAX_PULSE_WIDTH + max_offset
        min_offset = lower - self.MIN_PULSE_WIDTH  # lower bound offset
        max_offset = upper - self.MAX_PULSE_WIDTH  # upper bound offset
        
        # 立即更新本地数据（保持UI响应性）
        self.calibration_offsets[joint_id][0] = min_offset
        self.calibration_offsets[joint_id][1] = max_offset
        
        # 实施防抖：取消之前的定时器并设置新的定时器
        if joint_id in self.calibration_timers:
            self.after_cancel(self.calibration_timers[joint_id])
        
        # 100ms 后发送校准命令（如果没有新的滑动事件）
        self.calibration_timers[joint_id] = self.after(100, 
            lambda: self.send_calibration_offset_debounced(joint_id, min_offset, max_offset))

    def get_current_pulse(self, joint_id):
        """获取当前关节的脉冲值"""
        command = f"GPULSE,J{joint_id + 1}\n"
        try:
            # 发送获取脉冲命令
            self.protocol_class.send(command)
            self.log_message(f"Requesting current pulse for Joint {joint_id + 1}")
            
            # 使用protocol_class.receive方法接收响应
            self.after(100, lambda: self.check_pulse_response(joint_id))
        except Exception as e:
            self.log_message(f"Error requesting pulse for Joint {joint_id + 1}: {e}", "error")

    def check_pulse_response(self, joint_id):
        """检查脉冲响应"""
        try:
            # 使用protocol_class.receive方法接收响应，超时1秒
            received_lines, success = self.protocol_class.receive(timeout=1)
            
            for line in received_lines:
                if line.startswith("PULSE,J"):
                    # 解析响应: PULSE,J1,1500
                    parts = line.split(',')
                    if len(parts) == 3:
                        joint_str = parts[1]
                        pulse_value = int(parts[2])
                        
                        if joint_str == f"J{joint_id + 1}":
                            # 更新RangeSlider的home位置
                            self.current_pulses[joint_id] = pulse_value
                            
                            # 获取当前的上下限值
                            current_values = self.range_sliders[joint_id].get_values()
                            
                            # 临时禁用回调，避免触发不必要的命令
                            old_callback = self.range_sliders[joint_id].callback
                            self.range_sliders[joint_id].callback = None
                            
                            self.range_sliders[joint_id].set_values(
                                current_values["lower"], 
                                current_values["upper"], 
                                pulse_value
                            )
                            
                            # 恢复回调
                            self.range_sliders[joint_id].callback = old_callback
                            
                            self.log_message(f"Joint {joint_id + 1} current pulse: {pulse_value}", "success")
                            return
            
            # 如果没有找到对应的响应，显示警告
            if not any(line.startswith("PULSE,J") for line in received_lines):
                self.log_message(f"No pulse response received for Joint {joint_id + 1}", "warning")
                
        except Exception as e:
            self.log_message(f"Error reading pulse response: {e}", "error")

    def send_calibration_offset(self, joint, min_offset, max_offset):
        """send calibration offset (both min and max)"""
        command = f"CALIBRATE,{joint},{min_offset},{max_offset}\n"
        try:
            self.protocol_class.send(command)
            self.log_message(f"Calibration offset sent: {command.strip()}")
        except Exception as e:
            self.log_message(f"Error sending calibration offset: {e}", "error")

    def send_calibration_offset_debounced(self, joint_id, min_offset, max_offset):
        """发送防抖后的校准偏移命令"""
        # 清除已执行的定时器
        if joint_id in self.calibration_timers:
            del self.calibration_timers[joint_id]
        
        # 发送校准命令
        self.send_calibration_offset(joint_id, min_offset, max_offset)

    def cancel_all_calibration_timers(self):
        """取消所有待处理的校准定时器"""
        for joint_id, timer_id in self.calibration_timers.items():
            try:
                self.after_cancel(timer_id)
            except:
                pass  # 定时器可能已经执行，忽略错误
        self.calibration_timers.clear()

    def flush_pending_calibration_commands(self):
        """立即发送所有待处理的校准命令"""
        pending_commands = []
        
        # 收集所有待处理的命令
        for joint_id, timer_id in list(self.calibration_timers.items()):
            try:
                self.after_cancel(timer_id)
                # 获取当前关节的偏移值
                min_offset = self.calibration_offsets[joint_id][0]
                max_offset = self.calibration_offsets[joint_id][1]
                pending_commands.append((joint_id, min_offset, max_offset))
            except:
                pass
        
        # 清除定时器
        self.calibration_timers.clear()
        
        # 发送所有待处理的命令
        for joint_id, min_offset, max_offset in pending_commands:
            self.send_calibration_offset(joint_id, min_offset, max_offset)

    def load_calibration(self):
        """load calibration"""
        try:
            self.calibration_offsets = ProfileManager.get_calibration_offsets()
            for i, offset_pair in enumerate(self.calibration_offsets):
                if i < len(self.range_sliders):  # 确保索引不会超出范围
                    min_offset, max_offset = offset_pair
                    
                    # 计算对应的脉宽值: lower = MIN_PULSE_WIDTH + min_offset, upper = MAX_PULSE_WIDTH + max_offset
                    lower_pulse = self.MIN_PULSE_WIDTH + min_offset
                    upper_pulse = self.MAX_PULSE_WIDTH + max_offset
                    
                    # 获取当前的home值（保持不变）
                    current_values = self.range_sliders[i].get_values()
                    home_pulse = current_values["home"]
                    
                    # 临时禁用回调，避免在加载时发送不必要的命令
                    old_callback = self.range_sliders[i].callback
                    self.range_sliders[i].callback = None
                    
                    # 更新RangeSlider
                    self.range_sliders[i].set_values(lower_pulse, upper_pulse, home_pulse)
                    
                    # 恢复回调
                    self.range_sliders[i].callback = old_callback
                    
            self.log_message("Calibration settings loaded from profile", "success")
        except Exception as e:
            self.log_message(f"Error loading calibration settings: {e}", "error")
            # 如果加载失败，使用默认值
            num_calibratable = len(ProfileManager.get_main_joints())
            self.calibration_offsets = [[0.0, 0.0] for _ in range(num_calibratable)]



    def change_trajectory_value(self, param_type, joint_index_or_param_key, direction):
        """改变轨迹参数值（包括关节参数和全局参数）"""
        # 确定控件和参数类型
        if param_type == 'dt':
            param_key = joint_index_or_param_key  # 这种情况下是param_key
            control = self.trajectory_controls[param_key]
            unit = "s"
        else:
            # 处理关节参数（speed, acc, jerk）
            joint_index = joint_index_or_param_key  # 这种情况下是joint_index
            if param_type == 'speed':
                control = self.joint_speed_menus[joint_index]
                unit = "%"
            elif param_type == 'acc':
                control = self.joint_acc_menus[joint_index]
                unit = "%"
            elif param_type == 'jerk':
                control = self.joint_jerk_menus[joint_index]
                unit = "%"
            else:
                return
        
        current_index = control['current_index']
        options = control['options']
        
        # 计算新的索引
        new_index = max(0, min(len(options) - 1, current_index + direction))
        
        if new_index != current_index:
            control['current_index'] = new_index
            new_value = options[new_index]
            
            # 更新显示文本
            control['value_label'].configure(text=f"{new_value}{unit}")
            
            # 根据参数类型调用不同的处理函数
            if param_type == 'dt':
                self._handle_dt_change(param_key, new_value)
            elif param_type == 'speed':
                self._handle_speed_change(joint_index, new_value)
            elif param_type == 'acc':
                self._handle_acc_change(joint_index, new_value)
            elif param_type == 'jerk':
                self._handle_jerk_change(joint_index, new_value)

    def _handle_dt_change(self, param_key, dt_value):
        """处理dt变化"""
        # 更新Config类的相应属性
        setattr(Config, param_key, dt_value)
        self.log_message(f"Time step dt set to: {dt_value}s")
        
        # 通知运动学框架更新轨迹优化器
        self._notify_kinematics_frame_trajectory_params_change('dt')

    def _handle_speed_change(self, joint_index, speed_value):
        """处理速度变化，发送SPD命令（将百分比转换为浮点数）"""
        # 将百分比转换为浮点数倍数
        speed_multiplier = speed_value / 100.0
        command = f"SPD,J{joint_index+1}:{speed_multiplier:.2f}"
        try:
            self.protocol_class.send(command)
            self.log_message(f"Joint {joint_index+1} speed set to: {speed_value:.1f}%")
        except Exception as e:
            self.log_message(f"Error setting joint {joint_index+1} speed: {e}", "error")
        
        # 更新Config类的关节速度配置
        Config.set_joint_speed(joint_index, speed_value)
        
        # 通知运动学框架更新轨迹优化器
        self._notify_kinematics_frame_trajectory_params_change('speed')

    def _handle_acc_change(self, joint_index, acc_value):
        """处理加速度变化（仅UI更新，不发送协议命令）"""
        # 更新Config类的关节加速度配置
        Config.set_joint_acceleration(joint_index, acc_value)
        self.log_message(f"Joint {joint_index+1} acceleration set to: {acc_value}%")
        
        # 通知运动学框架更新轨迹优化器
        self._notify_kinematics_frame_trajectory_params_change('acceleration')

    def _handle_jerk_change(self, joint_index, jerk_value):
        """处理急动度变化（仅UI更新，不发送协议命令）"""
        # 更新Config类的关节急动度配置
        Config.set_joint_jerk(joint_index, jerk_value)
        self.log_message(f"Joint {joint_index+1} jerk set to: {jerk_value}%")
        
        # 通知运动学框架更新轨迹优化器
        self._notify_kinematics_frame_trajectory_params_change('jerk')

    # UI设置相关方法
    def change_ui_value(self, param_key, direction):
        """改变UI配置值"""
        control = self.ui_controls[param_key]
        current_index = control['current_index']
        options = control['options']
        
        # 计算新的索引
        new_index = max(0, min(len(options) - 1, current_index + direction))
        
        if new_index != current_index:
            control['current_index'] = new_index
            new_value = options[new_index]
            control['value_label'].configure(text=str(new_value))
            
            # 更新Config类的相应属性
            setattr(Config, param_key, new_value)

    # 轨迹优化器相关方法

    def on_serial_baud_change(self, choice):
        """Handle serial baud rate change"""
        new_baud = int(choice)
        Config.serial_baudrate = new_baud
        SerialProtocol.SERIAL_BAUDRATE = new_baud
        self.log_message(f"Serial baud rate set to: {new_baud} bps")

    def on_can_bitrate_change(self, choice):
        """Handle CAN bitrate change"""
        new_bitrate = int(choice)
        Config.can_bitrate = new_bitrate
        CanProtocol.bitrate = new_bitrate
        self.log_message(f"CAN bitrate set to: {new_bitrate} bps")

    def on_trajectory_method_change(self, choice):
        """Handle trajectory method change"""
        Config.trajectory_method = choice
        self.log_message(f"Trajectory method set to: {choice}")
        
        # 通知运动学框架更新轨迹方法
        self._notify_kinematics_frame_trajectory_change()

    def on_interpolation_method_change(self, choice):
        """Handle interpolation method change"""
        Config.interpolation_method = choice
        self.log_message(f"Interpolation method set to: {choice}")
        
        # 通知运动学框架更新插值方法
        self._notify_kinematics_frame_interpolation_change()

    def reset_ui_settings(self):
        """重置UI设置到默认值"""
        default_values = {
            'position_steps': 0.001,
            'orientation_steps': 1,
            'rcl_preview_point_radius': 0.0006,
            'rcl_preview_axis_length': 0.02
        }
        
        for param_key, default_value in default_values.items():
            if param_key in self.ui_controls:
                control = self.ui_controls[param_key]
                options = control['options']
                
                if default_value in options:
                    new_index = options.index(default_value)
                    control['current_index'] = new_index
                    control['value_label'].configure(text=str(default_value))
                    setattr(Config, param_key, default_value)
        
        self.log_message("UI settings reset to default", "success")

    def reset_calibration(self):
        """reset calibration"""
        # 取消所有待处理的校准定时器
        self.cancel_all_calibration_timers()
        
        # 根据需要校准的关节数量动态确定校准偏移数组大小
        num_calibratable = len(ProfileManager.get_main_joints())
        self.calibration_offsets = [[0.0, 0.0] for _ in range(num_calibratable)]
        
        for i in range(len(self.calibration_offsets)):
            if i < len(self.range_sliders):  # 确保不会越界
                # 临时禁用回调，避免在重置时发送不必要的命令
                old_callback = self.range_sliders[i].callback
                self.range_sliders[i].callback = None
                
                # 重置为默认脉宽范围
                default_home = int((self.MIN_PULSE_WIDTH + self.MAX_PULSE_WIDTH) / 2)
                self.range_sliders[i].set_values(self.MIN_PULSE_WIDTH, self.MAX_PULSE_WIDTH, default_home)
                self.current_pulses[i] = default_home
                
                # 恢复回调
                self.range_sliders[i].callback = old_callback

    def reset_joint_params(self):
        """重置关节参数设置（速度、加速度、急动度）"""
        # 重置速度到默认值（100%）
        default_speed = 100
        speed_commands = []
        for i in range(len(self.joint_speed_menus)):
            if i < len(self.joint_speed_menus):
                # 将百分比转换为浮点数倍数用于SPD命令
                speed_multiplier = default_speed / 100.0
                speed_commands.append(f"J{i+1}:{speed_multiplier:.2f}")
                # 同时更新UI
                control = self.joint_speed_menus[i]
                options = control['options']
                if default_speed in options:
                    new_index = options.index(default_speed)
                    control['current_index'] = new_index
                    control['value_label'].configure(text=f"{default_speed}%")
                    # 更新Config
                    Config.set_joint_speed(i, default_speed)
        
        # 发送SPD命令
        if speed_commands:
            command = "SPD," + ",".join(speed_commands)
            try:
                self.protocol_class.send(command)
                self.log_message("Joint speeds reset to default successfully", "success")
            except Exception as e:
                self.log_message(f"Error resetting joint speeds: {e}", "error")
        
        # 重置加速度和急动度到默认值（100%）
        for i in range(len(self.joint_acc_menus)):
            if i < len(self.joint_acc_menus):
                control = self.joint_acc_menus[i]
                options = control['options']
                if 100 in options:
                    new_index = options.index(100)
                    control['current_index'] = new_index
                    control['value_label'].configure(text="100%")
                    # 更新Config
                    Config.set_joint_acceleration(i, 100)
            
            if i < len(self.joint_jerk_menus):
                control = self.joint_jerk_menus[i]
                options = control['options']
                if 100 in options:
                    new_index = options.index(100)
                    control['current_index'] = new_index
                    control['value_label'].configure(text="100%")
                    # 更新Config
                    Config.set_joint_jerk(i, 100)
        
        self.log_message("Joint parameters reset to default", "success")

    def reset_protocol_settings(self):
        """Reset protocol settings to default"""
        # 设置默认值
        default_serial_baud = 115200
        default_can_bitrate = 500000
        
        # 更新协议类的值
        SerialProtocol.SERIAL_BAUDRATE = default_serial_baud
        CanProtocol.bitrate = default_can_bitrate
        
        # 更新UI控件
        self.serial_baud_var.set(str(default_serial_baud))
        self.can_bitrate_var.set(str(default_can_bitrate))
        
        # 更新Config值
        Config.serial_baudrate = default_serial_baud
        Config.can_bitrate = default_can_bitrate
        
        self.log_message("Protocol settings reset to default", "success") 

    def reset_trajectory_settings(self):
        """重置轨迹优化器设置到默认值"""
        # 重置dt参数
        default_dt = 0.5
        if 'dt' in self.trajectory_controls:
            control = self.trajectory_controls['dt']
            options = control['options']
            
            if default_dt in options:
                new_index = options.index(default_dt)
                control['current_index'] = new_index
                control['value_label'].configure(text=str(default_dt))
                setattr(Config, 'dt', default_dt)
        
        # 重置轨迹方法到默认值
        default_trajectory_method = "scurve"
        if 'trajectory_method' in self.trajectory_controls:
            self.trajectory_method_var.set(default_trajectory_method)
            Config.trajectory_method = default_trajectory_method
        
        # 重置关节参数
        self.reset_joint_params()
        
        self.log_message("Trajectory optimizer settings reset to default", "success")

    def reset_interpolation_settings(self):
        """重置插值设置到默认值"""
        # 重置插值方法到默认值
        default_interpolation_method = "linear"
        if 'interpolation_method' in self.interpolation_controls:
            self.interpolation_method_var.set(default_interpolation_method)
            Config.interpolation_method = default_interpolation_method
        
        self.log_message("Interpolation settings reset to default", "success")

    def save_current_tab(self):
        """根据当前标签页保存相应的设置"""
        current_tab = self.tabview.get()
        
        if current_tab == Config.current_lang["ui_settings"] or current_tab == "UI Settings":
            self.save_ui_settings()
        elif current_tab == Config.current_lang["robot_settings"] or current_tab == "Robot Settings":
            self.save_robot_settings()
        elif current_tab == Config.current_lang["advanced_settings"] or current_tab == "Advanced Settings":
            self.save_advanced_settings()
        else:
            self.log_message(f"Unknown tab: {current_tab}", "warning")

    def save_ui_settings(self):
        """保存UI设置"""
        if Config.save_global_config():
            self.log_message("UI settings saved successfully", "success")
        else:
            self.log_message("Failed to save UI settings", "error")

    # Robot设置相关方法
    def save_robot_settings(self):
        """保存机器人设置（校准和协议）"""
        try:
            # 确保所有待处理的校准命令都已发送
            self.flush_pending_calibration_commands()
            
            calibration_saved = ProfileManager.save_calibration_offsets(self.calibration_offsets)
            
            # 同步保存协议设置到全局配置
            protocol_saved = Config.save_global_config()
            
            if calibration_saved and protocol_saved:
                self.log_message("Robot settings saved successfully", "success")
            elif calibration_saved:
                self.log_message("Calibration saved, but protocol settings failed", "warning")
            elif protocol_saved:
                self.log_message("Protocol settings saved, but calibration failed", "warning")
            else:
                self.log_message("Failed to save robot settings", "error")
                
        except Exception as e:
            self.log_message(f"Error saving robot settings: {e}", "error")

    # Advanced设置相关方法
    def save_advanced_settings(self):
        """保存高级设置"""
        try:
            # 保存全局配置（包括关节参数：dt, trajectory_method, interpolation_method, joint_speeds, joint_accelerations, joint_jerks等）
            config_saved = Config.save_global_config()
            
            if config_saved:
                self.log_message("Advanced settings saved successfully", "success")
            else:
                self.log_message("Failed to save advanced settings", "error")
                
        except Exception as e:
            self.log_message(f"Error saving advanced settings: {e}", "error")

    def set_language(self, lang):
        """Handle language selection change"""
        # Update the settings frame's current language
        self.current_language = lang
        
        # Load the new language configuration
        Config.load_language(lang)
        self.app.update_texts()

    def log_message(self, message, message_type="info"):
        """显示日志消息"""
        # 如果 message_label 还没有创建，则直接返回
        if not hasattr(self, 'message_label') or self.message_label is None:
            return
            
        # 根据消息类型设置颜色
        colors = {
            "info": "#1f538d",      # 蓝色 - 信息
            "success": "#2da44e",   # 绿色 - 成功
            "warning": "#bf8700",   # 橙色 - 警告  
            "error": "#cf222e"      # 红色 - 错误
        }
        
        color = colors.get(message_type, colors["info"])
        self.message_label.configure(text=message, text_color=color)
        
        # 取消之前的定时器
        if hasattr(self, 'message_timer_id') and self.message_timer_id:
            self.after_cancel(self.message_timer_id)
        
        # 设置自动清除时间（错误消息显示更长时间）
        clear_time = 5000 if message_type == "error" else 3000
        self.message_timer_id = self.after(clear_time, self.clear_message)
    
    def clear_message(self):
        """清除消息"""
        if not hasattr(self, 'message_label') or self.message_label is None:
            return
        self.message_label.configure(text=Config.current_lang["ready"], text_color="gray")
    
    def _notify_kinematics_frame_trajectory_params_change(self, param_name):
        """通知运动学框架轨迹参数已变化"""
        try:
            self.app.kinematics_frame.on_trajectory_params_changed(param_name)
        except Exception as e:
            self.log_message(f"Failed to notify kinematics frame: {e}", "warning")
    
    def _notify_kinematics_frame_trajectory_change(self):
        """通知运动学框架轨迹方法已变化"""
        try:
            self.app.kinematics_frame.on_trajectory_method_changed()
        except Exception as e:
            self.log_message(f"Failed to notify kinematics frame: {e}", "warning")
    
    def _notify_kinematics_frame_interpolation_change(self):
        """通知运动学框架插值方法已变化"""
        try:
            self.app.kinematics_frame.on_interpolation_method_changed()
        except Exception as e:
            self.log_message(f"Failed to notify kinematics frame: {e}", "warning")
    
    def update_texts(self):
        """Update UI texts based on current language"""
        current_lang = Config.get_current_lang()
        
        # Update language dropdown if it exists
        current_language = self.current_language
        self.language_dropdown.set(current_language)
        
        # Update tab names
        current_tab = self.tabview.get()
        current_tabs = list(self.tabview._tab_dict.keys())

        new_names = [
            Config.current_lang["ui_settings"],
            Config.current_lang["robot_settings"],
            Config.current_lang["advanced_settings"],
            Config.current_lang["license"]
        ]
        
        # 找到当前选中标签页的索引
        try:
            current_tab_index = current_tabs.index(current_tab)
            new_current_tab = new_names[current_tab_index]
        except (ValueError, IndexError):
            new_current_tab = new_names[0] if new_names else None
        
        # 直接创建新的标签名称字典
        updated_tabs = {}
        for old_name, new_name in zip(current_tabs, new_names):
            tab = self.tabview._tab_dict[old_name]
            updated_tabs[new_name] = tab
        
        # 清空并重建tab字典
        self.tabview._tab_dict.clear()
        self.tabview._tab_dict.update(updated_tabs)
        
        # 更新name_list
        self.tabview._name_list = list(updated_tabs.keys())
        
        # 更新current_name
        if new_current_tab:
            self.tabview._current_name = new_current_tab
        
        # 更新segmented按钮
        self.tabview._segmented_button.configure(values=self.tabview._name_list)
        
        # 设置当前选中的标签页
        if new_current_tab:
            self.tabview._segmented_button.set(new_current_tab)
        
        # 更新所有文本标签
        if hasattr(self, 'language_title'):
            self.language_title.configure(text=f"-- {Config.current_lang['language_settings']} --")
        if hasattr(self, 'language_label'):
            self.language_label.configure(text=Config.current_lang["interface_language"])
        if hasattr(self, 'ui_params_title'):
            self.ui_params_title.configure(text=f"-- {Config.current_lang['display_parameters']} --")
        if hasattr(self, 'calibration_title'):
            self.calibration_title.configure(text=f"-- {Config.current_lang['calibration_settings']} --")

        if hasattr(self, 'protocol_title'):
            self.protocol_title.configure(text=f"-- {Config.current_lang['protocol_settings']} --")
        if hasattr(self, 'trajectory_title'):
            self.trajectory_title.configure(text=f"-- {Config.current_lang['trajectory_optimiser']} --")
        if hasattr(self, 'interpolation_title'):
            self.interpolation_title.configure(text=f"-- {Config.current_lang['interpolation_settings']} --")
        if hasattr(self, 'license_status_title'):
            self.license_status_title.configure(text=f"-- {Config.current_lang['license_status']} --")
        if hasattr(self, 'activation_title'):
            self.activation_title.configure(text=f"-- {Config.current_lang['software_activation']} --")
        if hasattr(self, 'activation_code_label'):
            self.activation_code_label.configure(text=Config.current_lang["activation_code"])
        if hasattr(self, 'activate_button'):
            self.activate_button.configure(text=Config.current_lang["activate"])
        if hasattr(self, 'plan_description_label'):
            self.plan_description_label.configure(text=Config.current_lang["plan_description"])
        if hasattr(self, 'copy_hardware_id_button'):
            self.copy_hardware_id_button.configure(text=Config.current_lang["copy"])
        
        self.unified_save_button.configure(text=Config.current_lang["save"])
        
        # 更新新增的许可证详细信息标签
        if hasattr(self, 'license_type_label'):
            self.license_type_label.configure(text=Config.current_lang["license_type"])
        if hasattr(self, 'expiry_date_label'):
            self.expiry_date_label.configure(text=Config.current_lang["expiry_date"])
        if hasattr(self, 'days_before_expiry_label'):
            self.days_before_expiry_label.configure(text=Config.current_lang["days_before_expiry"])
        if hasattr(self, 'max_devices_label'):
            self.max_devices_label.configure(text=Config.current_lang["maximum_devices"])
        
        # 更新消息标签
        current_text = self.message_label.cget("text")
        if current_text in ["Ready", "准备就绪", "準備完了"]:
            self.message_label.configure(text=Config.current_lang["ready"])

        # 更新UI参数标签
        ui_param_translations = {
            'position_steps': Config.current_lang["position_steps_kinematics"],
            'orientation_steps': Config.current_lang["orientation_steps_kinematics"],
            'rcl_preview_point_radius': Config.current_lang["preview_point_radius"],
            'rcl_preview_axis_length': Config.current_lang["preview_axis_length"]
        }
        
        for param_key, new_text in ui_param_translations.items():
            if param_key in self.ui_controls and 'param_label' in self.ui_controls[param_key]:
                self.ui_controls[param_key]['param_label'].configure(text=new_text)
                # 更新"度"单位标签
                if param_key == 'orientation_steps' and self.ui_controls[param_key]['desc_label']:
                    self.ui_controls[param_key]['desc_label'].configure(text=Config.current_lang["degrees"])

        # 更新轨迹优化器参数标签
        trajectory_param_translations = {
            'dt': Config.current_lang["time_step_dt"]
        }
        
        for param_key, new_text in trajectory_param_translations.items():
            if param_key in self.trajectory_controls and 'param_label' in self.trajectory_controls[param_key]:
                self.trajectory_controls[param_key]['param_label'].configure(text=new_text)
        
        # 更新轨迹方法标签
        if 'trajectory_method' in self.trajectory_controls and 'label' in self.trajectory_controls['trajectory_method']:
            self.trajectory_controls['trajectory_method']['label'].configure(text=Config.current_lang["trajectory_method"])
        
        # 更新插值方法标签
        if 'interpolation_method' in self.interpolation_controls and 'label' in self.interpolation_controls['interpolation_method']:
            self.interpolation_controls['interpolation_method']['label'].configure(text=Config.current_lang["interpolation_method"])

        # 更新协议设置标签
        if hasattr(self, 'protocol_content_frame'):
            try:
                # 更新串口波特率标签
                for widget in self.protocol_content_frame.winfo_children():
                    if isinstance(widget, ctk.CTkFrame):
                        children = widget.winfo_children()
                        if len(children) > 0:
                            first_label = children[0]
                            if isinstance(first_label, ctk.CTkLabel):
                                current_text = first_label.cget("text")
                                if "Serial" in current_text or "串口" in current_text or "シリアル" in current_text:
                                    first_label.configure(text=Config.current_lang["serial_baud_rate"])
                                elif "CAN" in current_text:
                                    first_label.configure(text=Config.current_lang["can_bitrate"])
            except (IndexError, AttributeError):
                pass

        # 更新关节标签
        if hasattr(self, 'calibration_content_frame'):
            num_calibratable = len(ProfileManager.get_main_joints())
            for i, joint_frame in enumerate(self.calibration_content_frame.winfo_children()):
                if i < num_calibratable:
                    try:
                        # RangeSlider的标签是第一个子控件
                        label = joint_frame.winfo_children()[0]
                        if isinstance(label, ctk.CTkLabel):
                            label.configure(text=f"{Config.current_lang['joint']}{i+1}")
                    except (IndexError, AttributeError):
                        continue

        # 更新轨迹设置中的表头标签
        if hasattr(self, 'speed_header_label'):
            self.speed_header_label.configure(text=Config.current_lang["speed"])
        if hasattr(self, 'acc_header_label'):
            self.acc_header_label.configure(text=Config.current_lang["acceleration"])
        if hasattr(self, 'jerk_header_label'):
            self.jerk_header_label.configure(text=Config.current_lang["jerk"])
        
        # 更新轨迹设置中的关节参数标签
        if hasattr(self, 'joint_params_section'):
            num_joints = len(ProfileManager.get_main_joints())
            children = self.joint_params_section.winfo_children()
            # 跳过表头（第一个子元素）
            for i, joint_frame in enumerate(children[1:]):
                if i < num_joints:
                    try:
                        label = joint_frame.winfo_children()[0]
                        if isinstance(label, ctk.CTkLabel):
                            label.configure(text=f"{Config.current_lang['joint']}{i+1}")
                    except (IndexError, AttributeError):
                        continue

    def destroy(self):
        """销毁settings frame并清理所有资源"""
        try:
            # 断开协议连接
            if hasattr(self, 'protocol_class') and self.protocol_class:
                if self.protocol_class.is_connected():
                    self.protocol_class.disconnect()
            
            # 销毁所有子窗口
            for widget in self.winfo_children():
                widget.destroy()
                
        except Exception as e:
            print(f"销毁SettingsFrame时出错: {str(e)}")
        finally:
            # 最后销毁自己
            super().destroy()
