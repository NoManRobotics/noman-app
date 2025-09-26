import os
import time
import platform
import subprocess
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from PIL import Image
import customtkinter as ctk
from utils.resource_loader import ResourceLoader
from utils.config import Config
from utils.tooltip import ToolTip
from noman.profile_manager import ProfileManager
from protocol.serial_protocol import SerialProtocol, SerialCommands
from protocol.can_protocol import CanProtocol, CANCommands

class ROSFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.is_connected = False
        self.ros_enabled = False
        self.client = None
        self.ros_version = "ROS"
        
        # 初始化ResourceLoader
        self.resource_loader = ResourceLoader()
        
        # 设置协议类
        self.current_profile = ProfileManager.current_profile
        self.protocol_class = SerialProtocol if self.current_profile["robot_type"] == "PWM/I2C" else CanProtocol
        
        self.load_icons()
        self.setup_banner()
        self.setup_ros_prepare_frame()
        self.setup_ros_info_frame()
        self.setup_log_frame()

    def load_icons(self):
        """Load all icon images used in the interface"""
        # Load all icon images
        self.left_icon_active = self.load_icon("left.png", (18, 18))
        self.left_icon_disabled = self.load_icon("left_disabled.png", (18, 18))
        self.right_icon_active = self.load_icon("right.png", (18, 18))
        self.right_icon_disabled = self.load_icon("right_disabled.png", (18, 18))
        self.question_icon_white = self.load_icon("question_white.png", (18, 18))

    def load_icon(self, filename, size):
        """Helper method to load an icon with the given filename and size"""
        path = self.resource_loader.get_asset_path(os.path.join("icons", filename))
        return ctk.CTkImage(Image.open(path).convert("RGBA"), size=size)

    def setup_banner(self):
        # 使用grid布局管理器，并设置权重以使框架占据整个窗口
        self.grid_columnconfigure(0, weight=1)

        # 标题横幅框架
        self.banner_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.banner_frame.grid(row=0, column=0, padx=10, pady=(10,0), sticky="ew")
        self.banner_frame.grid_columnconfigure(1, weight=1)  # 让右侧框架可以扩展
        
        # 上方左侧框架
        self.upper_left_frame = ctk.CTkFrame(self.banner_frame, fg_color="transparent")
        self.upper_left_frame.grid(row=0, column=0, sticky="w")
        
        # Frame Label
        self.frame_label = ctk.CTkLabel(self.upper_left_frame, text="ROS", font=("Arial", 16), anchor='w')
        self.frame_label.grid(row=0, column=0, padx=10, pady=(8,0), sticky="w")
        
        # 分隔符
        separator = ctk.CTkFrame(self.upper_left_frame, height=2, width=180, fg_color="black")
        separator.grid(row=1, column=0, sticky="w", padx=10, pady=(5,10))
        
        # 上方右侧框架（导航控件）
        self.upper_right_frame = ctk.CTkFrame(self.banner_frame, fg_color="transparent")
        self.upper_right_frame.grid(row=0, column=1, sticky="e")

        # 导航控件放在右侧框架中
        self.nav_left_button = ctk.CTkButton(self.upper_right_frame, image=self.left_icon_disabled, text="", width=30, fg_color="transparent", hover_color="#dbdbdb", command=self.switch_to_ros1)
        self.nav_left_button.grid(row=0, column=0, padx=5, pady=5)
        self.nav_left_button.configure(state="disabled")

        # 中间标签
        self.ros_label = ctk.CTkLabel(self.upper_right_frame, text="ROS")
        self.ros_label.grid(row=0, column=1, padx=5, pady=5)

        self.nav_right_button = ctk.CTkButton(self.upper_right_frame, image=self.right_icon_active, text="", width=30, fg_color="transparent", hover_color="#dbdbdb", command=self.switch_to_ros2)
        self.nav_right_button.grid(row=0, column=2, padx=(5,0), pady=5)

        # Switch to ROS 框架
        self.switch_to_ros_frame = ctk.CTkFrame(self, fg_color="#B3B3B3")
        self.switch_to_ros_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.switch_to_ros_frame.grid_columnconfigure(0, weight=2)
        self.switch_to_ros_frame.grid_columnconfigure(1, weight=2)
        self.switch_to_ros_frame.grid_columnconfigure(2, weight=1)
        
        # 标题行包含标签和状态指示器
        self.title_frame = ctk.CTkFrame(self.switch_to_ros_frame, fg_color="transparent")
        self.title_frame.grid(row=0, column=0, columnspan=3, sticky="ew", padx=20, pady=10)
        
        # ROS标签
        self.switch_to_ros_label = ctk.CTkLabel(self.title_frame, 
            text=Config.current_lang["switch_to_ros"], 
            fg_color="transparent")
        self.switch_to_ros_label.grid(row=0, column=0, sticky="w")
        
        # 状态指示器
        self.status_indicator = ctk.CTkButton(self.title_frame, text="", width=6, height=6, 
                                            corner_radius=10, fg_color="grey", 
                                            hover_color="grey", border_width=0)
        self.status_indicator.configure(state="disabled")
        self.status_indicator.grid(row=0, column=1, padx=(45, 12), sticky="e")

        self.title_frame.grid_columnconfigure(0, weight=5)
        self.title_frame.grid_columnconfigure(1, weight=1)
        
        # 按钮行
        self.system_check_button = ctk.CTkButton(self.switch_to_ros_frame, 
            text=Config.current_lang["system_check"], 
            command=self.system_check, height=30, width=180, hover_color="#41d054")
        self.system_check_button.grid(row=1, column=0, padx=(20, 10), pady=10, sticky="e")
        
        self.ros_toggle_button = ctk.CTkButton(self.switch_to_ros_frame, 
            text=Config.current_lang["enable_ros"], 
            command=self.toggle_ros, height=30, width=180, hover_color="#41d054")
        self.ros_toggle_button.grid(row=1, column=1, padx=(5, 20), sticky="e")

        self.question_button = ctk.CTkButton(
            self.switch_to_ros_frame,
            text="",
            image=self.question_icon_white,
            width=20,
            height=20,
            fg_color="transparent",
            hover_color="#B3B3B3"
        )
        self.question_button.grid(row=1, column=2, padx=(5,20), pady=10, sticky="e")
        ToolTip(self.question_button, "ROS(Robot Operating System) is a SDK for writing robot software.\n\n" + 
                                    "It provides tools, libraries, and conventions that help you create complex and robust robot behavior.\n\n" +
                                    "Toggle ROS: Enable/disable ROS communication bridge between the robot and ROS nodes.\n" +
                                    "When enabled, the robot can be controlled through ROS topics and services.")

    def setup_ros_prepare_frame(self):
        # ROS准备框架
        self.ros_prepare_frame = ctk.CTkFrame(self, fg_color="#B3B3B3")
        self.ros_prepare_frame.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        self.ros_toggle_label = ctk.CTkLabel(self.ros_prepare_frame, 
            text=Config.current_lang["ros_preparation"], anchor='w')
        self.ros_toggle_label.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10)

        self.left_frame = ctk.CTkFrame(self.ros_prepare_frame, fg_color="transparent")
        self.middle_frame = ctk.CTkFrame(self.ros_prepare_frame, fg_color="transparent")
        self.right_frame = ctk.CTkFrame(self.ros_prepare_frame, fg_color="transparent")
        self.ros_prepare_frame.grid_columnconfigure(0, weight=1)  
        self.ros_prepare_frame.grid_columnconfigure(1, weight=8)  
        self.ros_prepare_frame.grid_columnconfigure(2, weight=1)  
        
        # 左侧框架添加按钮组
        self.left_button_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        self.left_button_frame.pack(expand=True)
        
        self.left_button = ctk.CTkButton(self.left_button_frame, 
                                       image=self.left_icon_disabled, 
                                       text="", 
                                       width=20, 
                                       fg_color="transparent", 
                                       hover_color="#B3B3B3",
                                       command=self.on_left_button_click)
        self.left_button.grid(row=0, column=0, padx=0)
        self.left_button.configure(state="disabled")
        
        # 右侧框架添加按钮组
        self.right_button_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        self.right_button_frame.pack(expand=True)
        
        self.right_button = ctk.CTkButton(self.right_button_frame, 
                                             image=self.right_icon_disabled, 
                                             text="", 
                                             width=20, 
                                             fg_color="transparent", 
                                             hover_color="#B3B3B3",
                                             command=self.on_right_button_click)
        self.right_button.grid(row=0, column=0, padx=0)
        self.right_button.configure(state="disabled")
        
        self.left_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        self.middle_frame.grid(row=1, column=1, padx=10, pady=10, sticky="ew") 
        self.right_frame.grid(row=1, column=2, padx=10, pady=10, sticky="ew")

        # 初始化当前步骤并显示内容
        self.current_step = 1
        self.show_step_content()

    def setup_ros_info_frame(self):
        """设置ROS信息框架，用于显示topics、services和nodes信息"""
        self.ros_info_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.ros_info_frame.grid(row=3, column=0, padx=20, pady=10, sticky="ew")
        
        # Configure column weights to center the buttons
        self.ros_info_frame.grid_columnconfigure(0, weight=1)  # Left margin
        self.ros_info_frame.grid_columnconfigure(1, weight=0)  # Topics button
        self.ros_info_frame.grid_columnconfigure(2, weight=0)  # Services button
        self.ros_info_frame.grid_columnconfigure(3, weight=0)  # Nodes button
        self.ros_info_frame.grid_columnconfigure(4, weight=1)  # Right margin

        # Topics按钮
        self.topics_button = ctk.CTkButton(self.ros_info_frame,
            text="List Topics",
            command=self.list_topics,
            width=150,
            height=32,
            hover_color="#41d054")
        self.topics_button.grid(row=0, column=1, padx=5, pady=5)

        # Services按钮
        self.services_button = ctk.CTkButton(self.ros_info_frame,
            text="List Services",
            command=self.list_services,
            width=150,
            height=32,
            hover_color="#41d054")
        self.services_button.grid(row=0, column=2, padx=5, pady=5)

        # Nodes按钮
        self.nodes_button = ctk.CTkButton(self.ros_info_frame,
            text="List Nodes",
            command=self.list_nodes,
            width=150,
            height=32,
            hover_color="#41d054")
        self.nodes_button.grid(row=0, column=3, padx=5, pady=5)

    def show_step_content(self):
        # 清除现有内容
        for widget in self.middle_frame.winfo_children():
            widget.destroy()
        
        # 配置middle_frame的列权重和固定尺寸
        self.middle_frame.grid_columnconfigure(0, weight=1)  # 主要内容列
        self.middle_frame.grid_columnconfigure(1, weight=0)  # 按钮列
        self.middle_frame.configure(width=590, height=370)  # 设置固定尺寸
        self.middle_frame.grid_propagate(False)  # 禁止框架自动调整大小
            
        # 添加步骤指示器
        self.step_frame = ctk.CTkFrame(self.middle_frame, fg_color="transparent")
        self.step_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=(10,5), sticky="ew")
        self.step_label = ctk.CTkLabel(self.step_frame, 
            text=Config.current_lang[f"step_{self.current_step}"], 
            text_color="#000000")
        self.step_label.grid(row=0, column=0, padx=10, pady=5)

        # 根据步骤显示不同内容
        if self.current_step == 1:
            self._show_urdf_content()
        elif self.current_step == 2:
            self._show_ros_setup_content()
        elif self.current_step == 3:
            self._show_workspace_content()
        elif self.current_step == 4:
            self._show_moveit_setup_content()
        elif self.current_step == 5:
            self._show_additional_deps()
        elif self.current_step == 6:
            self._show_final_step_content()

        # 只在非最终步骤时添加确认框
        if self.current_step < 6:
            self.confirm_frame = ctk.CTkFrame(self.middle_frame, fg_color="transparent")
            self.confirm_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=(10,10), sticky="ew")
            
            self.confirm_var = ctk.BooleanVar()
            self.confirm_checkbox = ctk.CTkCheckBox(self.confirm_frame, 
                text=Config.current_lang["step_complete"],
                command=self.on_confirm_changed,
                variable=self.confirm_var)
            self.confirm_checkbox.grid(row=0, column=0, padx=5, pady=5, sticky="e")
            self.confirm_frame.grid_columnconfigure(0, weight=1)  # 使列可以伸展以实现右对齐

        # 更新导航按钮状态
        self.left_button.configure(
            state="normal" if self.current_step > 1 else "disabled",
            image=self.left_icon_active if self.current_step > 1 else self.left_icon_disabled
        )
        
        # 修改右侧按钮状态逻辑
        if self.current_step == 6:  # 在最后一步时禁用右侧按钮
            self.right_button.configure(state="disabled", image=self.right_icon_disabled)
        else:  # 其他步骤根据确认框状态决定
            self.right_button.configure(
                state="normal" if self.confirm_var.get() else "disabled",
                image=self.right_icon_active if self.confirm_var.get() else self.right_icon_disabled
            )

    def _show_urdf_content(self):
        self.urdf_frame = ctk.CTkFrame(self.middle_frame, fg_color="transparent")
        self.urdf_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        self.urdf_comment = ctk.CTkLabel(self.urdf_frame, 
            text=Config.current_lang["urdf_description"], 
            text_color="#000000", 
            wraplength=300,
            justify="left")
        self.urdf_comment.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        self.urdf_button = ctk.CTkButton(self.middle_frame, 
            text="URDF", 
            command=self.save_urdf, 
            height=53, 
            hover_color="#41d054")
        self.urdf_button.grid(row=1, column=1, padx=10, pady=5)

    def _show_ros_setup_content(self):
        """显示ROS设置内容"""
        # 创建ROS1和ROS2的框架
        self.ros1_setup_frame = ctk.CTkFrame(self.middle_frame, fg_color="transparent")
        self.ros2_setup_frame = ctk.CTkFrame(self.middle_frame, fg_color="transparent")
        
        # 配置框架的列权重
        self.ros1_setup_frame.grid_columnconfigure(0, weight=1)
        self.ros2_setup_frame.grid_columnconfigure(0, weight=1)
        
        # 设置ROS1内容
        self._setup_ros1_frame(self.ros1_setup_frame)
        # 设置ROS2内容
        self._setup_ros2_frame(self.ros2_setup_frame)
        
        # 根据当前ROS版本显示对应框架
        if self.ros_version == "ROS":
            self.ros1_setup_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
            self.ros2_setup_frame.grid_forget()
        else:  # ROS2
            self.ros2_setup_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
            self.ros1_setup_frame.grid_forget()

    def _setup_ros1_frame(self, frame):
        """设置ROS1框架内容"""
        comment = ctk.CTkLabel(frame, 
            text=Config.current_lang["setup_ros_description"], 
            text_color="#000000", 
            wraplength=460,
            justify="left")
        comment.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        setup_button = ctk.CTkButton(frame, 
            text=Config.current_lang["setup_ros"], 
            command=lambda: self.open_setup_link("https://github.com/NoManRobotics/ROS-setup"),
            height=40, 
            hover_color="#41d054")
        setup_button.grid(row=1, column=0, padx=10, pady=10)

    def _setup_ros2_frame(self, frame):
        """设置ROS2框架内容"""
        comment = ctk.CTkLabel(frame, 
            text=Config.current_lang["setup_ros2_description"], 
            text_color="#000000", 
            wraplength=500,
            justify="left")  # Add justify="left"
        comment.grid(row=0, column=0, padx=10, pady=10, sticky="w")  # Change sticky="ew" to sticky="w"
        
        # 创建链接按钮框架
        links_frame = ctk.CTkFrame(frame, fg_color="transparent")
        links_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        
        # 配置列权重使按钮居中
        links_frame.grid_columnconfigure(0, weight=1)  # 左边距
        links_frame.grid_columnconfigure(1, weight=0)  # 第一个按钮
        links_frame.grid_columnconfigure(2, weight=0)  # 第二个按钮
        links_frame.grid_columnconfigure(3, weight=1)  # 右边距
        
        # Ubuntu安装按钮
        ubuntu_button = ctk.CTkButton(links_frame,
            text="Ubuntu " + Config.current_lang["installation"],
            command=lambda: self.open_setup_link("https://github.com/NoManRobotics/ROS-setup"),
            height=40,
            hover_color="#41d054")
        ubuntu_button.grid(row=0, column=1, padx=5, pady=5)
        
        # Windows安装按钮
        windows_button = ctk.CTkButton(links_frame,
            text="Windows " + Config.current_lang["installation"],
            command=lambda: self.open_setup_link("https://ms-iot.github.io/ROSOnWindows/GettingStarted/SetupRos2.html"),
            height=40,
            hover_color="#41d054")
        windows_button.grid(row=0, column=2, padx=5, pady=5)

    def open_setup_link(self, url):
        webbrowser.open(url)

    def _show_workspace_content(self):
        self.workspace_frame = ctk.CTkFrame(self.middle_frame, fg_color="transparent")
        self.workspace_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        
        # 添加工作空间路径输入
        self.workspace_path_frame = ctk.CTkFrame(self.workspace_frame, fg_color="transparent")
        self.workspace_path_frame.grid(row=0, column=0, padx=10, pady=5, sticky="ew")
        
        self.workspace_label = ctk.CTkLabel(self.workspace_path_frame, 
            text=Config.current_lang["workspace_path"], 
            text_color="#000000")
        self.workspace_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        
        self.workspace_entry = ctk.CTkEntry(self.workspace_path_frame, width=150)
        self.workspace_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.workspace_entry.insert(0, "~/ros_ws")  # 默认工作空间路径
        
        self.browse_button = ctk.CTkButton(self.workspace_path_frame, 
            text=Config.current_lang["browse"],
            command=self.browse_workspace,
            width=60,
            hover_color="#41d054")
        self.browse_button.grid(row=0, column=2, padx=5, pady=5)
        
        # 添加创建工作空间按钮
        self.create_workspace_button = ctk.CTkButton(self.workspace_path_frame, 
            text=Config.current_lang["create_workspace"], 
            command=self.create_workspace, 
            width=100,
            hover_color="#41d054")
        self.create_workspace_button.grid(row=0, column=3, padx=5, pady=5)
        
        # 添加说明文本
        self.workspace_comment = ctk.CTkLabel(self.workspace_frame, 
            text=Config.current_lang["workspace_description_ros1"] if self.ros_version == "ROS" else Config.current_lang["workspace_description_ros2"], 
            text_color="#000000", 
            wraplength=500)
        self.workspace_comment.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        
        # 添加命令框架
        commands_frame = ctk.CTkFrame(self.workspace_frame, fg_color="transparent")
        commands_frame.grid(row=2, column=0, padx=0, pady=5, sticky="ew")
        
        # 根据ROS版本显示不同的命令
        if self.ros_version == "ROS":
            commands = [
                "catkin_make",
                "source devel/setup.bash"
            ]
        else:  # ROS2
            commands = [
                "colcon build",
                "source install/setup.bash"
            ]
        
        for i, cmd in enumerate(commands):
            cmd_frame = ctk.CTkFrame(commands_frame, fg_color="transparent")
            cmd_frame.grid(row=i, column=0, padx=0, pady=1, sticky="ew")
            
            # 使用文本框显示命令
            cmd_text = ctk.CTkTextbox(cmd_frame, 
                width=400,
                height=20,
                wrap="none",
                fg_color="transparent")
            cmd_text.grid(row=0, column=0, padx=0, pady=1, sticky="ew")
            cmd_text.insert("1.0", f"$ {cmd}")
            cmd_text.configure(state="disabled")
            
            # 添加复制按钮
            copy_button = ctk.CTkButton(cmd_frame,
                text=Config.current_lang["copy"],
                command=lambda c=cmd: self.copy_to_clipboard(c),
                width=60,
                height=25,
                hover_color="#41d054")
            copy_button.grid(row=0, column=1, padx=5, pady=2)
            
            # 配置框架列权重
            cmd_frame.grid_columnconfigure(0, weight=1)

    def _show_moveit_setup_content(self):
        """显示MoveIt设置内容"""
        self.moveit_frame = ctk.CTkFrame(self.middle_frame, fg_color="transparent")
        self.moveit_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        
        # 添加MoveIt Assistant说明
        self.moveit_comment = ctk.CTkLabel(self.moveit_frame, 
            text=Config.current_lang["moveit_description_ros1"] if self.ros_version == "ROS" else Config.current_lang["moveit_description_ros2"],
            text_color="#000000", 
            wraplength=520,
            justify="left")
        self.moveit_comment.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        # 创建命令框架
        self.command_frame = ctk.CTkFrame(self.moveit_frame, fg_color="transparent")
        self.command_frame.grid(row=1, column=0, padx=0, pady=5, sticky="ew")
        
        # 创建一个内部框架来容纳命令文本和复制按钮
        inner_frame = ctk.CTkFrame(self.command_frame, fg_color="transparent")
        inner_frame.grid(row=0, column=0, sticky="w")
        
        # 显示命令
        command = "ros2 launch moveit_setup_assistant setup_assistant.launch.py" if self.ros_version == "ROS2" else "roslaunch moveit_setup_assistant setup_assistant.launch"
        
        cmd_text = ctk.CTkTextbox(inner_frame, 
            width=400,
            height=20,
            wrap="none",
            fg_color="transparent")
        cmd_text.grid(row=0, column=0, pady=2)
        cmd_text.insert("1.0", f"$ {command}")
        cmd_text.configure(state="disabled")
        
        copy_button = ctk.CTkButton(inner_frame,
            text=Config.current_lang["copy"],
            command=lambda: self.copy_to_clipboard(command),
            width=60,
            height=25,
            hover_color="#41d054")
        copy_button.grid(row=0, column=1, padx=(5,0), pady=2)
        
        # 添加教程链接
        tutorial_button = ctk.CTkButton(self.moveit_frame,
            text=Config.current_lang["view_tutorial"],
            command=lambda: webbrowser.open("https://moveit.picknik.ai/main/doc/examples/setup_assistant/setup_assistant_tutorial.html"),
            hover_color="#41d054")
        tutorial_button.grid(row=2, column=0, padx=10, pady=(20,10))

    def _show_additional_deps(self):
        """显示额外依赖项的安装步骤"""
        self.deps_frame = ctk.CTkFrame(self.middle_frame, fg_color="transparent")
        self.deps_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        
        # 创建命令框架
        commands_frame = ctk.CTkFrame(self.deps_frame, fg_color="transparent")
        commands_frame.grid(row=0, column=0, padx=0, pady=5, sticky="ew")

        comment = Config.current_lang["deps_description_ros1"] if self.ros_version == "ROS" else Config.current_lang["deps_description_ros2"]
        deps_comment = ctk.CTkLabel(commands_frame, text=comment, text_color="#000000", wraplength=500, justify="left")
        deps_comment.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        if self.ros_version == "ROS2":
            commands = [
                "cd ~ && mkdir -p microros_ws/src && cd microros_ws/src && git clone -b $ROS_DISTRO https://github.com/micro-ROS/micro_ros_setup.git",
                "cd ~/microros_ws && rosdep update && rosdep install --from-paths src --ignore-src -y && colcon build && source install/local_setup.bash",
                "ros2 run micro_ros_setup create_agent_ws.sh",
                "ros2 run micro_ros_setup build_agent.sh",
                "sudo chmod 666 /dev/ttyUSB0"
            ]
        else:  # ROS1
            commands = [
                "ls -l /dev/ttyUSB*",  # 检查串口设备
                "sudo chmod 666 /dev/ttyUSB0"  # 设置串口权限
            ]
        
        for i, cmd in enumerate(commands):
            cmd_frame = ctk.CTkFrame(commands_frame, fg_color="transparent")
            cmd_frame.grid(row=i+1, column=0, padx=0, pady=1, sticky="ew")
            
            # 使用文本框显示命令
            cmd_text = ctk.CTkTextbox(cmd_frame, 
                width=400,
                height=20,
                wrap="none",
                fg_color="transparent")
            cmd_text.grid(row=0, column=0, padx=0, pady=1, sticky="ew")
            cmd_text.insert("1.0", f"$ {cmd}")
            cmd_text.configure(state="disabled")
            
            # 添加复制按钮
            copy_button = ctk.CTkButton(cmd_frame,
                text=Config.current_lang["copy"],
                command=lambda c=cmd: self.copy_to_clipboard(c),
                width=60,
                height=25,
                hover_color="#41d054")
            copy_button.grid(row=0, column=1, padx=5, pady=2)
            
            # 配置框架列权重
            cmd_frame.grid_columnconfigure(0, weight=1)

    def copy_to_clipboard(self, text):
        """复制文本到剪贴板"""
        self.clipboard_clear()
        self.clipboard_append(text)
        self.log_message(Config.current_lang["copied_to_clipboard"])

    def create_workspace(self):
        workspace_path = os.path.expanduser(self.workspace_entry.get())
        
        try:
            # 创建工作空间目录结构
            os.makedirs(os.path.join(workspace_path, "src"), exist_ok=True)
            
            # 根据ROS版本执行不同的命令
            if self.ros_version == "ROS":
                build_commands = [
                    ["bash", "-c", "catkin_make"],
                    ["bash", "-c", f"echo 'source {workspace_path}/devel/setup.bash' >> ~/.bashrc"],
                    ["bash", "-c", "source ~/.bashrc"]
                ]
            else:  # ROS2
                build_commands = [
                    ["bash", "-c", "colcon build"],
                    ["bash", "-c", f"echo 'source {workspace_path}/install/setup.bash' >> ~/.bashrc"],
                    ["bash", "-c", "source ~/.bashrc"]
                ]
            
            # 执行命令并记录输出
            for cmd in build_commands:
                self.log_message(f"执行命令: {' '.join(cmd[2:])}")
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=workspace_path)
                if result.stdout:
                    self.log_message(result.stdout)
                if result.stderr:
                    self.log_message(result.stderr)
            
            messagebox.showinfo(Config.current_lang["success"], Config.current_lang["workspace_created"])
            
        except Exception as e:
            messagebox.showerror(Config.current_lang["error"], f"{Config.current_lang['workspace_creation_error']}: {str(e)}")
            self.log_message(f"错误: {str(e)}")

    def _show_final_step_content(self):
        """显示最终步骤内容"""
        self.final_frame = ctk.CTkFrame(self.middle_frame, fg_color="transparent")
        self.final_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        
        # 添加说明文本
        description = ctk.CTkLabel(self.final_frame, 
            text=Config.current_lang["final_step_description"], 
            text_color="#000000", 
            wraplength=520,
            justify="left")
        description.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        # 创建命令框架
        commands_frame = ctk.CTkFrame(self.final_frame, fg_color="transparent")
        commands_frame.grid(row=1, column=0, padx=0, pady=5, sticky="ew")
        
        # 根据ROS版本定义不同的命令
        if self.ros_version == "ROS2":
            commands = [
                "ros2 launch [YOUR-CONFIG] demo.launch.py use_rviz:=true",
                "ros2 run micro_ros_agent micro_ros_agent serial --dev /dev/ttyUSB0 -b 460800",
                "ros2 topic echo /joint_states"
            ]
        else:  # ROS1
            commands = [
                "roslaunch [YOUR-CONFIG] demo.launch rviz_tutorial:=true",
                "rosrun rosserial_python serial_node.py _port:=/dev/ttyUSB0 _baud:=115200",
                "rostopic echo /joint_states",
                "rostopic echo /servoarm"
            ]
        
        for i, cmd in enumerate(commands):
            cmd_frame = ctk.CTkFrame(commands_frame, fg_color="transparent")
            cmd_frame.grid(row=i, column=0, padx=0, pady=1, sticky="ew")
            
            # 使用文本框替代标签来显示命令
            cmd_text = ctk.CTkTextbox(cmd_frame, 
                width=400,
                height=20,
                wrap="none",  # 防止文本自动换行
                fg_color="transparent")
            cmd_text.grid(row=0, column=0, padx=0, pady=1, sticky="ew")
            cmd_text.insert("1.0", f"$ {cmd}")
            cmd_text.configure(state="disabled")  # 设置为只读
            
            # 添加复制按钮
            copy_button = ctk.CTkButton(cmd_frame,
                text=Config.current_lang["copy"],
                command=lambda c=cmd: self.copy_to_clipboard(c),
                width=60,
                height=25,
                hover_color="#41d054")
            copy_button.grid(row=0, column=1, padx=5, pady=2)
            
            # 配置框架列权重以允许文本框扩展
            cmd_frame.grid_columnconfigure(0, weight=1)

    def list_topics(self):
        """列出当前所有topics"""
        try:
            if self.ros_version == "ROS2":
                cmd = "ros2 topic list"
            else:
                cmd = "rostopic list"
                
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                self.log_message("\n=== Topics ===")
                topics = result.stdout.strip().split('\n')
                for topic in topics:
                    self.log_message(topic)
            else:
                self.log_message(f"Error listing topics: {result.stderr}")
        except Exception as e:
            self.log_message(f"Error: {str(e)}")

    def list_services(self):
        """列出当前所有services"""
        try:
            if self.ros_version == "ROS2":
                cmd = "ros2 service list"
            else:
                cmd = "rosservice list"
                
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                self.log_message("\n=== Services ===")
                services = result.stdout.strip().split('\n')
                for service in services:
                    self.log_message(service)
            else:
                self.log_message(f"Error listing services: {result.stderr}")
        except Exception as e:
            self.log_message(f"Error: {str(e)}")

    def list_nodes(self):
        """列出当前所有nodes"""
        try:
            if self.ros_version == "ROS2":
                cmd = "ros2 node list"
            else:
                cmd = "rosnode list"
                
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                self.log_message("\n=== Nodes ===")
                nodes = result.stdout.strip().split('\n')
                for node in nodes:
                    self.log_message(node)
            else:
                self.log_message(f"Error listing nodes: {result.stderr}")
        except Exception as e:
            self.log_message(f"Error: {str(e)}")

    def on_right_button_click(self):
        self.current_step += 1
        self.show_step_content()

    def on_left_button_click(self):
        self.current_step -= 1
        self.show_step_content()

    def on_confirm_changed(self):
        if self.confirm_var.get():
            self.right_button.configure(state="normal", image=self.right_icon_active)
        else:
            self.right_button.configure(state="disabled", image=self.right_icon_disabled)

    def setup_log_frame(self):
        self.command_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.command_frame.grid(row=4, column=0, padx=20, pady=10, sticky="nsew")
        self.log_text = ScrolledText(self.command_frame, state=tk.DISABLED, wrap=tk.WORD, 
                                     background="#000000", foreground="#41d054",
                                     width=50, height=10)
        self.log_text.pack(fill="both", expand=True)

    def system_check(self):
        self.log_message(Config.current_lang["checking_system"])
        
        # 获取操作系统信息
        os_system = platform.system()
        self.log_message(f"{Config.current_lang['system_check']}: {os_system}")

        # 检查ROS版本
        if self.ros_version == "ROS":
            # ROS1检查代码保持不变
            if os_system != 'Linux':
                self.log_message(Config.current_lang["system_not_linux"])
                self.status_indicator.configure(fg_color="#FF0000")
                return
            
            try:
                ros_version = subprocess.check_output(['rosversion', '-d']).decode().strip()
                self.log_message(f"{Config.current_lang['ros_version']}: {ros_version}")
                self.status_indicator.configure(fg_color="#41d054")
            except Exception as e:
                self.log_message(f"{Config.current_lang['error_checking_ros']}: {e}")
                self.status_indicator.configure(fg_color="#FF0000")
                
        else:  # ROS2
            try:
                if os_system == 'Windows':
                    # 使用where命令检查ros2可执行文件是否存在
                    where_result = subprocess.run('where ros2', shell=True, capture_output=True, text=True)
                    
                    if where_result.returncode == 0:
                        # 尝试在常见安装目录中查找ROS2
                        try:
                            # 检查常见的安装根目录
                            possible_root_paths = [
                                "C:\\dev",
                                "C:\\opt",
                                os.path.expanduser("~")
                            ]
                            
                            ros2_found = False
                            for root_path in possible_root_paths:
                                if os.path.exists(root_path):
                                    # 在根目录下查找以"ros2"开头的文件夹
                                    for item in os.listdir(root_path):
                                        if item.lower().startswith("ros2"):
                                            full_path = os.path.join(root_path, item)
                                            if os.path.isdir(full_path):
                                                self.log_message(f"找到ROS2安装路径: {full_path}")
                                                ros2_found = True
                                                self.status_indicator.configure(fg_color="#41d054")
                                                break
                                if ros2_found:
                                    break
                            
                            if not ros2_found:
                                self.log_message("警告: 未在标准路径找到ROS2安装，但ros2命令可用")
                                self.status_indicator.configure(fg_color="#41d054")
                                
                        except Exception as e:
                            self.log_message(f"警告: 检查ROS2安装路径时出错: {e}")
                            # 即使出错也保持绿色，因为ros2命令是可用的
                            self.status_indicator.configure(fg_color="#41d054")
                    else:
                        raise Exception("未找到ros2命令，请确保ROS2已正确安装并添加到系统PATH中")
                else:  # Linux
                    # 使用 ros2 -h 来检查ROS2是否安装
                    result = subprocess.run('ros2 -h', shell=True, capture_output=True, text=True)
                    if result.returncode == 0:
                        # 尝试获取更具体的ROS2发行版信息
                        try:
                            distro_result = subprocess.run('printenv ROS_DISTRO', shell=True, capture_output=True, text=True)
                            ros_distro = distro_result.stdout.strip() if distro_result.returncode == 0 else "未知"
                            self.log_message(f"{Config.current_lang['ros_version']}: ROS2 {ros_distro}")
                        except:
                            self.log_message(f"{Config.current_lang['ros_version']}: ROS2")
                        self.status_indicator.configure(fg_color="#41d054")
                    else:
                        raise Exception("ROS2命令执行失败")
                        
            except Exception as e:
                self.log_message(f"{Config.current_lang['error_checking_ros']}: {e}")
                self.status_indicator.configure(fg_color="#FF0000")
                # 添加更多诊断信息
                if os_system == 'Windows':
                    self.log_message("\n诊断建议:")
                    self.log_message("1. 确保已经运行 setup.bat (通常在 ROS2安装目录下的local_setup.bat)")
                    self.log_message("2. 检查系统环境变量 PATH 是否包含 ROS2 路径")
                    self.log_message("3. 尝试重新打开命令提示符并运行 'ros2 --version'")
                    self.log_message("4. 如果问题持续，可能需要重新安装 ROS2")

    def toggle_ros(self):
        # 检查当前ROS版本
        if self.ros_version == "ROS":
            # ROS1只支持Linux
            if platform.system() != 'Linux':
                self.status_indicator.configure(fg_color="#FF0000")  # 红色表示不支持
                messagebox.showerror(Config.current_lang["error"], Config.current_lang["ros_linux_only"])
                return
        else:
            # ROS2支持Linux和Windows
            if platform.system() not in ['Linux', 'Windows']:
                self.status_indicator.configure(fg_color="#FF0000")
                messagebox.showerror(Config.current_lang["error"], Config.current_lang["ros2_platform_error"])
                return

        self.ros_enabled = not self.ros_enabled
        if self.ros_enabled:
            command = "TOROS\n"
            self.protocol_class.send(command)
            self.log_message(f"发送串口命令: {command.strip()}")  # 添加日志显示

            # 根据ROS版本显示不同的启用文本
            if self.ros_version == "ROS":
                self.ros_toggle_button.configure(text=Config.current_lang["disable_ros"])
            else:
                self.ros_toggle_button.configure(text=Config.current_lang["disable_ros2"])
            self.status_indicator.configure(fg_color="#41d054")  # 绿色表示启用
        else:
            command = "TOCTR\n"
            self.protocol_class.send(command)
            # 清空串口缓冲区
            self.protocol_class.clear_serial_buffer()
            self.log_message(f"发送串口命令: {command.strip()}")
            self.log_message("已清空串口缓冲区")

            # 根据ROS版本显示不同的禁用文本
            if self.ros_version == "ROS":
                self.ros_toggle_button.configure(text=Config.current_lang["enable_ros"])
            else:
                self.ros_toggle_button.configure(text=Config.current_lang["enable_ros2"])
            self.status_indicator.configure(fg_color="grey")  # 灰色表示禁用

    def save_urdf(self):
        # 打开Carbonara-URDF仓库链接
        url = "https://github.com/NoManRobotics/Minima-URDF"
        webbrowser.open(url)

    def setup_ros(self):
        url = "https://github.com/NoManRobotics/RPL-Scripts"
        webbrowser.open(url)

    def browse_workspace(self):
        directory = filedialog.askdirectory()
        if directory:
            self.workspace_entry.delete(0, tk.END)
            self.workspace_entry.insert(0, directory)

    def log_message(self, message):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.yview(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def switch_to_ros2(self):
        self.ros_version = "ROS2"
        self.ros_label.configure(text="ROS2")
        self.nav_left_button.configure(state="normal", image=self.left_icon_active)
        self.nav_right_button.configure(state="disabled", image=self.right_icon_disabled)
        
        # 更新ROS2特定的文本和说明
        self.switch_to_ros_label.configure(text=Config.current_lang["switch_to_ros"])
        self.ros_toggle_label.configure(text=Config.current_lang["ros2_preparation"])
        
        # 刷新当前步骤的内容
        if hasattr(self, 'current_step'):
            self.show_step_content()
        
        # 更新系统检查按钮文本
        self.system_check_button.configure(text=Config.current_lang["system_check"])
        
        # 更新ROS切换按钮文本
        self.ros_toggle_button.configure(text=Config.current_lang["enable_ros2"] if not self.ros_enabled else Config.current_lang["disable_ros2"])

    def switch_to_ros1(self):
        self.ros_version = "ROS"
        self.ros_label.configure(text="ROS")
        self.nav_left_button.configure(state="disabled", image=self.left_icon_disabled)
        self.nav_right_button.configure(state="normal", image=self.right_icon_active)
        
        # 刷新当前步骤的内容
        if hasattr(self, 'current_step'):
            self.show_step_content()
        
        # 恢复ROS1特定的文本和说明
        self.switch_to_ros_label.configure(text=Config.current_lang["switch_to_ros"])
        self.ros_toggle_label.configure(text=Config.current_lang["ros_preparation"])
        
        # 更新系统检查按钮文本
        self.system_check_button.configure(text=Config.current_lang["system_check"])
        
        # 更新ROS切换按钮文本
        self.ros_toggle_button.configure(text=Config.current_lang["enable_ros"] if not self.ros_enabled else Config.current_lang["disable_ros"])

    def update_texts(self):
        """更新所有文本内容"""
        if hasattr(self, 'switch_to_ros_label') and self.switch_to_ros_label.winfo_exists():
            self.switch_to_ros_label.configure(text=Config.current_lang["switch_to_ros"])
            
        if hasattr(self, 'system_check_button') and self.system_check_button.winfo_exists():
            self.system_check_button.configure(text=Config.current_lang["system_check"])
            
        if hasattr(self, 'ros_toggle_button') and self.ros_toggle_button.winfo_exists():
            self.ros_toggle_button.configure(
                text=Config.current_lang["disable_ros"] if self.ros_enabled else Config.current_lang["enable_ros"]
            )
            
        if hasattr(self, 'ros_toggle_label') and self.ros_toggle_label.winfo_exists():
            self.ros_toggle_label.configure(text=Config.current_lang["ros_preparation"])

        if hasattr(self, 'workspace_comment') and self.workspace_comment.winfo_exists():
            self.workspace_comment.configure(text=Config.current_lang["workspace_description_ros1"] if self.ros_version == "ROS" else Config.current_lang["workspace_description_ros2"])
        
        if hasattr(self, 'moveit_comment') and self.moveit_comment.winfo_exists():
            self.moveit_comment.configure(text=Config.current_lang["moveit_description_ros1"] if self.ros_version == "ROS" else Config.current_lang["moveit_description_ros2"])

        # 如果当前在步骤页面,更新步骤内容
        if hasattr(self, 'current_step'):
            self.show_step_content()
