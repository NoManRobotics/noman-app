import os
import time
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox, filedialog
from tkinter import filedialog
from PIL import Image, ImageTk
import pybullet as p
import serial.tools.list_ports
import math
import numpy as np

from utils.config import Config
from utils.resource_loader import ResourceLoader
from utils.range_slider import RangeSlider
from utils.tooltip import ToolTip
from utils.color_utils import *
from noman.utils.urdf_manager import *
from noman.profile_manager import ProfileManager
from noman.physics.bullet.physics_engine import PhysicsEngine
from protocol.serial_protocol import SerialProtocol, SerialCommands
from protocol.can_protocol import CanProtocol, CANCommands

class RobotProfileFrame(ctk.CTkFrame):
    def __init__(self, master, app, robot_state=None):
        super().__init__(master)
        self.app = app
        self.grid(row=0, column=0, sticky="nsew")
        self.grid_columnconfigure(0, weight=1)
        
        # 添加机器人状态对象
        self.robot_state = robot_state
        
        # 将自身注册为robot_state的观察者
        if self.robot_state:
            self.robot_state.add_observer(self)
        
        # 初始化专用的物理引擎客户端
        self.physics_engine = PhysicsEngine.get_instance()
        self.client_id = self.physics_engine.init_client('profile_viewer', p.DIRECT)
        self.robot_id = None

        self.profiles_path = ProfileManager.profiles_path
        self.is_creating_new_profile = False
        self.is_editing_profile      = False

        self.tools = []
        self.joint_labels  = []
        self.joint_widgets = {}
        self.used_group_names = set()
        self.used_colors = set()

        # 添加组名和颜色列表
        self.available_group_names = list("ABCDEFG")
        self.color_palette = [
            "#db0936",  # 红色
            "#0e76b3",  # 蓝色
            "#D295BF",  # 紫色
            "#FF7700",  # 橙色
            "#EDAE49",  # 黄色
            "#f58eec",  # 粉色
            "#00AFB5"   # 青色
        ]
        self.default_color = "#FFFFFF"
        
        # ID label variable
        self.id_var = tk.StringVar()
        
        self.load_icons()
        self.init_render_param()
        self.setup_banner()
        self.setup_connection_frame()
        self.setup_profile_frame()
        self.setup_status_frame()
        self.setup_custom_options()
        self.setup_button_frame()

        self.load_profile()

    def load_icons(self):
        """Load all icon images used in the interface"""
        # Load all icon images
        self.refresh_icon = self.load_icon("refresh_white.png", (20, 20))
        self.edit_icon = self.load_icon("edit.png", (20, 20))
        self.share_icon = self.load_icon("share.png", (20, 20))
        self.bin_icon = self.load_icon("bin.png", (20, 20))
        self.specqr_icon = self.load_icon("specqr.png", (70, 70))
        self.plus_icon = self.load_icon("plus.png", (18, 18))
        self.minus_icon = self.load_icon("minus.png", (18, 18))
        self.setting_icon = self.load_icon("setting.png", (20, 20))
        self.up_icon = self.load_icon("uparrow.png", (15, 15))
        self.down_icon = self.load_icon("downarrow.png", (15, 15))
        self.question_icon = self.load_icon("question_white.png", (15, 15))

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
        self.frame_label = ctk.CTkLabel(self.upper_left_frame, text=Config.current_lang["robot_profile"], font=("Arial", 16), anchor='w')
        self.frame_label.grid(row=0, column=0, padx=10, pady=(8,0), sticky="w")
        
        separator = ctk.CTkFrame(self.upper_left_frame, height=2, width=180, fg_color="black")
        separator.grid(row=1, column=0, sticky="w", padx=10, pady=(5,10))
        
        # 上方右侧框架
        self.upper_right_frame = ctk.CTkFrame(self.banner_frame, fg_color="transparent")
        self.upper_right_frame.grid(row=0, column=1, sticky="e")
        
        # 编辑按钮
        self.edit_button = ctk.CTkButton(
            self.upper_right_frame,
            text="",
            image=self.edit_icon,
            width=30,
            command=self.on_edit,
            fg_color="transparent",
            hover_color="#41d054"
        )
        self.edit_button.grid(row=0, column=0, padx=(0,5), sticky="e")

        # 导出按钮
        self.export_button = ctk.CTkButton(
            self.upper_right_frame,
            text="",
            image=self.share_icon,
            width=30,
            command=self.export_info,
            fg_color="transparent",
            hover_color="#41d054"
        )
        self.export_button.grid(row=0, column=1, padx=(0,5), sticky="e")
        
        # 删除按钮
        self.delete_button = ctk.CTkButton(
            self.upper_right_frame,
            text="",
            image=self.bin_icon,
            width=30,
            command=self.delete_profile,
            fg_color="transparent",
            hover_color="#FF6B6B"
        )
        self.delete_button.grid(row=0, column=2, padx=(0,10), sticky="e")

    def setup_connection_frame(self):
        self.upper_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.upper_frame.grid(row=1, column=0, padx=20, pady=(10,21), sticky="ew")
        self.upper_frame.grid_columnconfigure(0, weight=1)

        # 左侧框架
        self.upper_left_frame = ctk.CTkFrame(self.upper_frame, fg_color="#B3B3B3")
        self.upper_left_frame.grid(row=0, column=0, sticky="ew")

        self.connection_label = ctk.CTkLabel(self.upper_left_frame, text=Config.current_lang["serial_connection"], anchor='w')
        self.connection_label.grid(row=0, column=0, columnspan=4, sticky="ew", padx=10)

        self.ports = self.enumerate_ports()
        self.port_var = ctk.StringVar()
        self.port_dropdown = ctk.CTkOptionMenu(self.upper_left_frame, variable=self.port_var, values=self.ports)
        self.port_dropdown.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        if self.ports:
            self.port_dropdown.set(self.ports[0])

        self.connect_button = ctk.CTkButton(self.upper_left_frame, text=Config.current_lang["connect"], command=self.on_connect, hover_color="#41d054", width=110)
        self.connect_button.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        self.disconnect_button = ctk.CTkButton(self.upper_left_frame, text=Config.current_lang["disconnect"], command=self.on_disconnect, state=ctk.DISABLED, hover_color="#41d054", width=110)
        self.disconnect_button.grid(row=1, column=2, padx=10, pady=10, sticky="ew")

        # add refresh button
        self.refresh_button = ctk.CTkButton(self.upper_left_frame, text="", image=self.refresh_icon, command=self.refresh_ports, width=40, hover_color="#41d054")
        self.refresh_button.grid(row=1, column=3, padx=10, pady=10, sticky="ew")

        # 右侧框架，包含 QR 码
        self.upper_right_frame = ctk.CTkFrame(self.upper_frame, fg_color="transparent")
        self.upper_right_frame.grid(row=0, column=1, sticky="ew")

        self.specqr_label = ctk.CTkLabel(self.upper_right_frame, image=self.specqr_icon, text="")  # 确保不显示文本
        self.specqr_label.grid(row=0, column=0, padx=(20,0), pady=5, sticky="ew")
        self.specqr_label.grid_remove()  # 默认隐藏

    def setup_profile_frame(self):
        """设置配置文件框架"""

        self.middle_frame = ctk.CTkFrame(self, fg_color="#B3B3B3")
        self.middle_frame.grid(row=2, column=0, padx=20, pady=(10,21), sticky="nsew")
        # 修改列权重配置，使两列平均分配空间
        self.middle_frame.grid_columnconfigure((0, 1), weight=1, uniform="column")
        
        # 左侧框架
        self.lower_left_frame = ctk.CTkFrame(self.middle_frame, fg_color="transparent")
        self.lower_left_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        # Robot ID
        self.id_label = ctk.CTkLabel(self.lower_left_frame, text="ROBOT ID ", anchor='w')
        self.id_label.grid(row=0, column=0, padx=(0,10), pady=(0,10), sticky="w")
        self.id_display = ctk.CTkLabel(self.lower_left_frame, textvariable=self.id_var)
        self.id_display.grid(row=0, column=0, padx=(65,0), pady=(0,10), sticky="w")

        # Robot Type Option Menu
        self.type_label = ctk.CTkLabel(self.lower_left_frame, text=Config.current_lang["type"], anchor='w')
        self.type_label.grid(row=1, column=0, padx=(0,10), pady=10, sticky="w")
        
        self.robot_type_var = tk.StringVar(value="PWM/I2C")
        self.type_option = ctk.CTkOptionMenu(
            self.lower_left_frame,
            variable=self.robot_type_var,
            values=["PWM/I2C", "Stepper/CAN"]
        )
        self.type_option.grid(row=1, column=0, padx=(55,0), pady=10, sticky="w")

        # 添加机器人名称输入框
        self.name_label = ctk.CTkLabel(self.lower_left_frame, text=Config.current_lang["name"], anchor='w')
        self.name_label.grid(row=2, column=0, padx=(0,10), pady=10, sticky="w")
        
        self.name_var = tk.StringVar()
        self.name_entry = ctk.CTkEntry(self.lower_left_frame, textvariable=self.name_var)
        self.name_entry.grid(row=2, column=0, padx=(55,0), pady=10, sticky="w")

        self.urdf_frame = ctk.CTkFrame(self.lower_left_frame, fg_color="transparent")
        self.urdf_frame.grid(row=3, column=0, sticky="ew")

        # URDF Folder
        self.urdf_label = ctk.CTkLabel(self.urdf_frame, text="URDF:", anchor='w')
        self.urdf_label.grid(row=0, column=0, padx=(0,10), pady=(10,5), sticky="w")

        self.urdf_entry = ctk.CTkEntry(self.urdf_frame)
        self.urdf_entry.grid(row=0, column=1, padx=10, pady=(10,5), sticky="ew")

        self.upload_urdf_button = ctk.CTkButton(self.urdf_frame, text="Browse", 
                                           command=self.upload_urdf,
                                           hover_color="#41d054",
                                           width=80)
        self.upload_urdf_button.grid(row=0, column=2, padx=5, pady=(10,5))
        
        # 右侧框架 - 3D 视图
        self.lower_right_frame = ctk.CTkFrame(self.middle_frame, fg_color="white")
        self.lower_right_frame.grid(row=0, column=1, padx=10, pady=10)
        
        # 创建用于显示3D视图的画布
        self.view_canvas = tk.Canvas(self.lower_right_frame, bg="white", highlightthickness=0, height=200)
        self.view_canvas.grid(row=0, column=0, sticky="nsew")
        
        # 绑定鼠标事件用于视图交互
        self.view_canvas.bind("<Button-1>", self.on_mouse_down)
        self.view_canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.view_canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.view_canvas.bind("<MouseWheel>", self.on_mouse_wheel)  # Windows
        self.view_canvas.bind("<Button-4>", self.on_mouse_wheel)    # Linux up
        self.view_canvas.bind("<Button-5>", self.on_mouse_wheel)    # Linux down
        
        # 添加鼠标中键平移视图功能
        self.view_canvas.bind("<Button-2>", self.on_middle_mouse_down)  # 中键按下 (Linux)
        self.view_canvas.bind("<Button-3>", self.on_middle_mouse_down)  # 中键按下 (Windows)
        self.view_canvas.bind("<B2-Motion>", self.on_middle_mouse_drag)  # 中键拖动 (Linux)
        self.view_canvas.bind("<B3-Motion>", self.on_middle_mouse_drag)  # 中键拖动 (Windows)
        self.view_canvas.bind("<ButtonRelease-2>", self.on_middle_mouse_up)  # 中键释放 (Linux)
        self.view_canvas.bind("<ButtonRelease-3>", self.on_middle_mouse_up)  # 中键释放 (Windows)
        
        # 绑定窗口大小改变事件
        self.view_canvas.bind("<Configure>", self.on_resize)

    def setup_status_frame(self):
        self.lower_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.lower_frame.grid(row=3, column=0, padx=20, pady=(10,15), sticky="nsew")
        self.lower_frame.grid_columnconfigure((0, 1), weight=1, uniform="column")
        
        # 左侧中间框架 - 关节信息显示
        self.left_middle_frame = ctk.CTkFrame(self.lower_frame, fg_color="transparent")
        self.left_middle_frame.grid(row=0, column=0, padx=(0,10), pady=5, sticky="nsew")
        self.left_middle_frame.grid_columnconfigure(0, weight=1)
        
        # 创建按钮框架
        self.group_buttons_frame = ctk.CTkFrame(self.left_middle_frame, fg_color="transparent")
        self.group_buttons_frame.grid(row=0, column=0, padx=(10,0), pady=5, sticky="ew")
        
        # 存储按钮的列表
        self.group_buttons = []
        
        self.update_group_buttons()
        
        # 可滚动框架用于显示关节信息
        self.joint_scroll_frame = ctk.CTkScrollableFrame(
            self.left_middle_frame,
            fg_color="transparent",
            height=380
        )
        self.joint_scroll_frame.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
        self.joint_scroll_frame.grid_columnconfigure(0, weight=1)

    def setup_custom_options(self):
        """设置自定义选项框架，包含主要设置和终端执行器选项卡"""
        self.right_middle_frame = ctk.CTkFrame(self.lower_frame, fg_color="#B3B3B3")
        self.right_middle_frame.grid(row=0, column=1, padx=(10,0), pady=10, sticky="nsew")
        self.right_middle_frame.grid_columnconfigure(0, weight=1)
        self.right_middle_frame.grid_rowconfigure(1, weight=1)

        # 添加选项卡式按钮框架
        tab_frame = ctk.CTkFrame(self.right_middle_frame, fg_color="transparent")
        tab_frame.grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        tab_frame.grid_columnconfigure((0, 1), weight=1, uniform="tabs")
        
        # 创建两个独立的框架，每个框架包含一个按钮和下划线
        self.main_tab_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        self.main_tab_frame.grid(row=0, column=0, sticky="ew")
        self.main_tab_frame.grid_columnconfigure(0, weight=1)
        
        self.end_effector_tab_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        self.end_effector_tab_frame.grid(row=0, column=1, sticky="ew")
        self.end_effector_tab_frame.grid_columnconfigure(0, weight=1)
        
        # 主要选项卡按钮
        self.main_button = ctk.CTkButton(
            self.main_tab_frame,
            text="GROUPS",
            fg_color="#B3B3B3",
            hover_color="#B3B3B3",
            command=self.show_groups_frame
        )
        self.main_button.grid(row=0, column=0, sticky="ew")
        
        # 主要选项卡下划线
        self.main_underline = ctk.CTkFrame(self.main_tab_frame, height=2, fg_color="#DBDBDB")
        self.main_underline.grid(row=1, column=0, padx=5, sticky="ew")
        
        # 终端执行器选项卡按钮
        self.end_effector_button = ctk.CTkButton(
            self.end_effector_tab_frame,
            text="TOOLS",
            fg_color="#B3B3B3",
            hover_color="#B3B3B3",
            command=self.show_end_effector_frame
        )
        self.end_effector_button.grid(row=0, column=0, sticky="ew")
        
        # 终端执行器下划线
        self.end_effector_underline = ctk.CTkFrame(self.end_effector_tab_frame, height=2, fg_color="#DBDBDB")
        self.end_effector_underline.grid(row=1, column=0, padx=5, sticky="ew")
        self.end_effector_underline.grid_remove()  # 默认隐藏
        
        # 创建内容框架
        self.content_frame = ctk.CTkFrame(self.right_middle_frame, fg_color="transparent")
        self.content_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)

        # 创建主要设置框架
        self.group_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.group_frame.grid_columnconfigure(0, weight=1)

        # 创建终端执行器框架
        self.end_effector_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")

        # 设置主要设置和终端执行器框架
        self.setup_groups_frame()
        self.setup_end_effector_frame()

        # 默认显示主要设置
        self.show_groups_frame()

    def setup_groups_frame(self):
        """设置主要设置框架"""
        self.group_frame.grid(row=0, column=0, padx=0, sticky="ew")
        self.group_frame.grid_columnconfigure(0, weight=1)

    def setup_end_effector_frame(self):
        """设置终端执行器界面"""
        self.end_effector_frame.grid_columnconfigure(0, weight=1)
        self.end_effector_frames = []
        
    def update_joint_widgets(self, selected_group=None):
        """
        根据关节类型创建不同类型的控件：
        - revolute关节：使用旋转角度的范围滑块
        - prismatic关节：使用平移距离的范围滑块
        - 其他类型：使用适当的小部件
        
        Args:
            selected_group: 选中的组名，如果为None则不显示任何控件
        """
        # 清除之前的小部件
        for widget in self.group_frame.winfo_children():
            widget.destroy()
        
        # 如果没有选择组，直接返回
        if selected_group is None:
            return
        
        # 获取选中的组
        group_data = ProfileManager.get_group_by_name(selected_group)
        if not group_data:
            return
        
        joint_indices = group_data.get("includes", [])
        
        if not joint_indices:
            return
        
        # 添加组链状态标题框架
        group_header_frame = ctk.CTkFrame(self.group_frame, fg_color="transparent")
        group_header_frame.grid(row=0, column=0, pady=(0, 2), sticky="ew")
        
        # 创建组框架
        group_widget_frame = ctk.CTkFrame(self.group_frame, fg_color="transparent")
        group_widget_frame.grid(row=1, column=0, sticky="ew")
        group_widget_frame.grid_columnconfigure(0, weight=1)
        
        # 创建关节控件容器
        joints_container = ctk.CTkFrame(group_widget_frame, fg_color="transparent")
        joints_container.grid(row=0, column=0, padx=10, pady=3, sticky="ew")
        joints_container.grid_columnconfigure(1, weight=1)

        # 检查组是否为链式连接
        is_connected, _, _ = ProfileManager.is_chained_group(selected_group)
        
        # 创建标签，显示链状态
        chain_label = ctk.CTkLabel(group_header_frame, text="Chain:")
        chain_label.grid(row=0, column=0, padx=10, pady=2, sticky="w")
        
        chain_status_text = "success" if is_connected else "broken"
        chain_status_color = "#41d054" if is_connected else "#db0936"
        
        chain_status_label = ctk.CTkLabel(
            group_header_frame, 
            text=chain_status_text,
            text_color=chain_status_color,
        )
        chain_status_label.grid(row=0, column=1, padx=10, pady=2, sticky="w")
        
        ee_label = ctk.CTkLabel(group_header_frame, text="TOOL:")
        ee_label.grid(row=0, column=2, padx=(80,2), pady=2, sticky="w")

        # 创建复选框变量并添加回调函数
        self.ee_var = tk.BooleanVar(value=False)
        
        for tool in self.tools:
            if selected_group in tool["group"]:
                self.ee_var.set(True)
        
        ee_tickbox = ctk.CTkCheckBox(group_header_frame, 
                                     text="", 
                                     variable=self.ee_var, 
                                     command=lambda: self.on_tool_checkbox_changed(selected_group))
        ee_tickbox.grid(row=0, column=3, padx=2, pady=2, sticky="w")
        
        # 获取关节信息
        joints = ProfileManager.current_profile.get("joints", [])
        
        # 初始化当前组的滑块列表
        sliders = []
        
        # 为组中的每个关节创建控件
        for i, joint_idx in enumerate(joint_indices):
            if joint_idx >= len(joints):
                continue
                
            joint = joints[joint_idx]
            joint_type = joint.get("type", "unknown")
            
            # 根据关节类型创建不同的控件
            if joint_type.lower() == "revolute":
                # 获取关节限制
                limit = joint.get("limit", {})
                lower = limit.get("lower", -180)
                upper = limit.get("upper", 180)
                home = joint.get("home", 0)
                
                # 创建范围滑块
                slider = RangeSlider(
                    joints_container,
                    from_=lower,
                    to=upper,
                    home=home,
                    canvas_bg='#B3B3B3', 
                    slider_width=120
                )
                slider.grid(row=i, column=0, pady=2, sticky="ew")
                # 设置滑块回调函数
                slider.set_callback(lambda l, u, h, joint_index=joint_idx, joint_type=joint_type: self.on_joint_change(joint_index, joint_type, h))
                # 将滑块添加到列表
                sliders.append({"joint_index": joint_idx, "slider": slider})
                
            elif joint_type.lower() == "prismatic":
                # 获取关节限制
                limit = joint.get("limit", {})
                lower = limit.get("lower", 0)
                upper = limit.get("upper", 1)
                home = joint.get("home", 0)
                
                # 创建范围滑块
                slider = RangeSlider(
                    joints_container,
                    from_=lower,
                    to=upper,
                    home=home,
                    canvas_bg='#B3B3B3', 
                    slider_width=120,
                    number_of_steps=int((upper-lower)*1000/2)
                )
                slider.grid(row=i, column=0, pady=2, sticky="ew")
                # 设置滑块回调函数
                slider.set_callback(lambda l, u, h, joint_index=joint_idx, joint_type=joint_type: self.on_joint_change(joint_index, joint_type, h))
                # 将滑块添加到列表
                sliders.append({"joint_index": joint_idx, "slider": slider})
                
            elif joint_type.lower() == "fixed":
                # 创建一个带边框的框架来容纳固定关节标签
                fixed_frame = ctk.CTkFrame(
                    joints_container,
                    fg_color="transparent",
                    border_color="black",
                    border_width=1,
                    corner_radius=1
                )
                fixed_frame.grid(row=i, column=0, padx=(0, 10), pady=2, sticky="ew", columnspan=2)
                
                # 在框架中添加标签
                fixed_label = ctk.CTkLabel(
                    fixed_frame,
                    text="Fixed Joint",
                    font=("Arial", 12),
                    fg_color="transparent",
                )
                fixed_label.grid(row=0, column=0, pady=2, padx=10)
                
            else:
                # 创建一个带边框的框架来容纳其他类型关节标签
                other_frame = ctk.CTkFrame(
                    joints_container,
                    fg_color="transparent",
                    border_color="black",
                    border_width=1,
                    corner_radius=1
                )
                other_frame.grid(row=i, column=0, padx=(0, 10), pady=2, sticky="ew", columnspan=2)
                
                # 在框架中添加标签
                other_label = ctk.CTkLabel(
                    other_frame,
                    text=f"类型: {joint_type}",
                    font=("Arial", 12),
                    fg_color="transparent",
                )
                other_label.grid(row=0, column=0, pady=2, padx=10)
        
        # 如果是末端执行器，添加actuation类型下拉菜单
        actuation_frame = None
        if self.ee_var.get():
            actuation_frame = ctk.CTkFrame(group_widget_frame, fg_color="transparent")
            actuation_frame.grid(row=1, column=0, padx=10, pady=3, sticky="ew")
            actuation_frame.grid_columnconfigure(1, weight=1)
            
            # 添加标签
            actuation_label = ctk.CTkLabel(actuation_frame, text="Actuation:")
            actuation_label.grid(row=0, column=0, padx=(0,10), pady=2, sticky="w")
            
            # 获取当前工具的actuation值，如果没有则默认为第一个选项
            current_tool = None
            for tool in self.tools:
                if tool["group"] == selected_group:
                    current_tool = tool
                    break
            
            current_actuation = ProfileManager.DEFAULT_ACTUATION_TYPE
            if current_tool and "actuation" in current_tool:
                current_actuation = current_tool["actuation"]
            
            # 创建actuation类型下拉菜单
            actuation_var = tk.StringVar(value=current_actuation)
            actuation_dropdown = ctk.CTkOptionMenu(
                actuation_frame,
                variable=actuation_var,
                values=ProfileManager.ACTUATION_TYPES,
                command=lambda value: self.on_actuation_change(selected_group, value)
            )
            actuation_dropdown.grid(row=0, column=1, padx=10, pady=2, sticky="ew")
        
        # 确保 joint_widgets 字典已初始化
        if not hasattr(self, 'joint_widgets'):
            self.joint_widgets = {}
        
        # 保存当前组的控件信息
        self.joint_widgets[selected_group] = {
            "container": joints_container,
            "sliders": sliders
        }

    def on_joint_change(self, joint_index, joint_type, value):
        """
        滑块值改变时的回调函数，更新PyBullet机器人状态
        
        参数:
            joint_index: 关节索引
            joint_type: 关节类型（revolute或prismatic）
            value: 滑块当前值（角度或距离）
        """       
        try:
            # 根据关节类型处理数值
            if joint_type.lower() == "revolute":
                # 将角度转换为弧度
                angle_rad = math.radians(value)
                p.resetJointState(
                    self.robot_id,
                    joint_index,
                    angle_rad,
                    physicsClientId=self.client_id
                )
            elif joint_type.lower() == "prismatic":
                # prismatic关节使用实际距离值，不需要转换
                p.resetJointState(
                    self.robot_id,
                    joint_index,
                    value,  # 直接使用距离值
                    physicsClientId=self.client_id
                )
            
            # 更新3D视图
            self.update_view()
        except Exception as e:
            print(f"更新关节状态时出错: {str(e)}")

    def init_end_effector_interface(self):
        """初始化终端执行器界面"""
        # 清除现有的终端执行器框架
        for frame in self.end_effector_frames:
            frame.destroy()
        
        self.show_groups_frame()

    def on_tool_checkbox_changed(self, group_name):
        """
        当工具复选框状态改变时调用的回调函数
        根据复选框状态添加或移除末端执行器
        
        参数:
            group_name: 选中的组名
        """
        # 获取复选框状态
        is_checked = self.ee_var.get()
        
            
        # 如果新添加了工具，设置默认actuation类型
        if is_checked:
            is_leaf, chain_str = ProfileManager.is_leaf_group(group_name)
            if not is_leaf:
                tk.messagebox.showerror("错误", f"Group '{group_name}' is not a leaf group, cannot be set as end effector.\n\nChain structure analysis:\n{chain_str}")
            else:
                # 直接添加一个新工具
                new_tool = {
                    "group": group_name,
                    "ee_offset": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                    "actuation": ProfileManager.DEFAULT_ACTUATION_TYPE
                }
                self.tools.append(new_tool)
        else:
            # 当复选框未选中时，移除对应组的工具
            self.tools = [tool for tool in self.tools if tool["group"] != group_name]
        
        # 重新更新关节控件以显示/隐藏actuation下拉菜单
        self.update_joint_widgets(group_name)

    def on_actuation_change(self, group_name, actuation_type):
        """
        当actuation类型改变时调用的回调函数
        
        参数:
            group_name: 组名
            actuation_type: 选中的actuation类型
        """
        # 找到对应的工具并更新actuation类型
        for tool in self.tools:
            if tool["group"] == group_name:
                tool["actuation"] = actuation_type
                break

    def on_tcp_entry_change(self, event, offset_index, group_name):
        """
        当TCP偏移输入框值改变时调用的回调函数
        
        参数:
            event: 事件对象
            offset_index: 偏移量索引 (0-5: X, Y, Z, R, P, Y)
            group_name: 组名
        """
        try:
            # 获取输入框的值
            new_value = float(event.widget.get() or 0.0)
            
            # 找到对应的工具并更新ee_offset
            for tool in self.tools:
                if tool["group"] == group_name:
                    # 确保ee_offset列表存在并且有足够的元素
                    if "ee_offset" not in tool:
                        tool["ee_offset"] = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
                    elif len(tool["ee_offset"]) < 6:
                        # 扩展列表到6个元素
                        tool["ee_offset"].extend([0.0] * (6 - len(tool["ee_offset"])))
                    
                    # 更新指定索引的值
                    tool["ee_offset"][offset_index] = new_value
                    
                    break
                    
        except ValueError:
            # 如果输入的不是有效数字，忽略这次更新
            pass

    def show_groups_frame(self):
        """显示主要设置界面"""
        self.end_effector_frame.grid_forget()
        self.group_frame.grid(row=0, column=0, sticky="nsew")
        
        # 更新选项卡状态
        self.main_underline.grid()
        self.end_effector_underline.grid_remove()

    def show_end_effector_frame(self):
        """显示终端执行器界面"""
        self.group_frame.grid_forget()
        self.end_effector_frame.grid(row=0, column=0, sticky="nsew")
        
        # 更新选项卡状态
        self.main_underline.grid_remove()
        self.end_effector_underline.grid()
        
        # 清除现有的终端执行器框架
        for frame in self.end_effector_frames:
            frame.destroy()
        self.end_effector_frames = []
        
        # 如果没有工具，显示提示信息
        if not self.tools:
            no_tool_frame = ctk.CTkFrame(self.end_effector_frame, fg_color="transparent")
            no_tool_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
            
            no_tool_label = ctk.CTkLabel(
                no_tool_frame,
                text="未设置任何工具，请在GROUPS选项卡中选择组并勾选TOOL选项",
                wraplength=300,
                justify="center",
                text_color="#DBDBDB"
            )
            no_tool_label.grid(row=0, column=0, padx=10, pady=20)
            
            self.end_effector_frames.append(no_tool_frame)
            return
        
        # 为每个工具(组)创建配置框架
        for i, tool in enumerate(self.tools):
            # 获取组数据
            group_data = ProfileManager.get_group_by_name(tool["group"])
            if not group_data:
                continue
            
            # 创建工具框架
            tool_frame = ctk.CTkFrame(self.end_effector_frame, fg_color="#DBDBDB")
            tool_frame.grid(row=i, column=0, padx=5, pady=(10,5), sticky="ew")
            tool_frame.grid_columnconfigure(0, weight=1)
            
            # 创建头部框架用于显示组信息
            header_frame = ctk.CTkFrame(tool_frame, fg_color="transparent")
            header_frame.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
            
            # 创建标题标签
            title_label = ctk.CTkLabel(header_frame, text="TCP offset")
            title_label.grid(row=0, column=0, padx=(5,10), pady=5, sticky="w")

            group_frame = ctk.CTkFrame(header_frame, width=20, height=20, fg_color=group_data["color"], corner_radius=1)
            group_frame.grid(row=0, column=1, padx=(5,0), pady=5)
            group_frame.grid_propagate(False)
            
            group_label = ctk.CTkLabel(group_frame, text=tool["group"], width=20, height=20, fg_color="transparent")
            group_label.grid(row=0, column=0, sticky="nsew")

            parent_group = ProfileManager.get_parent_group(tool["group"])
            if parent_group:
                vertical_line = ctk.CTkFrame(header_frame, width=10, height=2, fg_color=group_data["color"])
                vertical_line.grid(row=0, column=2, pady=5)

                parent_frame = ctk.CTkFrame(header_frame, width=20, height=20, fg_color=parent_group["color"], corner_radius=1)
                parent_frame.grid(row=0, column=3, pady=5)
                parent_frame.grid_propagate(False)
                
                parent_label = ctk.CTkLabel(parent_frame, text=parent_group["name"], width=20,height=20, fg_color="transparent")
                parent_label.grid(row=0, column=0, sticky="nsew")

            # 创建关节容器框架
            joints_container = ctk.CTkFrame(tool_frame, fg_color="transparent")
            joints_container.grid(row=1, column=0, padx=5, pady=5, sticky="ew")
            joints_container.grid_columnconfigure(0, weight=1)
            
            # 创建TCP偏移量输入框架
            tcp_frame = ctk.CTkFrame(joints_container, fg_color="transparent")
            tcp_frame.grid(row=0, column=0, pady=5, sticky="ew")
            tcp_frame.grid_columnconfigure((1,3,5), weight=1)

            # 获取工具的ee_offset值，如果不存在则使用默认值
            ee_offset = tool.get("ee_offset", [0.0, 0.0, 0.0, 0.0, 0.0, 0.0])

            # 创建XYZ输入框（同一行）
            xyz_labels = ["X:", "Y:", "Z:"]
            self.tcp_entries = {}

            for i, label in enumerate(xyz_labels):
                # 创建标签
                label_widget = ctk.CTkLabel(tcp_frame, text=label, anchor="e")
                label_widget.grid(row=0, column=i*2, padx=5, pady=5, sticky="e")

                # 创建输入框并设置默认值
                entry = ctk.CTkEntry(tcp_frame, width=55, placeholder_text="0.0")
                entry.grid(row=0, column=i*2+1, padx=(3,5), pady=5, sticky="w")
                entry.insert(0, f"{ee_offset[i]:.4f}")
                
                # 绑定实时更新事件
                entry.bind("<KeyRelease>", lambda event, idx=i, group=tool["group"]: self.on_tcp_entry_change(event, idx, group))
                
                # 存储输入框引用
                self.tcp_entries[label] = entry

            # 创建RPY输入框（同一行）
            rpy_labels = ["R:", "P:", "Y:"]

            for i, label in enumerate(rpy_labels):
                # 创建标签
                label_widget = ctk.CTkLabel(tcp_frame, text=label, anchor="e")
                label_widget.grid(row=1, column=i*2, padx=5, pady=5, sticky="e")

                # 创建输入框并设置默认值
                entry = ctk.CTkEntry(tcp_frame, width=55, placeholder_text="0.0")
                entry.grid(row=1, column=i*2+1, padx=(3,5), pady=5, sticky="w")
                entry.insert(0, f"{ee_offset[i+3]:.4f}")
                
                # 绑定实时更新事件
                entry.bind("<KeyRelease>", lambda event, idx=i+3, group=tool["group"]: self.on_tcp_entry_change(event, idx, group))
                
                # 存储输入框引用
                self.tcp_entries[label] = entry
            
            self.end_effector_frames.append(tool_frame)

    def setup_button_frame(self):
        """设置按钮框架"""
        self.button_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.button_frame.grid(row=4, column=0, padx=20, pady=0, sticky="ew")
        self.button_frame.grid_columnconfigure(0, weight=1)
        
        self.save_button = ctk.CTkButton(self.button_frame, text="Save Profile", 
                                       command=self.save_profile,
                                       hover_color="#41d054")
        self.save_button.grid(row=0, column=1)

    def upload_urdf(self):
        """浏览并选择URDF/XACRO文件，支持单个或多个选择"""
        filenames = filedialog.askopenfilenames(
            filetypes=[
                ("Robot Description Files", "*.urdf *.xacro"),
                ("URDF files", "*.urdf"),
                ("XACRO files", "*.xacro"),
                ("All files", "*.*")
            ]
        )
        if filenames:
            try:
                # 转换为列表以便检查
                filenames_list = list(filenames)
                
                # 获取第一个文件所在的目录
                base_dir = os.path.dirname(filenames_list[0])
                converted_urdf_path = os.path.join(base_dir, "_converted.urdf")
                
                # 确定处理方式
                if len(filenames_list) == 1:
                    filename = filenames_list[0]
                    # 单个文件处理
                    if filename.endswith('.xacro'):
                        result, error_msg = xacro_to_urdf(filename, converted_urdf_path)
                        if result == -1:
                            raise Exception(error_msg)
                        self.urdf_path = converted_urdf_path
                    else:
                        # 直接使用URDF文件
                        self.urdf_path = filename
                else:
                    # 多个文件处理,检查是否所有文件都是xacro文件
                    if not all(f.endswith('.xacro') for f in filenames_list):
                        raise Exception("多选模式下只能选择XACRO文件")
                        
                    xacro_includes_to_urdf(filenames_list, converted_urdf_path)
                    self.urdf_path = converted_urdf_path
                    
                self.urdf_entry.delete(0, tk.END)
                self.urdf_entry.insert(0, self.urdf_path)
                
                # 在专用客户端中加载URDF
                self.robot_id = self.physics_engine.load_urdf(self.urdf_path, 'profile_viewer')
                if self.robot_id is None:
                    raise Exception("加载URDF失败")
                
                # 添加这一行：计算最佳视图
                self.calculate_best_view()
                
                result = urdf_to_json(self.urdf_path, include_visuals=False, include_collisions=False)

                self.name_var.set(result["name"])
                self.used_group_names.clear()
                self.used_colors.clear()

                ProfileManager.current_profile["joints"] = result["joints"]
                ProfileManager.current_profile["links"] = result["links"]
                ProfileManager.current_profile["name"] = result["name"]
                ProfileManager.current_profile["groups"] = {}
                
                visual_shape_data = p.getVisualShapeData(self.robot_id, physicsClientId=self.client_id)
                default_colors = {item[1]: item[7] for item in visual_shape_data}
                self.default_colors = rgba_to_hex(default_colors[0])
                
                self.add_new_group()
                self.visualise_groups(ProfileManager.current_profile["joints"])
                self.update_view()
                
            except Exception as e:
                tk.messagebox.showerror("错误", f"加载URDF/XACRO文件失败: {str(e)}")

    def enumerate_ports(self):
        """获取可用串口列表"""
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    def refresh_ports(self):
        """刷新串口列表"""
        self.ports = self.enumerate_ports()
        self.port_dropdown.configure(values=self.ports)
        if self.ports:
            self.port_dropdown.set(self.ports[0])
        else:
            self.port_dropdown.set("No ports available")

    def on_connect(self):
        selected_port = self.port_var.get()
        robot_type = self.robot_type_var.get()

        # 根据机器人类型选择协议类
        protocol_class = SerialProtocol if robot_type == "PWM/I2C" else CanProtocol

        if protocol_class.connect(selected_port):
            if robot_type == "PWM/I2C":
                time.sleep(0.1)  # 等待设备完全启动
            self.connect_button.configure(state=ctk.DISABLED)
            self.disconnect_button.configure(state=ctk.NORMAL)
            # 更新连接状态
            self.app.controller_frame.update_connection_status()
        else:
            messagebox.showerror("Connection Error", f"Failed to connect to {selected_port}")

    def on_disconnect(self):
        robot_type = self.robot_type_var.get()

        # 根据机器人类型选择协议类
        protocol_class = SerialProtocol if robot_type == "PWM/I2C" else CanProtocol

        if protocol_class.disconnect():
            self.connect_button.configure(state=ctk.NORMAL)
            self.disconnect_button.configure(state=ctk.DISABLED)
            # 更新连接状态
            self.app.controller_frame.update_connection_status()

    def load_profile(self):
        """加载配置文件并更新界面"""
        self.is_creating_new_profile = False

        self.name_var.set(ProfileManager.current_profile["name"])
        self.id_var.set(ProfileManager.current_profile["id"])
        self.urdf_path = ProfileManager.current_profile["urdf_path"]
        self.groups = ProfileManager.current_profile["groups"]
        self.tools = ProfileManager.current_profile.get("end_effector", [])
        self.home_positions = []
        # 获取所有关节的home位置并设置到3D视图
        for joint in ProfileManager.current_profile.get("joints", []):
            self.home_positions.append(joint.get("home", 0))
        
        for tool in self.tools:
            if "ee_offset" in tool:
                # 更新robot_state中的tcp_offset
                self.robot_state.update_state("tcp_offset", np.array(tool["ee_offset"]), sender=self)
        
        self.urdf_entry.configure(state="normal")
        self.urdf_entry.delete(0, tk.END)
        self.urdf_entry.insert(0, self.urdf_path)
        self.urdf_entry.configure(state="disabled")
        
        self.robot_type_var.set(ProfileManager.current_profile["robot_type"])
        
        if self.urdf_path and os.path.exists(self.urdf_path):
            self.robot_id = self.physics_engine.load_urdf(self.urdf_path, 'profile_viewer')
            if self.robot_id is None:
                raise Exception("加载URDF失败")
            
            self.calculate_best_view()
        
        visual_shape_data = p.getVisualShapeData(self.robot_id, physicsClientId=self.client_id)
        default_colors = {item[1]: item[7] for item in visual_shape_data}
        self.default_colors = rgba_to_hex(default_colors[0])
            
        self.load_groups()
        self.visualise_groups(ProfileManager.current_profile["joints"])

        self.update_group_buttons()
        self.update_group_children_widgets()
        self.update_view(joint_angles=self.home_positions)

        # 初始化终端执行器部分
        self.init_end_effector_interface()

        self.enable_connection_widgets()
        self.disable_profile_widgets()
        self.bespoke_widgets(ProfileManager.current_profile['name'])
        self.select_group(list(self.groups.keys())[0])

    def load_new_profile(self):
        """加载新的配置文件模板"""
        # 调用ProfileManager创建新配置文件，获取结果和状态码
        success, result = ProfileManager.create_new_profile()
        
        if not success:
            # 根据不同的错误码显示相应的错误信息
            if result == -404:
                tk.messagebox.showerror(
                    "创建失败", 
                    "无法创建新配置文件：软件未激活。\n请在设置页面的License选项卡中激活软件。"
                )
            elif result == -101:
                tk.messagebox.showerror(
                    "创建失败", 
                    "无法创建新配置文件：已达到最大配置文件数量限制。\n请删除部分配置文件后重试，或升级您的许可证。"
                )
            elif result == -202:
                tk.messagebox.showerror(
                    "创建失败", 
                    "无法创建新配置文件：系统异常。\n请重试或联系技术支持。"
                )
            else:
                tk.messagebox.showerror(
                    "创建失败", 
                    f"无法创建新配置文件：未知错误 ({result})。"
                )
            return
            
        # result为新生成的配置文件ID
        new_profile_id = result
        self.is_creating_new_profile = True
        
        # 清除关节标签
        for joint_ui in self.joint_labels:
            joint_ui["frame"].destroy()
            joint_ui["index_label"].destroy()
            joint_ui["updown_button"].destroy()
        self.joint_labels.clear()

        self.used_group_names.clear()
        self.used_colors.clear()
        
        # 清除现有的组按钮
        for button in self.group_buttons:
            button.destroy()
        self.group_buttons.clear()

        # 初始化工具列表
        self.tools = []

        # 初始化终端执行器部分
        self.init_end_effector_interface()

        self.enable_profile_widgets()
        self.id_var.set(new_profile_id)  # 使用从ProfileManager返回的新ID
        self.name_var.set("")
        self.urdf_entry.delete(0, tk.END)
        self.disable_connection_widgets()
        self.bespoke_widgets(ProfileManager.current_profile["name"])
        
        # 清空3D视图
        if hasattr(self, 'physics_engine'):
            if self.client_id is not None and self.robot_id is not None:
                p.removeBody(self.robot_id, physicsClientId=self.client_id)
                # 重置客户端中的机器人ID
                self.physics_engine._clients['profile_viewer']['robot_id'] = None
                self.physics_engine._clients['profile_viewer']['urdf_path'] = None
        
        # 更新视图
        self.update_view()

    def save_profile(self):
        """保存配置文件，包括关节规格和组信息"""
        if not self.name_var.get():
            tk.messagebox.showerror("错误", "请填写机器人名称")
            return
        
        try:
            # 更新关节限制
            if hasattr(self, 'joint_widgets'):
                for _, widgets in self.joint_widgets.items():
                    for slider_data in widgets["sliders"]:
                        joint_index = slider_data["joint_index"]
                        slider = slider_data["slider"]
                        joint_values = slider.get_values()
                        joint_name = ProfileManager.current_profile["joints"][joint_index]["name"]
                        ProfileManager.update_joint_limits(
                            joint_name,
                            upper_limit=joint_values["upper"],
                            lower_limit=joint_values["lower"],
                            home=joint_values["home"]
                        )
        
            # 获取组字典
            groups_dict = ProfileManager.load_groups()                
            
            # 更新当前配置文件
            ProfileManager.current_profile.update({
                "name": self.name_var.get(),
                "urdf_path": self.urdf_entry.get(),
                "info_file": f"config/{self.name_var.get().lower().replace(' ', '_')}.info",
                "robot_type": self.robot_type_var.get(),
                "groups": groups_dict,
                "end_effector": self.tools
            })

            # 初始化校准偏移数组 - 根据需要校准的关节数量确定大小
            calibration_joint_count = len(ProfileManager.get_main_joints())
            if "calibration_offsets" not in ProfileManager.current_profile or len(ProfileManager.current_profile["calibration_offsets"]) != calibration_joint_count:
                # 如果不存在校准偏移或数量不匹配，则初始化为二维数组 [[min, max], ...]
                ProfileManager.current_profile["calibration_offsets"] = [[0.0, 0.0] for _ in range(calibration_joint_count)]
            
            # 初始化关节速度数组 - 根据需要控制的关节数量确定大小
            if "joint_speeds" not in ProfileManager.current_profile or len(ProfileManager.current_profile["joint_speeds"]) != calibration_joint_count:
                # 如果不存在关节速度或数量不匹配，则初始化为全1.0数组（默认速度）
                ProfileManager.current_profile["joint_speeds"] = [1.0] * calibration_joint_count  

            # 使用 ProfileManager 保存配置文件
            success, status_code = ProfileManager.save_profile(ProfileManager.current_profile)
            if success:
                self.is_editing_profile = False
                self.is_creating_new_profile = False
                
                # 更新下拉菜单选项
                profile_names = ProfileManager.get_all_profile_names()
                self.app.profile_dropdown.configure(values=profile_names)
                self.app.profile_var.set(ProfileManager.current_profile["name"])
                
                # 重新加载当前配置文件
                self.app.change_robot_profile(ProfileManager.current_profile["name"])
                
                tk.messagebox.showinfo("成功", "配置文件已保存")
            else:
                # 根据状态码显示相应的错误信息
                if status_code == -404:
                    error_msg = "保存失败：软件未激活。\n请在设置页面的License选项卡中激活软件。"
                elif status_code == -101:
                    error_msg = "保存失败：已达到最大配置文件数量限制。\n请删除部分配置文件后重试，或升级您的许可证。"
                elif status_code == -202:
                    error_msg = "保存失败：数据无效。\n请检查配置文件数据或联系技术支持。"
                else:
                    error_msg = f"保存失败：未知错误 ({status_code})。"
                
                tk.messagebox.showerror("错误", error_msg)
                
        except ValueError as e:
            tk.messagebox.showerror("错误", f"保存关节配置时出错：{str(e)}")
            return

    def export_info(self):
        """导出当前机器人配置文件"""
        try:
            
            # 创建导出文件对话框
            default_filename = f"{ProfileManager.current_profile['name'].lower().replace(' ', '_')}.info"
            export_path = filedialog.asksaveasfilename(
                defaultextension=".info",
                initialfile=default_filename,
                filetypes=[("Info files", "*.info"), ("All files", "*.*")]
            )
            
            if export_path:
                # 使用 ProfileManager 导出配置文件
                if ProfileManager.export_profile_info(ProfileManager.current_profile, export_path):
                    tk.messagebox.showinfo("成功", f"配置文件已导出到：\n{export_path}")
                else:
                    tk.messagebox.showerror("错误", "导出配置文件失败")
                
        except Exception as e:
            tk.messagebox.showerror("错误", f"导出配置文件时发生错误：{str(e)}")

    def delete_profile(self):
        """删除当前配置文件"""
        current_profile_name = self.app.profile_var.get()
        
        if tk.messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the profile '{current_profile_name}'?"):
            try:
                # 获取当前配置文件的 ID
                current_profile_data = ProfileManager.get_profile_by_name(current_profile_name)
                if not current_profile_data:
                    raise ValueError(f"找不到配置文件: {current_profile_name}")

                if ProfileManager.delete_profile(current_profile_data["id"]):
                    # 重新加载配置文件数据
                    ProfileManager.load_profiles()
                    
                    # 更新下拉菜单选项
                    profile_names = ProfileManager.get_all_profile_names()
                    self.app.profile_dropdown.configure(values=profile_names)
                    self.app.profile_var.set(ProfileManager.current_profile["name"])
                    
                    # 重新加载当前配置文件
                    self.app.change_robot_profile(ProfileManager.current_profile["name"])
                    
                    tk.messagebox.showinfo("Success", "Profile deleted successfully")
                else:
                    tk.messagebox.showerror("Error", "Failed to delete profile")
                
            except Exception as e:
                tk.messagebox.showerror("Error", f"Failed to delete profile: {str(e)}")

    def visualise_groups(self, urdf_data):
        """加载URDF数据并显示关节信息"""
        try:
            for joint_ui in self.joint_labels:
                joint_ui["frame"].destroy()
                joint_ui["index_label"].destroy()
                joint_ui["updown_button"].destroy()
            self.joint_labels.clear()

            for i, joint in enumerate(urdf_data):
                # 创建主 joint frame
                joint_frame = ctk.CTkFrame(
                    self.joint_scroll_frame,
                    fg_color="#DBDBDB",
                    corner_radius=0,
                    border_color="#B3B3B3",
                    border_width=1
                )
                joint_frame.grid(row=i, column=0, pady=1, sticky="ew")
                
                # 左侧框架 - 显示索引
                left_frame = ctk.CTkFrame(
                    joint_frame,
                    fg_color="transparent",
                )
                left_frame.grid(row=0, column=0, padx=2, pady=2)
                
                # 索引标签
                index_label = ctk.CTkLabel(
                    left_frame,
                    text=f"{i}",
                    width=20,
                    height=20,
                    anchor="center",
                    fg_color="gray"
                )
                index_label.grid(row=0, column=0, padx=2, pady=2)
                
                # 中间框架 - 显示关节名称和类型 (原右侧框架)
                middle_frame = ctk.CTkFrame(
                    joint_frame,
                    fg_color="#DBDBDB",
                    corner_radius=0,
                    width=210,  # 固定宽度
                    height=30   # 固定高度
                )
                middle_frame.grid(row=0, column=1, pady=2)
                middle_frame.grid_propagate(False)  # 禁止框架自动调整大小
                middle_frame.grid_columnconfigure(0, weight=1)
                
                # 关节名称和类型标签
                name_label = ctk.CTkLabel(
                    middle_frame,
                    text=f"{joint['name']} ({joint['type']})",
                    anchor="w",
                    fg_color="transparent"
                )
                name_label.grid(row=0, column=0, padx=(15,0), pady=2, sticky="w")

                # 新的右侧框架 - 放置按钮
                right_frame = ctk.CTkFrame(
                    joint_frame,
                    fg_color="#DBDBDB",
                    corner_radius=0
                )
                right_frame.grid(row=0, column=2, pady=2, sticky="e")
                
                # 向下箭头按钮
                updown_button = ctk.CTkButton(
                    right_frame,
                    text="",
                    image=self.up_icon,
                    width=20,
                    height=20,
                    fg_color="transparent",
                    hover_color="#B3B3B3",
                    command=lambda idx=i: self.toggle_joint_group(idx)
                )
                updown_button.grid(row=0, column=0, padx=5, pady=2)
                
                # 保存标签引用
                self.joint_labels.append({
                    'frame': joint_frame,
                    'index_label': index_label,
                    'updown_button': updown_button
                })

        except Exception as e:
            print(f"Error loading URDF data: {str(e)}")

    def enable_connection_widgets(self):
        """启用连接相关的部件"""
        self.port_dropdown.configure(state="normal")
        self.connect_button.configure(state="normal")
        self.refresh_button.configure(state="normal")
        self.export_button.configure(state="normal")
        self.delete_button.configure(state="normal")
        
        # 使用协议类检查连接状态
        robot_type = self.robot_type_var.get()
        protocol_class = SerialProtocol if robot_type == "PWM/I2C" else CanProtocol
        
        if protocol_class.is_connected():
            self.disconnect_button.configure(state="normal")
        else:
            self.disconnect_button.configure(state="disabled")

    def disable_connection_widgets(self):
        """禁用连接相关的部件"""
        self.port_dropdown.configure(state="disabled")
        self.connect_button.configure(state="disabled")
        self.disconnect_button.configure(state="disabled")
        self.refresh_button.configure(state="disabled")
        self.export_button.configure(state="disabled")
        self.delete_button.configure(state="disabled")

    def enable_profile_widgets(self):
        """启用配置文件相关的部件"""
        self.name_entry.configure(state="normal")
        self.type_option.configure(state="normal")
        self.urdf_entry.configure(state="normal")
        self.upload_urdf_button.configure(state="normal")
        self.save_button.configure(state="normal")

        if hasattr(self, 'add_group_button'):
            self.add_group_button.grid(row=0, column=len(self.group_buttons))
        if hasattr(self, 'delete_group_button'):
            self.delete_group_button.grid(row=0, column=len(self.group_buttons)+1)

    def disable_profile_widgets(self):
        """禁用配置文件相关的部件"""
        self.name_entry.configure(state="disabled")
        self.type_option.configure(state="disabled")
        self.urdf_entry.configure(state="disabled")
        self.upload_urdf_button.configure(state="disabled")
        self.save_button.configure(state="disabled")

        if hasattr(self, 'add_group_button'):
            self.add_group_button.grid_remove()
        if hasattr(self, 'delete_group_button'):
            self.delete_group_button.grid_remove()

    def bespoke_widgets(self, profile_name):
        # 如果是MINIMA配置文件，隐藏特定按钮和框架，显示工具选择
        if ProfileManager.is_profile_official(profile_name):
            self.edit_button.grid_remove()
            self.delete_button.grid_remove()
            self.save_button.grid_remove()
            self.specqr_label.grid()  # 显示 QR 码
            self.upper_right_frame.grid()  # 显示右侧框架
        else:
            self.edit_button.grid()
            self.delete_button.grid()
            self.save_button.grid()
            self.specqr_label.grid_remove()  # 隐藏 QR 码
            self.upper_right_frame.grid_remove()  # 隐藏右侧框架

    def on_edit(self):
        """处理编辑按钮点击事件"""
        self.is_editing_profile = True
        self.is_creating_new_profile = False

        self.enable_profile_widgets()
        self.disable_connection_widgets()

        self.save_button.configure(state="normal")

    def init_render_param(self):
        """初始化PyBullet渲染器"""
        # 初始设置默认相机参数（后续会基于模型自动调整）
        self.camera_distance = 0.45
        self.camera_yaw = -15
        self.camera_pitch = -15
        self.camera_target = [0.02, 0, 0.1]
        
        # 记录鼠标状态
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.is_dragging = False
        
        # 添加平移状态变量
        self.last_pan_x = 0
        self.last_pan_y = 0
        self.is_panning = False

    def calculate_best_view(self):
        """根据机器人模型自动计算最佳视图参数"""
        if self.robot_id is None:
            return
        
        try:
            # 获取机器人的轴对齐边界框
            aabb_min, aabb_max = p.getAABB(self.robot_id, physicsClientId=self.client_id)
            
            # 计算边界框中心作为相机目标点
            self.camera_target = [
                (aabb_min[0] + aabb_max[0]) / 2,
                (aabb_min[1] + aabb_max[1]) / 2,
                (aabb_min[2] + aabb_max[2]) / 2
            ]
            
            # 计算边界框对角线长度
            diagonal = math.sqrt(
                (aabb_max[0] - aabb_min[0])**2 +
                (aabb_max[1] - aabb_min[1])**2 +
                (aabb_max[2] - aabb_min[2])**2
            )
            
            # 根据对角线长度计算合适的相机距离（添加一个缩放因子以确保机器人完全可见）
            self.camera_distance = diagonal * 1.5
            
            # 保持摄像机的视角参数（或者可以设置为更合适的值）
            self.camera_yaw = 30
            self.camera_pitch = -25
            
            # 更新视图
            self.update_view()
        except Exception as e:
            print(f"计算最佳视图失败: {str(e)}")

    def update_view(self, joint_angles=None):
        """更新3D视图"""
        if joint_angles is not None:
            # 将joint_angles转换为numpy数组并转换为弧度
            joint_angles_array = np.array(joint_angles, dtype=float)
            joint_angles_rad = np.radians(joint_angles_array)
            for i, angle in enumerate(joint_angles_rad):
                p.resetJointState(self.robot_id, i, angle, physicsClientId=self.client_id)

        # 获取画布尺寸
        width = self.view_canvas.winfo_width()
        height = self.view_canvas.winfo_height()
        
        if width <= 1 or height <= 1:
            return
        
        # 设置相机视角
        view_matrix = p.computeViewMatrixFromYawPitchRoll(
            cameraTargetPosition=self.camera_target,
            distance=self.camera_distance,
            yaw=self.camera_yaw,
            pitch=self.camera_pitch,
            roll=0,
            upAxisIndex=2,
            physicsClientId=self.client_id
        )
        
        proj_matrix = p.computeProjectionMatrixFOV(
            fov=60,
            aspect=float(width)/float(height),
            nearVal=0.1,
            farVal=100.0
        )
        
        # 渲染场景
        (_, _, px, _, _) = p.getCameraImage(
            width=width,
            height=height,
            viewMatrix=view_matrix,
            projectionMatrix=proj_matrix,
            renderer=p.ER_BULLET_HARDWARE_OPENGL,
            physicsClientId=self.client_id
        )
        
        # 转换为PIL图像并显示在画布上
        px_bytes = np.ascontiguousarray(px, dtype=np.uint8).tobytes()
        image = Image.frombytes('RGBA', (width, height), px_bytes)
        photo = ImageTk.PhotoImage(image)
        #image = Image.fromarray(px)
        #photo = ImageTk.PhotoImage(image)
        
        # 更新画布
        self.view_canvas.delete("all")
        self.view_canvas.create_image(0, 0, image=photo, anchor="nw")
        self.view_canvas.image = photo  # 保持引用

    def on_mouse_down(self, event):
        """处理鼠标按下事件"""
        self.last_mouse_x = event.x
        self.last_mouse_y = event.y
        self.is_dragging = True

    def on_mouse_drag(self, event):
        """处理鼠标拖动事件"""
        if not self.is_dragging:
            return
        
        dx = event.x - self.last_mouse_x
        dy = event.y - self.last_mouse_y
        
        self.camera_yaw += dx * 0.5
        self.camera_pitch = max(-89, min(89, self.camera_pitch - dy * 0.5))
        
        self.last_mouse_x = event.x
        self.last_mouse_y = event.y
        
        self.update_view()

    def on_mouse_up(self, event):
        """处理鼠标释放事件"""
        self.is_dragging = False

    def on_mouse_wheel(self, event):
        """处理鼠标滚轮事件"""
        if event.num == 5 or event.delta < 0:  # 向下滚动
            self.camera_distance = min(3.0, self.camera_distance * 1.1)  # 限制最大距离为3.0
        else:  # 向上滚动
            self.camera_distance = max(0.3, self.camera_distance * 0.9)  # 限制最小距离为0.3
        
        self.update_view()

    def on_middle_mouse_down(self, event):
        """处理鼠标中键按下事件"""
        self.last_pan_x = event.x
        self.last_pan_y = event.y
        self.is_panning = True
        
    def on_middle_mouse_drag(self, event):
        """处理鼠标中键拖动事件（平移视图）"""
        if not self.is_panning:
            return
            
        # 计算拖动距离
        dx = event.x - self.last_pan_x
        dy = event.y - self.last_pan_y
        
        # 调整平移系数，使其与相机距离成比例
        pan_scale = self.camera_distance * 0.001
        
        # 计算相机坐标系下的右方向向量和上方向向量
        yaw_rad = math.radians(self.camera_yaw)
        pitch_rad = math.radians(self.camera_pitch)
        
        # 右方向向量（考虑相机yaw角）
        right_x = math.cos(yaw_rad)
        right_y = math.sin(yaw_rad)
        
        # 上方向向量（考虑相机pitch角和yaw角）
        up_z = math.cos(pitch_rad)
        up_xy_scale = math.sin(pitch_rad)
        up_x = -up_xy_scale * math.sin(yaw_rad)
        up_y = up_xy_scale * math.cos(yaw_rad)
        
        # 根据鼠标拖动调整相机目标位置
        self.camera_target[0] += (-right_x * dx - up_x * dy) * pan_scale
        self.camera_target[1] += (-right_y * dx - up_y * dy) * pan_scale
        self.camera_target[2] += -up_z * dy * pan_scale
        
        # 更新上次鼠标位置
        self.last_pan_x = event.x
        self.last_pan_y = event.y
        
        # 更新视图
        self.update_view()
        
    def on_middle_mouse_up(self, event):
        """处理鼠标中键释放事件"""
        self.is_panning = False

    def on_resize(self, event):
        """处理窗口大小改变事件"""
        self.update_view() 

    def update_group_buttons(self):
        """更新组按钮"""
        # 清除group_buttons_frame中的所有部件
        for widget in self.group_buttons_frame.winfo_children():
            widget.destroy()
        self.group_buttons.clear()
        
        # 获取组字典
        groups_dict = ProfileManager.load_groups()
        
        # 为每个组创建新按钮
        for i, (group_name, group_data) in enumerate(groups_dict.items()):
            group_color = group_data["color"]
            button = ctk.CTkButton(
                self.group_buttons_frame,
                text=group_name,
                width=25,
                height=25,
                fg_color=group_color,
                border_width=3,
                corner_radius=1,
                border_color=group_color,
                hover_color=group_color,
                command=lambda name=group_name: self.select_group(name)
            )
            button.grid(row=0, column=i, padx=(0,5), pady=5)
            self.group_buttons.append(button)

        # 添加新组的按钮
        self.add_group_button = ctk.CTkButton(
            self.group_buttons_frame,
            text="",
            image=self.plus_icon,
            width=20,
            height=20,
            fg_color="transparent",
            hover_color="#41d054",
            command=self.add_new_group
        )
        # 将添加按钮放入网格
        self.add_group_button.grid(row=0, column=len(self.group_buttons))
        
        # 添加删除组的按钮
        self.delete_group_button = ctk.CTkButton(
            self.group_buttons_frame,
            text="",
            image=self.minus_icon,
            width=20,
            height=20,
            fg_color="transparent",
            hover_color="#FF6B6B",
            command=self.delete_selected_group
        )
        # 将删除按钮放入网格
        self.delete_group_button.grid(row=0, column=len(self.group_buttons)+1)

    def select_group(self, group_name):
        """选择一个组"""
        # 首先重置所有链接的颜色为默认白色
        self.change_link_color(self.default_colors)  # 使用新函数重置颜色

        # 检查当前点击的按钮是否已经被选中
        for button in self.group_buttons:
            if button.cget("text") == group_name:
                if button.cget("border_color") == "#41d054":  # 如果已经选中
                    # 重置为原始颜色
                    button.configure(border_color=ProfileManager.get_group_by_name(group_name)["color"])
                    # 显示所有updown按钮
                    self.update_updown_buttons_visibility(None)

                    return
                break
        
        # 重置所有按钮的边框颜色为各自组的颜色
        for button in self.group_buttons:
            button_text = button.cget("text")
            button.configure(border_color=ProfileManager.get_group_by_name(button_text)["color"])
        
        # 设置选中按钮的边框颜色为高亮色
        for button in self.group_buttons:
            if button.cget("text") == group_name:
                button.configure(border_color="#41d054")
                break
        
        # 更新updown按钮的可见性
        self.update_updown_buttons_visibility(group_name)
        
        # 更新选中组的关节控件
        self.update_joint_widgets(group_name)

        # 更新链接颜色
        self.change_link_color(
            ProfileManager.get_group_by_name(group_name)["color"], 
            ProfileManager.get_group_by_name(group_name)["includes"]
        )

    def update_updown_buttons_visibility(self, selected_group):
        """
        更新updown按钮的可见性
        Args:
            selected_group: 选中的组名，如果为None则显示所有按钮
        """
        if selected_group is None:
            # 显示所有按钮
            for joint_ui in self.joint_labels:
                joint_ui["updown_button"].grid()
        else:
            # 获取组字典
            groups_dict = ProfileManager.load_groups()
            
            # 只显示选中组的成员和未分组的关节的按钮
            for i, joint_ui in enumerate(self.joint_labels):
                # 检查该关节是否属于其他组
                belongs_to_other_group = False
                for group_name, group_data in groups_dict.items():
                    if group_name != selected_group and i in group_data["includes"]:
                        belongs_to_other_group = True
                        break
                
                if belongs_to_other_group:
                    joint_ui["updown_button"].grid_remove()  # 隐藏按钮
                else:
                    joint_ui["updown_button"].grid()  # 显示按钮

    def load_groups(self):
        # 重置组相关的状态
        self.used_group_names.clear()
        self.used_colors.clear()
        
        # 使用ProfileManager加载组数据
        groups_dict = ProfileManager.load_groups()
        
        # 更新本地组数据和使用状态
        for name, group_data in groups_dict.items():
            if name in self.available_group_names:
                self.used_group_names.add(name)
            self.used_colors.add(group_data["color"])

    def add_new_group(self):
        """添加新的组"""
        new_group = ProfileManager.add_new_group(
            self.available_group_names,
            self.used_group_names,
            self.color_palette,
            self.used_colors
        )
        
        if not new_group:
            messagebox.showwarning(
                Config.current_lang.get("warning", "警告"),
                Config.current_lang.get("max_groups_reached", "已达到最大组数限制")
            )
            return
        
        # 更新本地状态
        new_group_name = new_group["name"]
        new_color = new_group["color"]
        
        # 更新已使用的组名和颜色集合
        self.used_group_names.add(new_group_name)
        self.used_colors.add(new_color)
        
        # 更新按钮显示
        self.update_group_buttons()
        

    def toggle_joint_group(self, joint_index):
        """
        切换关节的组归属状态
        """
        if not self.is_creating_new_profile and not self.is_editing_profile:
            return

        # 查找当前选中的组按钮
        group_name = None
        for button in self.group_buttons:
            if button.cget("border_color") == "#41d054":  # 检查高亮边框
                group_name = button.cget("text")
                break
        
        if not group_name:
            return  # 如果没有选中的组，直接返回
        
        # 获取当前关节的UI元素
        joint_ui = self.joint_labels[joint_index]
        group = ProfileManager.get_group_by_name(group_name)
        
        # 检查该关节是否已在组中
        if joint_index in group["includes"]:
            # 如果在组中，则移除
            ProfileManager.update_joint_in_group(group_name, joint_index, add=False)
            joint_ui["updown_button"].configure(image=self.up_icon)
            joint_ui["index_label"].configure(fg_color="gray")  # 重置颜色
            # 重置该关节的3D视图颜色为白色
            self.change_link_color(self.default_colors, [joint_index])
        else:
            # 如果不在组中，则添加
            ProfileManager.update_joint_in_group(group_name, joint_index, add=True)
            joint_ui["updown_button"].configure(image=self.down_icon)
            joint_ui["index_label"].configure(
                fg_color=group["color"]
            )
            # 更新该关节的3D视图颜色为组颜色
            self.change_link_color(group["color"], [joint_index])

        self.update_joint_widgets(group_name)

    def update_group_children_widgets(self):
        """
        更新所有组中子节点的视觉状态
        """
        # 首先重置所有关节的视觉状态为默认
        for joint_ui in self.joint_labels:
            joint_ui["index_label"].configure(fg_color="gray")
            joint_ui["updown_button"].configure(image=self.up_icon)
        
        # 获取组字典
        groups_dict = ProfileManager.load_groups()
        
        # 遍历每个组及其子节点
        for group_name, group_data in groups_dict.items():
            for joint_index in group_data["includes"]:
                if joint_index < len(self.joint_labels):
                    joint_ui = self.joint_labels[joint_index]
                    # 更新索引标签颜色为组颜色
                    joint_ui["index_label"].configure(fg_color=group_data["color"])
                    # 更新按钮图标为向下箭头
                    joint_ui["updown_button"].configure(image=self.down_icon)

    def change_link_color(self, hex_color, joint_indices=None):
        """
        Change the color of specified joint links
        
        Args:
            hex_color: Hex color code (e.g., "#FF0000")
            joint_indices: List of joint indices to change color, None for all joints
        """
        if not hasattr(self, 'physics_engine'):
            return
            
        if self.robot_id is None:
            return
            
        # Convert hex color to RGB values
        rgb = hex_to_rgb(hex_color)
        
        # Get joint indices if not specified
        if joint_indices is None:
            num_joints = p.getNumJoints(self.robot_id, physicsClientId=self.client_id)
            joint_indices = range(num_joints)
        
        # Change colors
        for joint_index in joint_indices:
            p.changeVisualShape(
                self.robot_id,
                joint_index,
                rgbaColor=[*rgb, 1.0],  # Add alpha=1
                physicsClientId=self.client_id
            )
        
        # Update the 3D view
        self.update_view()

    def delete_selected_group(self):
        """删除选中的组"""
        # 查找当前选中的组
        selected_group_name = None
        for button in self.group_buttons:
            if button.cget("border_color") == "#41d054":  # 检查高亮边框
                selected_group_name = button.cget("text")
                break
                
        if not selected_group_name:
            return  # 如果没有选中的组或组不存在，直接返回
            
        # 确认是否删除
        if messagebox.askyesno(
            Config.current_lang.get("confirm", "确认"),
            Config.current_lang.get("delete_group_confirm", f"确定要删除组 '{selected_group_name}' 吗？")
        ):
            # 重置属于该组的所有关节的颜色和状态
            for joint_index in ProfileManager.get_group_by_name(selected_group_name)["includes"]:
                if joint_index < len(self.joint_labels):
                    joint_ui = self.joint_labels[joint_index]
                    joint_ui["index_label"].configure(fg_color="gray")
                    joint_ui["updown_button"].configure(image=self.up_icon)
            
            # 重置3D视图中该组所有关节的颜色
            self.change_link_color(self.default_colors, ProfileManager.get_group_by_name(selected_group_name)["includes"])
            
            # 从已用组名和颜色集合中移除
            group_name_letter = selected_group_name
            if group_name_letter in self.used_group_names:
                self.used_group_names.remove(group_name_letter)
            
            if "color" in ProfileManager.get_group_by_name(selected_group_name):
                group_color = ProfileManager.get_group_by_name(selected_group_name)["color"]
                if group_color in self.used_colors:
                    self.used_colors.remove(group_color)
            
            # 调用ProfileManager的delete_group方法删除组
            ProfileManager.delete_group(selected_group_name)
            
            self.update_group_buttons()
            self.update_updown_buttons_visibility(None)

    def update(self, state):
        """
        更新机器人状态
        
        Args:
            state: 机器人状态字典
        """
        # 如果有末端执行器偏移量更新，则更新界面
        if self.tools:
            for tool in self.tools:
                if "ee_offset" in tool:
                    # 更新工具的偏移量
                    tool["ee_offset"] = state["tcp_offset"].tolist()

    def update_texts(self):
        self.frame_label.configure(text=Config.current_lang["robot_profile"])
        self.connection_label.configure(text=Config.current_lang["serial_connection"])
        self.connect_button.configure(text=Config.current_lang["connect"])
        self.disconnect_button.configure(text=Config.current_lang["disconnect"])
        self.type_label.configure(text=Config.current_lang["type"])
        self.name_label.configure(text=Config.current_lang["name"])
