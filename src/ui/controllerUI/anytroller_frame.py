import os
import json
import time
import tkinter as tk
from PIL import Image
import customtkinter as ctk
from tkinter import messagebox, filedialog
from tkinter.scrolledtext import ScrolledText
from threading import Thread, Event

from utils.config import Config
from utils.resource_loader import ResourceLoader
from utils.tooltip import ToolTip
from protocol.serial_protocol import SerialProtocol, SerialCommands
from protocol.can_protocol import CanProtocol, CANCommands
from noman.profile_manager import ProfileManager
from ui.controllerUI.command_info_dialog import CommandInfoDialog
from ui.controllerUI.script_generator import ScriptGenerator

class AnytrollerFrame(ctk.CTkFrame):
    def __init__(self, master, robot_state):
        super().__init__(master)
        self.current_profile = ProfileManager.current_profile
        self.name = self.current_profile["name"]

        # 更新配置文件组加载逻辑
        self.main_group = None
        self.tool_group = None
        self.actuation = None

        for group_name, _ in ProfileManager.get_all_groups().items():
            if ProfileManager.is_end_effector_group(group_name):
                self.actuation = ProfileManager.get_end_effector(group_name)["actuation"]
                self.tool_group = ProfileManager.get_joints_by_group(group_name)
            else:
                self.main_group = ProfileManager.get_joints_by_group(group_name)

        # 使用主要组加载关节限制和初始角度
        self.joint_limits = []
        self.home_angles = []
        for joint in self.main_group:
            # 检查关节是否有limit属性
            if "limit" in joint:
                self.joint_limits.append((joint["limit"]["lower"], joint["limit"]["upper"]))
                self.home_angles.append(joint["home"])

        self.servo_count = len(self.joint_limits)

        self.protocol_class = SerialProtocol if self.current_profile["robot_type"] == "PWM/I2C" else CanProtocol

        self.robot_state = robot_state
        self.robot_state.add_observer(self)
        
        self.operating_system = Config.operating_system

        self.stop_event = Event()
        self.read_thread = None
        self.recording = False
        self.replaying = False
        self.gripper_open = False
        self.paused = False
        self.data = []
        self.command_history = []
        
        # 存储当前关节角度
        self.current_angles = self.home_angles.copy()

        self.load_icons()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)  # 让日志框架可以扩展
        
        self.setup_banner()
        self.setup_control_frame()
        self.setup_program_and_home_frames()
        self.setup_callback_frame()
        self.setup_log_frame()
        
        # 初始化命令信息对话框
        self.command_info_dialog = None
        
        # 初始化脚本生成器引用
        self.script_generator = None

    def load_icons(self):
        """Load all icon images used in the interface"""
        # Load all icon images
        self.checklist_icon = self.load_icon("checklist.png", (20, 20))
        self.generate_icon = self.load_icon("generate.png", (18, 18))
        self.question_icon_white = self.load_icon("question_white.png", (15, 15))

    def load_icon(self, filename, size):
        """Helper method to load an icon with the given filename and size"""
        path = ResourceLoader.get_asset_path(os.path.join("icons", filename))
        return ctk.CTkImage(Image.open(path).convert("RGBA"), size=size)

    def setup_banner(self):
        # 上方框架
        self.banner_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.banner_frame.grid(row=0, column=0, padx=10, pady=(10,0), sticky="ew")
        self.banner_frame.grid_columnconfigure(1, weight=1)  # 让右侧框架可以扩展
        
        # 上方左侧框架
        self.upper_left_frame = ctk.CTkFrame(self.banner_frame, fg_color="transparent")
        self.upper_left_frame.grid(row=0, column=0, sticky="w")
        
        # Frame Label
        self.frame_label = ctk.CTkLabel(self.upper_left_frame, text=f"{Config.current_lang['controller']} ({self.name})", font=("Arial", 16), anchor='w')
        self.frame_label.grid(row=0, column=0, padx=10, pady=(8,0), sticky="w")
        
        separator = ctk.CTkFrame(self.upper_left_frame, height=2, width=180, fg_color="black")
        separator.grid(row=1, column=0, sticky="w", padx=10, pady=(5,10))
        
        # 上方右侧框架
        self.upper_right_frame = ctk.CTkFrame(self.banner_frame, fg_color="transparent")
        self.upper_right_frame.grid(row=0, column=1, sticky="e")

        # Add generate button
        self.generate_button = ctk.CTkButton(
            self.upper_right_frame,
            text="",
            image=self.generate_icon,
            width=30,
            command=self.generate_script,
            fg_color="transparent", 
            hover_color="#41d054"
        )
        self.generate_button.grid(row=0, column=0, padx=(0,5), sticky="e")

        # Add checklist button
        self.checklist_button = ctk.CTkButton(
            self.upper_right_frame,
            text="",
            image=self.checklist_icon,
            width=30,
            command=self.show_command_info,
            fg_color="transparent", 
            hover_color="#41d054"
        )
        self.checklist_button.grid(row=0, column=1, padx=(0,5), sticky="e")

    def setup_control_frame(self):
        self.control_frame = ctk.CTkFrame(self, fg_color="#B3B3B3")
        self.control_frame.grid(row=1, column=0, padx=20, pady=(10,21), sticky="ew")
        self.control_label = ctk.CTkLabel(self.control_frame, text=Config.current_lang["arm_control"], anchor='w')
        self.control_label.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10)

        # Main body frame - 包含关节滑块
        self.mainbody_frame = ctk.CTkFrame(self.control_frame, fg_color="#B3B3B3")
        self.mainbody_frame.grid(row=1, column=0, sticky="ew", padx=(10,0), pady=(0,5))
        self.mainbody_frame.grid_columnconfigure(1, weight=1)  # Make right side expandable
        
        # Left mainbody frame - 关节滑块
        self.left_mainbody_frame = ctk.CTkFrame(self.mainbody_frame, fg_color="#B3B3B3")
        self.left_mainbody_frame.grid(row=0, column=0, sticky="ew", padx=(0,10))
        
        # Right mainbody frame - 空的，为了布局平衡
        self.right_mainbody_frame = ctk.CTkFrame(self.mainbody_frame, fg_color="#B3B3B3")
        self.right_mainbody_frame.grid(row=0, column=1, sticky="nsew")
        
        # Tool frame - gripper/tool controls
        self.tool_frame = ctk.CTkFrame(self.control_frame, fg_color="#B3B3B3")
        self.tool_frame.grid(row=2, column=0, sticky="ew", padx=(10,0), pady=5)
        
        # Bottom frame - execution controls
        self.bottom_frame = ctk.CTkFrame(self.control_frame, fg_color="#B3B3B3")
        self.bottom_frame.grid(row=3, column=0, sticky="ew", padx=(10,0), pady=(5,0))

        self.setup_joint_sliders()
        self.setup_gripper_control()
        self.setup_execution_controls()

    def setup_joint_sliders(self):
        # 初始化数组来存储滑块和标签
        self.joint_sliders = []
        self.joint_labels = []

        for i in range(self.servo_count):
            # 前4个关节放在左侧，其余放在右侧
            if i < 4:
                parent_frame = self.left_mainbody_frame
                row = i
            else:
                parent_frame = self.right_mainbody_frame  
                row = i - 4
            
            label_text = ctk.CTkLabel(parent_frame, text=f"{Config.current_lang['joint']} {i+1}")
            label_text.grid(row=row, column=0, padx=10, pady=10)
            
            slider = ctk.CTkSlider(
                parent_frame, 
                from_=self.joint_limits[i][0], 
                to=self.joint_limits[i][1], 
                number_of_steps=int(self.joint_limits[i][1] - self.joint_limits[i][0]),
                width=190,
                command=lambda v, i=i: self.on_joint_change(i)
            )
            slider.set(self.home_angles[i])
            slider.grid(row=row, column=1, padx=10, pady=10, sticky="ew")
            
            value_label = ctk.CTkLabel(parent_frame, text=f"{self.home_angles[i]} °")
            value_label.grid(row=row, column=2, padx=10, pady=10)
            
            # 存储到数组中
            self.joint_sliders.append(slider)
            self.joint_labels.append(value_label)

    def setup_gripper_control(self):
        """setup gripper control based on actuation type"""
        self.gripper_label = ctk.CTkLabel(self.tool_frame, text=Config.current_lang["tool"])
        self.gripper_label.grid(row=0, column=0, padx=10, pady=10)
        
        if not self.tool_group or not self.actuation:
            self.gripper_switch = ctk.CTkSwitch(self.tool_frame, text="", command=self.on_gripper_toggle)
            self.gripper_switch.grid(row=0, column=1, padx=10, pady=10, sticky="w")
            return
        
        if self.actuation == "signal":
            # Simple toggle for signal-based control
            self.gripper_switch = ctk.CTkSwitch(self.tool_frame, text="", command=self.on_gripper_toggle)
            self.gripper_switch.grid(row=0, column=1, padx=10, pady=10, sticky="w")
            
        elif self.actuation == "uniform movable":
            # Single slider for all joints in tool group with combined limits
            # 只考虑有limit属性的关节
            joints_with_limits = [joint for joint in self.tool_group if "limit" in joint]
            if joints_with_limits:
                min_limit = min(joint["limit"]["lower"] for joint in joints_with_limits)
                max_limit = max(joint["limit"]["upper"] for joint in joints_with_limits)
                initial_value = joints_with_limits[0]["home"]  # Use first joint's home as initial
            else:
                # 如果没有有效的关节，使用默认值
                min_limit, max_limit = 0, 1
                initial_value = 0
            
            slider_steps = 0
            if joints_with_limits and joints_with_limits[0]["type"] == "revolute":
                unit = "°" 
                slider_steps = max_limit - min_limit
            elif joints_with_limits and joints_with_limits[0]["type"] == "prismatic":
                unit = "m"
                slider_steps = (max_limit - min_limit) * 1000 / 2 # per 2mm
            else:
                unit = ""
                slider_steps = 1
            
            self.gripper_slider = ctk.CTkSlider(
                self.tool_frame,
                from_=min_limit,
                to=max_limit,
                number_of_steps=slider_steps,
                command=self.on_uniform_gripper_change,
                width=100
            )
            self.gripper_slider.set(initial_value)
            self.gripper_slider.grid(row=0, column=1, padx=10, pady=10, sticky="w")
            
            self.gripper_value_label = ctk.CTkLabel(self.tool_frame, text=f"{initial_value} {unit}")
            self.gripper_value_label.grid(row=0, column=2, padx=10, pady=10, sticky="w")
            
        elif self.actuation == "independent movable":
            # Individual sliders for each joint in tool group
            self.gripper_sliders = []
            self.gripper_labels = []
            
            for i, joint in enumerate(self.tool_group):
                # 只处理有limit属性的关节
                if "limit" not in joint:
                    continue
                    
                row_offset = i + 1  # Start from row 1 since row 0 has the gripper label
 
                slider_steps = 0
                if joint["type"] == "revolute":
                    unit = "°"
                    slider_steps = joint["limit"]["upper"] - joint["limit"]["lower"]
                elif joint["type"] == "prismatic":
                    unit = "m"
                    slider_steps = (joint["limit"]["upper"] - joint["limit"]["lower"]) * 1000 / 2 # per 2mm
                else:
                    continue  # 跳过不支持的关节类型
                
                # Joint label
                joint_label = ctk.CTkLabel(self.tool_frame, text=f"{joint['name']}")
                joint_label.grid(row=row_offset, column=0, padx=10, pady=10)
                
                # Joint slider
                slider = ctk.CTkSlider(
                    self.tool_frame,
                    from_=joint["limit"]["lower"],
                    to=joint["limit"]["upper"],
                    number_of_steps=slider_steps,
                    command=lambda v, idx=i: self.on_independent_gripper_change(idx),
                    width=100
                )
                slider.set(joint["home"])
                slider.grid(row=row_offset, column=1, padx=10, pady=10, sticky="w")
                
                # Value label
                value_label = ctk.CTkLabel(self.tool_frame, text=f"{joint['home']} {unit}")
                value_label.grid(row=row_offset, column=2, padx=10, pady=10, sticky="w")
                
                self.gripper_sliders.append(slider)
                self.gripper_labels.append(value_label)

    def setup_execution_controls(self):
        # home button
        self.home_button = ctk.CTkButton(self.bottom_frame, text=Config.current_lang["home"], command=self.reset_sliders, width=120, hover_color="#41d054")
        self.home_button.grid(row=0, column=0, padx=10, pady=10)

        # execute button
        self.execute_button = ctk.CTkButton(self.bottom_frame, text=Config.current_lang["execute"], command=self.on_execute, width=120, hover_color="#41d054")
        self.execute_button.grid(row=0, column=1, padx=10, pady=10)
        
        # record once button
        self.record_once_button = ctk.CTkButton(self.bottom_frame, text=Config.current_lang["record_once"], command=self.on_record_once, width=120, hover_color="#41d054", state=ctk.DISABLED)
        self.record_once_button.grid(row=0, column=2, padx=(60,10), pady=10)

        # loop delay label
        self.loop_delay_label = ctk.CTkLabel(self.bottom_frame, text=Config.current_lang["loop_delay"])
        self.loop_delay_label.grid(row=0, column=3, padx=(15,5), pady=10)
        
        # loop delay entry
        self.loop_delay_entry = ctk.CTkEntry(self.bottom_frame, width=40, state=ctk.DISABLED)
        self.loop_delay_entry.grid(row=0, column=4, padx=5, pady=10)

        # question button
        self.question_button = ctk.CTkButton(
            self.bottom_frame,
            text="",
            image=self.question_icon_white,
            width=20,
            height=20,
            fg_color="transparent",
            hover_color="#B3B3B3"
        )
        self.question_button.grid(row=0, column=5, padx=5, pady=10)
        ToolTip(self.question_button, "Delay: the time between each recorded trajectory\nRecord Once: record last angles after EXEC execution with loop delay")

    def setup_program_and_home_frames(self):
        self.program_home_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.program_home_frame.grid(row=2, column=0, padx=20, pady=21, sticky="ew")
        self.program_home_frame.grid_columnconfigure(1, weight=1)

        self.program_frame = ctk.CTkFrame(self.program_home_frame, fg_color="#B3B3B3")
        self.program_frame.grid(row=0, column=0, padx=(0, 10), sticky="nsew")

        self.program_label = ctk.CTkLabel(self.program_frame, text=Config.current_lang["program"], anchor='w')
        self.program_label.grid(row=0, column=0, columnspan=3, sticky="ew", padx=10)

        self.start_button = ctk.CTkButton(self.program_frame, text=Config.current_lang["start_recording"], command=self.on_start_recording, width=120, hover_color="#41d054")
        self.start_button.grid(row=1, column=0, padx=(20,10), pady=10, sticky="ew")

        self.stop_button = ctk.CTkButton(self.program_frame, text=Config.current_lang["stop_recording"], command=self.on_stop_recording, width=120, font=ctk.CTkFont(size=15), hover_color="#41d054")
        self.stop_button.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        self.replay_button = ctk.CTkButton(self.program_frame, text=Config.current_lang["replay_trajectory"], command=self.on_replay_file, width=120, hover_color="#41d054")
        self.replay_button.grid(row=2, column=0, padx=(20,10), pady=10, sticky="ew")

        self.repeat_frame = ctk.CTkFrame(self.program_frame, fg_color="#B3B3B3")
        self.repeat_frame.grid(row=2, column=1, padx=10, pady=10, sticky="ew")

        self.repeat_label = ctk.CTkLabel(self.repeat_frame, text=Config.current_lang["repeat"], anchor='w')
        self.repeat_label.grid(row=0, column=0, padx=(0, 5), pady=2, sticky="w")

        self.repeat_spinbox = ctk.CTkEntry(self.repeat_frame, width=50)
        self.repeat_spinbox.grid(row=0, column=1, padx=5, pady=2, sticky="e")
        self.repeat_spinbox.insert(0, "1")

         # 添加进度条
        self.progress_frame = ctk.CTkFrame(self.program_frame, fg_color="#B3B3B3")
        self.progress_frame.grid(row=3, column=0, columnspan=3, padx=10, pady=10, sticky="ew")
        
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame)
        self.progress_bar.pack(fill="x", padx=10, pady=5)
        self.progress_bar.set(0)
        
        # 添加进度更新事件
        self.progress_update_event = Event()

        self.estop_button = ctk.CTkButton(self.program_frame, text=Config.current_lang["stop"], command=self.on_emergency_pause_resume, width=80, height=80, hover_color="#d64141")
        self.estop_button.grid(row=1, column=2, rowspan=2, padx=20, pady=10)

    def setup_callback_frame(self):
        # Setting frame
        self.callback_frame = ctk.CTkFrame(self.program_home_frame, fg_color="#B3B3B3")
        self.callback_frame.grid(row=0, column=1, padx=(10, 0), sticky="nsew")

        self.callback_label = ctk.CTkLabel(self.callback_frame, text=Config.current_lang["callback"], anchor='w')
        self.callback_label.grid(row=0, column=0, columnspan=3, sticky="ew", padx=10)

        self.connection_status_frame = ctk.CTkFrame(self.callback_frame, fg_color="transparent")
        self.connection_status_frame.grid(row=1, column=0, padx=10, pady=0, sticky="ew")

        self.serial_status = ctk.CTkLabel(self.connection_status_frame, text=Config.current_lang["serial"], anchor='w', width=65)
        self.serial_status.grid(row=0, column=0, padx=(10,0), pady=5, sticky="w")

        self.status_indicator = ctk.CTkButton(self.connection_status_frame, 
                                         text="", width=6, height=6, 
                                         corner_radius=3, fg_color="red", 
                                         hover_color="red", border_width=0)
        self.status_indicator.grid(row=0, column=1, padx=(12,5), pady=5, sticky="w")
        self.status_indicator.configure(state="disabled")

        self.connection_status_label = ctk.CTkLabel(self.connection_status_frame, text=Config.current_lang["disconnected"], anchor='w')
        self.connection_status_label.grid(row=0, column=2, padx=5, pady=5, sticky="w")

        # 状态框架
        self.callback_status_frame = ctk.CTkFrame(self.callback_frame, fg_color="transparent")
        self.callback_status_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")

        self.status_label = ctk.CTkLabel(self.callback_status_frame, text=Config.current_lang["status"], anchor='w', width=65)
        self.status_label.grid(row=0, column=0, padx=(10,0), sticky="w")

        self.callback_status_indicator = ctk.CTkButton(self.callback_status_frame, 
                                                 text="", width=6, height=6, 
                                                 corner_radius=3, fg_color="grey", 
                                                 hover_color="grey", border_width=0)
        self.callback_status_indicator.grid(row=0, column=1, padx=(12,5), sticky="w")
        self.callback_status_indicator.configure(state="disabled")

        self.current_status = ctk.CTkLabel(self.callback_status_frame, text=Config.current_lang["idle"], anchor='w')
        self.current_status.grid(row=0, column=2, padx=5, sticky="w")

    def setup_log_frame(self):
        self.command_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.command_frame.grid(row=4, column=0, padx=10, pady=10, sticky="nsew")
        self.log_text = ScrolledText(self.command_frame, state=tk.DISABLED, wrap=tk.WORD, 
                                     background="#000000", foreground="#41d054",
                                     width=50, height=10)
        self.log_text.pack(padx=10, pady=10, fill="both", expand=True)

    def update_connection_status(self):
        """更新连接状态"""
        if self.protocol_class.is_connected():
            self.status_indicator.configure(fg_color="#41d054")
            self.connection_status_label.configure(text=f"{self.protocol_class.port}")
        else:
            self.status_indicator.configure(fg_color="red")
            self.connection_status_label.configure(text=Config.current_lang["disconnected"])

    def update_callback_status(self, status_text, status_color="grey"):
        """更新回调状态指示器和文本
        Args:
            status_text: 状态文本
            status_color: 状态颜色 (grey/green/purple/red)
        """
        self.current_status.configure(text=status_text)
        self.callback_status_indicator.configure(fg_color=status_color, hover_color=status_color)

    def on_gripper_toggle(self):
        self.gripper_open = self.gripper_switch.get()
        
        try:
            # Use 0 or 1 for all tools, consistent with kinematics frame
            tool_value = 1 if self.gripper_open else 0
            command = f"M280,{tool_value}\n"
            self.protocol_class.send(command)
            self.log_message(f"Tool command sent: {command.strip()}")
            
            # 如果正在录制，记录M280命令到历史
            if self.recording:
                self.command_history.append(('M280', time.time()))
                
        except Exception as e:
            self.log_message(f"Error sending tool command: {e}")

    def on_uniform_gripper_change(self, value):
        """处理统一可移动执行器的滑块变化"""       
        # 获取单位符号
        unit = "°" if self.tool_group[0]["type"] == "revolute" else "m"
        float_value = float(f"{value:.3f}")
        self.gripper_value_label.configure(text=f"{float_value} {unit}")
        
        # 发送工具控制命令，所有关节使用相同值
        try:
            # 为工具组中的每个关节发送相同的值
            joint_values = [str(float_value)] * len(self.tool_group)
            command = f"M280,{','.join(joint_values)}\n"
            self.protocol_class.send(command)
            self.log_message(f"Uniform tool command sent: {command.strip()}")
            
            # 如果正在录制，记录M280命令到历史
            if self.recording:
                self.command_history.append(('M280', time.time()))
                
        except Exception as e:
            self.log_message(f"Error sending uniform tool command: {e}")

    def on_independent_gripper_change(self, joint_index):
        """处理独立可移动执行器的滑块变化"""
        if joint_index >= len(self.gripper_sliders) or joint_index >= len(self.tool_group):
            return
            
        slider = self.gripper_sliders[joint_index]
        label = self.gripper_labels[joint_index]
        joint = self.tool_group[joint_index]
        
        # 获取单位符号和值
        unit = "°" if joint["type"] == "revolute" else "m"
        float_value = float(f"{slider.get():.3f}")
        label.configure(text=f"{float_value} {unit}")
        
        # 发送工具控制命令，包含所有关节的当前值
        try:
            joint_values = []
            for i, s in enumerate(self.gripper_sliders):
                joint_values.append(str(float(f"{s.get():.3f}")))
            
            command = f"M280,{','.join(joint_values)}\n"
            self.protocol_class.send(command)
            self.log_message(f"Independent tool command sent: {command.strip()}")
            
            # 如果正在录制，记录M280命令到历史
            if self.recording:
                self.command_history.append(('M280', time.time()))
                
        except Exception as e:
            self.log_message(f"Error sending independent tool command: {e}")

    def reset_sliders(self):
        for i, initial_value in enumerate(self.home_angles):
            slider = self.joint_sliders[i]
            slider.set(initial_value)
            self.on_joint_change(i)

    def on_joint_change(self, joint_index, no_state_update=False):
        """处理关节滑块变化
        Args:
            joint_index: 关节索引
            no_state_update: 是否不更新状态
        """
        slider = self.joint_sliders[joint_index]
        label = self.joint_labels[joint_index]
        value = int(slider.get())
        label.configure(text=f"{value} °")
        
        self.current_angles[joint_index] = value
        
        if not no_state_update:
            self.robot_state.update_state('joint_angles', self.current_angles)

    def on_execute(self):
        # 使用joint_sliders数组获取角度值
        joint_angles = [slider.get() for slider in self.joint_sliders]
        
        # 发送关节运动命令（只有关节）
        joint_command = ",".join(map(str, joint_angles)) + "\n"

        try:
            self.protocol_class.send("EXEC\n")
            self.protocol_class.send(joint_command)
            self.log_message(f"Joint data sent: {joint_command.strip()}")
            
            # 如果正在录制，记录EXEC命令到历史
            if self.recording:
                self.command_history.append(('EXEC', time.time()))
            
            # 等待关节执行完成
            _, isReplied = self.protocol_class.receive(timeout=5, expected_signal="CP0")
            if not isReplied:
                self.log_message("joint execution timeout")
                self.update_callback_status(Config.current_lang["execution_timeout"], "red")
            else:
                self.log_message("Joint execution completed")
            
        except Exception as e:
            self.log_message(f"Error sending data: {e}")

    def on_record_once(self):
        """record once""" 
        loop_delay = float(self.loop_delay_entry.get() or 0)
        
        # 找到最后的EXEC和M280命令
        last_exec_idx = -1
        last_m280_idx = -1
        
        for i, (cmd, _) in enumerate(self.command_history):
            if cmd == 'EXEC':
                last_exec_idx = i
            elif cmd == 'M280':
                last_m280_idx = i
        
        try:
            # 根据存在性和顺序决定发送什么
            if last_exec_idx == -1 and last_m280_idx == -1:
                # 都没有发送过，不需要记录任何东西
                self.log_message("No commands to record")
                return
            elif last_exec_idx == -1:
                # 只发送过M280，只记录工具
                self.protocol_class.send("RECONCET\n")
                all_responses, success = self.protocol_class.receive(timeout=7, expected_signal="TP0")
                if success:
                    for response in all_responses:
                        if response.startswith("M280,"):
                            self.data.append(response)
                            self.log_message(f"Recorded tool data: {response}")
                else:
                    self.log_message("Timeout waiting for TP0 signal")
            elif last_m280_idx == -1:
                # 只发送过EXEC，只记录关节
                self.protocol_class.send("RECONCEJ\n")
                all_responses, success = self.protocol_class.receive(timeout=7, expected_signal="CP0")
                if success:
                    for response in all_responses:
                        if response.startswith("REC,"):
                            self.data.append(response)
                            self.log_message(f"Recorded joint data: {response}")
                else:
                    self.log_message("Timeout waiting for CP0 signal")
            else:
                # 两个都存在，按顺序发送和接收
                if last_m280_idx < last_exec_idx:
                    # M280先发送，先记录工具，再记录关节
                    self.protocol_class.send("RECONCET\n")
                    all_responses, success = self.protocol_class.receive(timeout=7, expected_signal="TP0")
                    if success:
                        for response in all_responses:
                            if response.startswith("M280,"):
                                self.data.append(response)
                                self.log_message(f"Recorded tool data: {response}")
                    else:
                        self.log_message("Timeout waiting for TP0 signal")
                    
                    # 然后记录关节
                    self.protocol_class.send("RECONCEJ\n")
                    all_responses, success = self.protocol_class.receive(timeout=7, expected_signal="CP0")
                    if success:
                        for response in all_responses:
                            if response.startswith("REC,"):
                                self.data.append(response)
                                self.log_message(f"Recorded joint data: {response}")
                    else:
                        self.log_message("Timeout waiting for CP0 signal")
                else:
                    # EXEC先发送，先记录关节，再记录工具
                    self.protocol_class.send("RECONCEJ\n")
                    all_responses, success = self.protocol_class.receive(timeout=7, expected_signal="CP0")
                    if success:
                        for response in all_responses:
                            if response.startswith("REC,"):
                                self.data.append(response)
                                self.log_message(f"Recorded joint data: {response}")
                    else:
                        self.log_message("Timeout waiting for CP0 signal")
                    
                    # 然后记录工具
                    self.protocol_class.send("RECONCET\n")
                    all_responses, success = self.protocol_class.receive(timeout=7, expected_signal="TP0")
                    if success:
                        for response in all_responses:
                            if response.startswith("M280,"):
                                self.data.append(response)
                                self.log_message(f"Recorded tool data: {response}")
                    else:
                        self.log_message("Timeout waiting for TP0 signal")
            
            # 添加延迟到数据中
            self.data.append(f"DELAY,S{loop_delay}")
            
            # 清空命令历史，为下一次记录做准备
            self.command_history.clear()
            
        except Exception as e:
            self.log_message(f"Error sending data: {e}")
            # 即使出错也要清空命令历史
            self.command_history.clear()

    def read_serial(self):
        """read data from serial"""
        buffer = ""
        while self.recording and not self.stop_event.is_set():
            try:
                serial_conn = self.protocol_class._serial
                if serial_conn and serial_conn.in_waiting:
                    buffer += serial_conn.read(serial_conn.in_waiting).decode()
                    lines = buffer.split('\n')
                    buffer = lines.pop()  # leave incomplete lines in buffer
                    for line in lines:
                        line = line.strip()
                        if line.startswith("REC,"):
                            self.data.append(line)
                            self.log_message(f"received data: {line}")
                            
            except Exception as e:
                self.log_message(f"从串口读取时出错：{e}")
            time.sleep(0.005)
        self.log_message(f"停止读取串口数据。总数据点：{len(self.data)}")

    def start_recording(self):
        """start recording"""
        self.recording = True
        self.data.clear()
        self.command_history.clear()  # 清空命令历史
        self.protocol_class.send("RECSTART\n")  # send start command to ESP32
        self.stop_event.clear()  # reset stop event
        if self.read_thread is None or not self.read_thread.is_alive():
            self.read_thread = Thread(target=self.read_serial)
            self.read_thread.start()
        self.log_message("Recording started.")

    def stop_recording(self, filename):
        """stop recording"""
        self.recording = False
        self.protocol_class.send("RECSTOP\n", sleep_time=0.1)  # send stop command to ESP32
        
        if not self.data:
            self.log_message("No data recorded.")
            messagebox.showwarning("No Data", "No data was recorded.")
            return
        
        try:
            with open(filename, 'w') as f:
                json.dump(self.data, f, indent=4)
            messagebox.showinfo("Saved", f"Data saved to {filename}")
            self.log_message(f"Recording stopped and data saved to {filename}.")
        except Exception as e:
            error_msg = f"Error saving data to file: {str(e)}"
            self.log_message(error_msg)
            messagebox.showerror("Save Error", error_msg)
        
        self.data.clear()  # clear data for next recording
        self.command_history.clear()  # clear command history

    def update_progress(self, total_steps):
        """更新进度条的线程函数"""
        current_step = 0
        self.progress_bar.set(0)
        
        while current_step < total_steps and self.replaying:
            if self.progress_update_event.is_set():
                current_step += 1
                # 使用after来确保在主线程中更新UI
                self.after(0, lambda v=current_step/total_steps: self.progress_bar.set(v))
                self.progress_update_event.clear()
            time.sleep(0.001)  # 短暂休眠避免CPU占用过高
        
        self.after(0, lambda: self.progress_bar.set(0))

    def replay_trajectory(self, json_file, repeat_count):
        """
        Replay trajectory from file with pause/resume support
        Args:
            json_file: trajectory file
            repeat_count: repeat count
        """
        self.replaying = True
        try:
            with open(json_file, 'r') as f:
                trajectory = json.load(f)

            total_steps = len(trajectory) * repeat_count
            
            # 启动进度条更新线程
            progress_thread = Thread(target=self.update_progress, args=(total_steps,))
            progress_thread.daemon = True  # 设置为守护线程
            progress_thread.start()
            
            for repeat in range(repeat_count):
                for data in trajectory:
                    # 暂停时等待
                    while self.paused and self.replaying:
                        time.sleep(0.01)
                    
                    if not self.replaying:
                        break
                    
                    # 检查是否是延迟命令
                    if isinstance(data, str) and data.startswith("DELAY,"):
                        command = data if data.endswith("\n") else data + "\n"
                        self.protocol_class.send(command)
                        continue
                    elif isinstance(data, str) and data.startswith("REC,"):
                        # 新格式的REC数据
                        joint_values = data[4:].split(',')
                        command = "REP," + ",".join(joint_values) + "\n"
                    else:
                        # 兼容旧格式的数组数据
                        command = "REP," + ",".join(map(str, data)) + "\n"
                    
                    self.protocol_class.send(command, sleep_time=0.001)
                    
                    if not self.protocol_class.receive(timeout=5, expected_signal="CP1"):
                        self.log_message("replay timeout")
                        
                    # 触发进度更新事件
                    self.progress_update_event.set()
                
                if not self.replaying:
                    break
                
            self.log_message(f"Replaying trajectory from {json_file} for {repeat_count} times.")
            self.update_callback_status(Config.current_lang["idle"], "grey")
        except Exception as e:
            self.log_message(f"Error replaying trajectory: {e}")
        finally:
            self.replaying = False
            # 等待进度条线程结束
            if progress_thread.is_alive():
                progress_thread.join(timeout=1.0)

    def on_start_recording(self):
        """start recording button callback"""
        if not self.recording:
            self.start_recording()
            self.update_callback_status(Config.current_lang["recording"], "green")
            # 启用相关控件
            self.loop_delay_entry.configure(state=ctk.NORMAL)
            self.record_once_button.configure(state=ctk.NORMAL)
            self.execute_button.configure(state=ctk.NORMAL)

    def on_stop_recording(self):
        """stop recording button callback"""
        if self.recording:
            self.stop_event.set()  # set stop event to end read thread
            if self.read_thread and self.read_thread.is_alive():
                self.read_thread.join(timeout=1.0)  # wait for thread to finish, max wait 1 second
            filename = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
            if filename:
                self.stop_recording(filename)
            else:
                self.log_message("Recording stopped. No file saved.")
                self.recording = False
                self.protocol_class.send("RECSTOP\n")  # send stop command even if user cancels save
                
            # Configure control states
            self.update_callback_status(Config.current_lang["stopped_recording"], "grey")
            self.loop_delay_entry.configure(state=ctk.DISABLED)
            self.record_once_button.configure(state=ctk.DISABLED)
            self.execute_button.configure(state=ctk.NORMAL)

    def on_replay_file(self):
        serial_conn = self.protocol_class._serial
        if serial_conn and serial_conn.is_open and not self.recording and not self.replaying:
            json_file = filedialog.askopenfilename(filetypes=[("JSON files", ".json")])
            if json_file:
                repeat_count = int(self.repeat_spinbox.get()) if self.repeat_spinbox.get().isdigit() else 1
                self.update_callback_status("Replaying trajectory...", "purple")
                self.replaying = True
                self.paused = False 
                Thread(target=self.replay_trajectory, args=(json_file, repeat_count)).start()

    def on_emergency_pause_resume(self):
        if self.replaying:
            if self.paused:
                # resume operation
                self.paused = False
                self.estop_button.configure(text=Config.current_lang["stop"])
                self.update_callback_status("Replaying trajectory...", "purple")
                self.log_message("Resuming replay.")
            else:
                self.paused = True
                self.estop_button.configure(text=Config.current_lang["resume"])
                self.update_callback_status("Paused", "red")
                self.log_message("Paused replay.")

    def generate_script(self):
        self.script_generator = ScriptGenerator(self)
        self.script_generator.create_window()

    def show_command_info(self):
        """显示命令信息窗口"""
        # 创建命令按钮映射（简化版，只包含anytroller支持的命令）
        gripper_control = None
        if hasattr(self, 'gripper_switch'):
            gripper_control = self.gripper_switch
        elif hasattr(self, 'gripper_slider'):
            gripper_control = self.gripper_slider
        elif hasattr(self, 'gripper_sliders') and self.gripper_sliders:
            gripper_control = self.gripper_sliders[0]
        
        command_button_map = {
            "EXEC": self.execute_button,
            "RECONCEJ": self.record_once_button,
            "RECONCET": self.record_once_button,
            "RECSTART": self.start_button,
            "RECSTOP": self.stop_button,
            "REP": self.replay_button,
            "M280": gripper_control if gripper_control else None,
            "DELAY": self.loop_delay_entry
        }
        
        # 定义anytroller支持的命令列表
        supported_commands = ["EXEC", "RECONCEJ", "RECONCET", "RECSTART", "RECSTOP", "REP", "M280", "DELAY", "SPD"]
        
        # 创建或更新命令信息对话框
        if self.command_info_dialog is None:
            self.command_info_dialog = CommandInfoDialog(self, command_button_map, supported_commands)
        else:
            self.command_info_dialog.update_command_button_map(command_button_map, supported_commands)
        
        # 显示对话框
        self.command_info_dialog.show()

    def log_message(self, message):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.yview(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def update_texts(self):
        # basic control interface text update
        self.frame_label.configure(text=f"{Config.current_lang['controller']} ({self.name})")
        self.control_label.configure(text=Config.current_lang["arm_control"])
        self.home_button.configure(text=Config.current_lang["home"])
        self.execute_button.configure(text=Config.current_lang["execute"])
        self.record_once_button.configure(text=Config.current_lang["record_once"])
        self.program_label.configure(text=Config.current_lang["program"])
        self.start_button.configure(text=Config.current_lang["start_recording"])
        self.stop_button.configure(text=Config.current_lang["stop_recording"])
        self.replay_button.configure(text=Config.current_lang["replay_trajectory"])
        self.repeat_label.configure(text=Config.current_lang["repeat"])
        self.estop_button.configure(text=Config.current_lang["stop"] if not getattr(self, 'paused', False) else Config.current_lang["resume"])
        self.gripper_label.configure(text=Config.current_lang["tool"])
        self.loop_delay_label.configure(text=Config.current_lang["loop_delay"])
        self.callback_label.configure(text=Config.current_lang["callback"])
        self.status_label.configure(text=Config.current_lang["status"])
        self.serial_status.configure(text=Config.current_lang["serial"])
        self.update_callback_status(Config.current_lang["idle"], "grey")
        
        # 更新连接状态文本（如果当前处于断开状态）
        if not self.protocol_class.is_connected():
            self.connection_status_label.configure(text=Config.current_lang["disconnected"])

        # update slider labels
        for i in range(self.servo_count):
            # 前4个关节在左侧，其余在右侧
            if i < 4:
                parent_frame = self.left_mainbody_frame
                row = i
            else:
                parent_frame = self.right_mainbody_frame
                row = i - 4
                
            # 从对应框架获取关节标签
            label_widgets = [w for w in parent_frame.grid_slaves(row=row, column=0) if isinstance(w, ctk.CTkLabel)]
            if label_widgets:
                label_widgets[0].configure(text=f"{Config.current_lang['joint']} {i+1}")

        # 调用脚本生成器的update_texts方法
        if self.script_generator is not None:
            self.script_generator.update_texts()

    def update(self, state):
        """根据状态更新UI
        Args:
            state: 状态字典
        """
        joint_angles = state['joint_angles']
        
        # 更新滑块显示的关节角度
        for i, angle in enumerate(joint_angles):
            if i < len(self.joint_sliders):
                slider = self.joint_sliders[i]
                slider.set(angle)
                # 调用on_joint_change来处理值的变化
                self.on_joint_change(i, no_state_update=True)

    def destroy(self):
        """销毁anytroller frame并清理所有资源"""
        try:
            # 停止所有线程
            self.stop_event.set()
            if self.read_thread and self.read_thread.is_alive():
                self.read_thread.join(timeout=1.0)
            
            # 移除robot_state观察者
            if hasattr(self, 'robot_state') and self.robot_state:
                self.robot_state.remove_observer(self)
            
            # 断开协议连接
            if hasattr(self, 'protocol_class') and self.protocol_class:
                if self.protocol_class.is_connected():
                    self.protocol_class.disconnect()
            
            # 销毁脚本生成器
            if hasattr(self, 'script_generator') and self.script_generator:
                self.script_generator.destroy()
            
            # 销毁所有子窗口
            for widget in self.winfo_children():
                widget.destroy()
                
        except Exception as e:
            print(f"销毁AnytrollerFrame时出错: {str(e)}")
        finally:
            # 最后销毁自己
            super().destroy()
