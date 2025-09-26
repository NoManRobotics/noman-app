import os
import sys
import json
import time
import math
import copy
import traceback
import threading
import multiprocessing
import queue
import numpy as np
import customtkinter as ctk
import tkinter as tk
import pybullet as p
from PIL import Image
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText

from utils.config import Config
from utils.tooltip import ToolTip
from utils.resource_loader import ResourceLoader
from utils.math import rpy_to_quaternion, quaternion_to_rpy
from noman.profile_manager import ProfileManager
from noman.physics.bullet.physics_engine import PhysicsEngine
from .pybullet_gui import pybullet_gui_process

class SimulatorFrame(ctk.CTkFrame):
    def __init__(self, master, robot_state, app):
        super().__init__(master)
        self.master = master
        self.app = app
        self.operating_system = Config.operating_system

        self.physics_engine = PhysicsEngine.get_instance()
        self.robot_id = self.physics_engine.get_robot_id('default')
        self.client_id = self.physics_engine.get_client_id('default')
        self.client_name = 'default'
        
        self.is_simulating = False

        self.robot_state = robot_state
        self.robot_state.add_observer(self)

        self.marker_ids = []
        
        # Initialize multiprocessing communication
        self.robot_state_queue = None
        self.offline_params_queue = None
        self.shutdown_event = None
        self.gui_process = None

        self.grid(row=0, column=0, sticky="nsew")
        self.grid_columnconfigure(0, weight=1)

        self.main_group_includes = []
        self.tool_group_includes = []

        self.question_icon = self.load_icon("question_white.png", (15, 15))
        self.edit_icon = self.load_icon("edit.png", (15, 15))

        self.setup_banner()
        self.setup_engine()
        self.setup_robot_status()
        self.setup_shape_manager()
        self.setup_terminal()
        
        self.load_robot_profile()
        self.update_ui()

    def load_icon(self, filename, size):
        """Helper method to load an icon with the given filename and size"""
        path = ResourceLoader.get_asset_path(os.path.join("icons", filename))
        return ctk.CTkImage(Image.open(path).convert("RGBA"), size=size)

    def setup_banner(self):
        """设置横幅框架"""
        self.banner_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.banner_frame.grid(row=0, column=0, padx=10, pady=(10,0), sticky="ew")
        self.banner_frame.grid_columnconfigure(1, weight=1)

        # 左侧框架
        self.upper_left_frame = ctk.CTkFrame(self.banner_frame, fg_color="transparent")
        self.upper_left_frame.grid(row=0, column=0, sticky="w")

        # 框架标签
        self.frame_label = ctk.CTkLabel(self.upper_left_frame, text=Config.current_lang["simulator"], font=("Arial", 16), anchor='w')
        self.frame_label.grid(row=0, column=0, padx=10, pady=(8,0), sticky="w")

        separator = ctk.CTkFrame(self.upper_left_frame, height=2, width=180, fg_color="black")
        separator.grid(row=1, column=0, sticky="w", padx=10, pady=(5,10))

    def setup_engine(self):
        self.engine_frame = ctk.CTkFrame(self, fg_color="#B3B3B3")
        self.engine_frame.grid(row=1, column=0, padx=20, pady=(10,21), sticky="ew")

        self.engine_label = ctk.CTkLabel(self.engine_frame, text=Config.current_lang["simulator"], anchor='w')
        self.engine_label.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=10)

        self.upper_engine_frame = ctk.CTkFrame(self.engine_frame, fg_color="transparent")
        self.upper_engine_frame.grid(row=1, column=0, sticky="nsew")

        # Engine dropdown
        self.engine_dropdown = ctk.CTkOptionMenu(self.upper_engine_frame, values=["Pybullet"])
        self.engine_dropdown.grid(row=0, column=0, padx=10, pady=10, sticky="w")

        # Start simulation button
        self.start_simulation_button = ctk.CTkButton(self.upper_engine_frame, text=Config.current_lang["start_simulation"], command=self.toggle_simulation,  hover_color="#41d054")
        self.start_simulation_button.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        
        # Save world button
        self.save_world_button = ctk.CTkButton(self.upper_engine_frame, text=Config.current_lang["save_world"], command=self.save_world, hover_color="#41d054")
        self.save_world_button.grid(row=0, column=2, padx=10, pady=10, sticky="w")
        
        # Load world button
        self.load_world_button = ctk.CTkButton(self.upper_engine_frame, text=Config.current_lang["load_world"], command=self.load_world, hover_color="#41d054")
        self.load_world_button.grid(row=0, column=3, padx=10, pady=10, sticky="w")

    def setup_robot_status(self):
        """设置机器人状态模块"""
        self.robot_status_frame = ctk.CTkFrame(self, fg_color="#B3B3B3")
        self.robot_status_frame.grid(row=2, column=0, padx=20, pady=(10, 21), sticky="ew")

        self.base_status_frame = ctk.CTkFrame(self.robot_status_frame, fg_color="transparent")
        self.base_status_frame.grid(row=0, column=0, padx=10, pady=5, sticky="w")

        self.ee_status_frame = ctk.CTkFrame(self.robot_status_frame, fg_color="transparent")
        self.ee_status_frame.grid(row=0, column=1, padx=10, pady=5, sticky="w")

        self.base_status_label = ctk.CTkLabel(self.base_status_frame, text=Config.current_lang["robot_status"], anchor='w')
        self.base_status_label.grid(row=0, column=0, columnspan=3, sticky="ew", padx=10)

        self.ee_status_label = ctk.CTkLabel(self.ee_status_frame, text=Config.current_lang["end_effector_offset"], anchor='w')
        self.ee_status_label.grid(row=0, column=0, columnspan=3, sticky="ew", padx=10)

        # 位置控制 (单位：毫米)
        self.base_position_frame = ctk.CTkFrame(self.base_status_frame, fg_color="transparent")
        self.base_position_frame.grid(row=1, column=0, padx=10, pady=5, sticky="w")
        
        self.base_position_label = ctk.CTkLabel(self.base_position_frame, text=Config.current_lang["position"])
        self.base_position_label.grid(row=0, column=0, padx=5)
        
        self.base_x_pos = ctk.CTkEntry(self.base_position_frame, width=65, placeholder_text="X")
        self.base_x_pos.grid(row=0, column=1, padx=2)
        self.base_x_pos.insert(0, "0")
        
        self.base_y_pos = ctk.CTkEntry(self.base_position_frame, width=65, placeholder_text="Y")
        self.base_y_pos.grid(row=0, column=2, padx=2)
        self.base_y_pos.insert(0, "0")
        
        self.base_z_pos = ctk.CTkEntry(self.base_position_frame, width=65, placeholder_text="Z")
        self.base_z_pos.grid(row=0, column=3, padx=2)
        self.base_z_pos.insert(0, "0")

        # 姿态控制 (单位：度)
        self.base_orientation_frame = ctk.CTkFrame(self.base_status_frame, fg_color="transparent")
        self.base_orientation_frame.grid(row=2, column=0, padx=10, pady=5, sticky="w")
        
        self.base_orientation_label = ctk.CTkLabel(self.base_orientation_frame, text=Config.current_lang["orientation"])
        self.base_orientation_label.grid(row=0, column=0, padx=5)
        
        self.base_roll = ctk.CTkEntry(self.base_orientation_frame, width=65, placeholder_text="Roll")
        self.base_roll.grid(row=0, column=1, padx=2)
        self.base_roll.insert(0, "0")
        
        self.base_pitch = ctk.CTkEntry(self.base_orientation_frame, width=65, placeholder_text="Pitch")
        self.base_pitch.grid(row=0, column=2, padx=2)
        self.base_pitch.insert(0, "0")
        
        self.base_yaw = ctk.CTkEntry(self.base_orientation_frame, width=65, placeholder_text="Yaw")
        self.base_yaw.grid(row=0, column=3, padx=2)
        self.base_yaw.insert(0, "0")

        # 设置按钮
        self.set_base_pose_button = ctk.CTkButton(
            self.base_status_frame, 
            text=Config.current_lang.get("set_base_pose", "设置基座位姿"), 
            command=self.set_base_pose,
            hover_color="#41d054"
        )
        self.set_base_pose_button.grid(row=3, column=0, padx=10, pady=10, sticky="w")

        self.ee_position_frame = ctk.CTkFrame(self.ee_status_frame, fg_color="transparent")
        self.ee_position_frame.grid(row=1, column=0, padx=10, pady=5, sticky="w")

        self.ee_position_label = ctk.CTkLabel(self.ee_position_frame, text=Config.current_lang["position"])
        self.ee_position_label.grid(row=0, column=0, padx=5)

        self.ee_x_pos = ctk.CTkEntry(self.ee_position_frame, width=65, placeholder_text="X")
        self.ee_x_pos.grid(row=0, column=1, padx=2)
        self.ee_x_pos.insert(0, "0")

        self.ee_y_pos = ctk.CTkEntry(self.ee_position_frame, width=65, placeholder_text="Y")
        self.ee_y_pos.grid(row=0, column=2, padx=2)
        self.ee_y_pos.insert(0, "0")

        self.ee_z_pos = ctk.CTkEntry(self.ee_position_frame, width=65, placeholder_text="Z")
        self.ee_z_pos.grid(row=0, column=3, padx=2)
        self.ee_z_pos.insert(0, "0")

        self.ee_orientation_frame = ctk.CTkFrame(self.ee_status_frame, fg_color="transparent")
        self.ee_orientation_frame.grid(row=2, column=0, padx=10, pady=5, sticky="w")

        self.ee_orientation_label = ctk.CTkLabel(self.ee_orientation_frame, text=Config.current_lang["orientation"])
        self.ee_orientation_label.grid(row=0, column=0, padx=5)

        self.ee_roll = ctk.CTkEntry(self.ee_orientation_frame, width=65, placeholder_text="Roll")
        self.ee_roll.grid(row=0, column=1, padx=2)
        self.ee_roll.insert(0, "0")

        self.ee_pitch = ctk.CTkEntry(self.ee_orientation_frame, width=65, placeholder_text="Pitch")
        self.ee_pitch.grid(row=0, column=2, padx=2)
        self.ee_pitch.insert(0, "0")

        self.ee_yaw = ctk.CTkEntry(self.ee_orientation_frame, width=65, placeholder_text="Yaw")
        self.ee_yaw.grid(row=0, column=3, padx=2)
        self.ee_yaw.insert(0, "0")

        self.ee_position_button = ctk.CTkButton(self.ee_status_frame, text=Config.current_lang["set_end_position"], command=self.set_ee_offset, hover_color="#41d054")
        self.ee_position_button.grid(row=3, column=0, padx=10, pady=10, sticky="w")

        self.question_button = ctk.CTkButton(
            self.ee_status_frame,
            text="",
            image=self.question_icon,
            width=20,
            height=20,
            fg_color="transparent",
            hover_color="#B3B3B3"
        )
        self.question_button.grid(row=3, column=1, pady=(10,5))
        
        # 添加tooltip
        ToolTip(self.question_button, "Approximate Tool center point(TCP); save the TCP offset in Robot Profile.\n It is theoretical TCP! real TCP is limited by hardware inaccuracies.")


    def set_base_pose(self):
        """设置机器人基座位姿"""
        try:
            # 获取位置输入 (从毫米转换为米)
            x = float(self.base_x_pos.get() or 0) / 1000.0
            y = float(self.base_y_pos.get() or 0) / 1000.0
            z = float(self.base_z_pos.get() or 0) / 1000.0
            
            # 获取姿态输入
            rpy = np.radians([
                float(self.base_roll.get() or 0),
                float(self.base_pitch.get() or 0),
                float(self.base_yaw.get() or 0)
            ])
            
            # 将RPY角度转换为四元数
            orientation = rpy_to_quaternion(*rpy)
            
            # 设置基座位姿
            p.resetBasePositionAndOrientation(
                self.robot_id,
                [x, y, z],
                orientation,
                physicsClientId=self.client_id
            )

            # 更新self变量和robot_state
            self.base_position = np.array([x, y, z])
            self.base_orientation = np.array(orientation)
            self.robot_state.update_state("base_position", self.base_position, sender=self)
            self.robot_state.update_state("base_orientation", self.base_orientation, sender=self)

            self.log_message(f"基座位姿已设置 - 位置: ({x}, {y}, {z}), 姿态: ({np.degrees(rpy[0]):.2f}, {np.degrees(rpy[1]):.2f}, {np.degrees(rpy[2]):.2f})")
        except ValueError:
            self.log_message("无效的输入值")
        except Exception as e:
            self.log_message(f"设置基座位姿失败: {str(e)}")

    def set_ee_offset(self):
        """设置机器人末端位置"""
        try:
            # 获取位置输入 (毫米)
            x = float(self.ee_x_pos.get() or 0)
            y = float(self.ee_y_pos.get() or 0)
            z = float(self.ee_z_pos.get() or 0)

            # 获取姿态输入（角度）
            roll = float(self.ee_roll.get() or 0)
            pitch = float(self.ee_pitch.get() or 0)
            yaw = float(self.ee_yaw.get() or 0)
            
            # 更新tcp_offset：位置保存为毫米，姿态保存为度
            self.tcp_offset = np.array([x, y, z, roll, pitch, yaw])
            
            # 传给robot_state的tcp_offset需要位置转换为米
            new_tcp_offset = np.array([x/1000, y/1000, z/1000, roll, pitch, yaw])
            self.robot_state.update_state("tcp_offset", new_tcp_offset, sender=self)
            
            # 如果正在模拟，更新offline_params文件
            self.trigger_offline_params_update()
            
            self.log_message(f"末端位置偏移已设置 - 位置: ({x}, {y}, {z}), 姿态: ({roll}, {pitch}, {yaw})")
        except ValueError:
            self.log_message("无效的输入值")
        except Exception as e:
            self.log_message(f"设置末端位置偏移失败: {str(e)}")

    def setup_shape_manager(self):
        """设置形状管理模块"""
        self.shape_manager_frame = ctk.CTkFrame(self, fg_color="#B3B3B3")
        self.shape_manager_frame.grid(row=3, column=0, padx=20, pady=(10, 21), sticky="ew")
        
        # 设置列的权重，使左侧框架占据更多空间
        self.shape_manager_frame.grid_columnconfigure(0, weight=3)  # 左侧框架权重为3
        self.shape_manager_frame.grid_columnconfigure(1, weight=1)  # 右侧框架权重为1

        # 左侧框架
        left_frame = ctk.CTkFrame(self.shape_manager_frame, fg_color="transparent")
        left_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # 左侧上部：按钮切换框架
        toggle_frame = ctk.CTkFrame(left_frame, fg_color="transparent", corner_radius=0, height=30)
        toggle_frame.pack(fill="x")
        
        # 设置切换按钮框架使用均匀布局
        toggle_frame.columnconfigure((0, 1, 2), weight=1, uniform="tabs")
        
        # 创建三个独立的框架，每个框架包含一个按钮和下划线
        self.load_tab_frame = ctk.CTkFrame(toggle_frame, fg_color="transparent")
        self.load_tab_frame.grid(row=0, column=0, sticky="ew")
        self.load_tab_frame.grid_columnconfigure(0, weight=1)
        
        self.collision_tab_frame = ctk.CTkFrame(toggle_frame, fg_color="transparent")
        self.collision_tab_frame.grid(row=0, column=1, sticky="ew")
        self.collision_tab_frame.grid_columnconfigure(0, weight=1)
        
        self.visual_tab_frame = ctk.CTkFrame(toggle_frame, fg_color="transparent")
        self.visual_tab_frame.grid(row=0, column=2, sticky="ew")
        self.visual_tab_frame.grid_columnconfigure(0, weight=1)
        
        # 加载形状按钮
        self.load_shape_button = ctk.CTkButton(
            self.load_tab_frame, 
            text=Config.current_lang["load_shapes"],
            text_color="black",
            command=lambda: self.switch_shape_view("load"),
            fg_color="transparent", 
            hover_color="#B3B3B3",
            corner_radius=0,
            height=31
        )
        self.load_shape_button.grid(row=0, column=0, sticky="ew")
        
        # 加载形状下划线
        self.load_underline = ctk.CTkFrame(self.load_tab_frame, height=2, fg_color="#DBDBDB")
        self.load_underline.grid(row=1, column=0, sticky="ew")

        # 创建碰撞形状按钮
        self.create_collision_shape_button = ctk.CTkButton(
            self.collision_tab_frame, 
            text=Config.current_lang["collision_shapes"],
            text_color="black",
            command=lambda: self.switch_shape_view("collision"),
            fg_color="transparent",
            hover_color="#B3B3B3",
            corner_radius=0,
            height=31
        )
        self.create_collision_shape_button.grid(row=0, column=0, sticky="ew")
        
        # 创建碰撞形状下划线
        self.collision_underline = ctk.CTkFrame(self.collision_tab_frame, height=2, fg_color="#DBDBDB")
        self.collision_underline.grid(row=1, column=0, sticky="ew")
        self.collision_underline.grid_remove()  # 默认隐藏

        # 创建视觉形状按钮
        self.create_visual_shape_button = ctk.CTkButton(
            self.visual_tab_frame, 
            text=Config.current_lang["visual_shapes"],
            text_color="black",
            command=lambda: self.switch_shape_view("visual"),
            fg_color="transparent",
            hover_color="#B3B3B3",
            corner_radius=0,
            height=31
        )
        self.create_visual_shape_button.grid(row=0, column=0, sticky="ew")
        
        # 创建视觉形状下划线
        self.visual_underline = ctk.CTkFrame(self.visual_tab_frame, height=2, fg_color="#DBDBDB")
        self.visual_underline.grid(row=1, column=0, sticky="ew")
        self.visual_underline.grid_remove()  # 默认隐藏

        # 左侧下部：内容框架
        self.content_container = ctk.CTkFrame(left_frame, fg_color="transparent")
        self.content_container.pack(fill="both", expand=True, pady=(5,0))

        # 创建三个不同的内容框架
        self.load_frame = ctk.CTkFrame(self.content_container, fg_color="transparent")
        self.collision_frame = ctk.CTkFrame(self.content_container, fg_color="transparent")
        self.visual_frame = ctk.CTkFrame(self.content_container, fg_color="transparent")

        # 初始化各个框架的内容
        self.setup_load_frame()
        self.setup_collision_frame()
        self.setup_visual_frame()

        # 右侧框架：形状管理
        right_frame = ctk.CTkFrame(self.shape_manager_frame, fg_color="transparent")
        right_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        right_frame.grid_columnconfigure(0, weight=1)

        # 形状列表
        self.shapes_scrollable_frame = ctk.CTkScrollableFrame(right_frame, width=300, height=300)
        self.shapes_scrollable_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=5)

        self.update_shapes_list()  # 添加新方法调用
        
        # 显示默认的加载形状框架
        self.switch_shape_view("load")

    def setup_load_frame(self):
        """设置加载形状框架的内容"""
        # 文件类型选择
        type_frame = ctk.CTkFrame(self.load_frame, fg_color="transparent")
        type_frame.pack(fill="x", padx=10, pady=5)
        
        self.file_type_label = ctk.CTkLabel(type_frame, text=Config.current_lang["file_type"])
        self.file_type_label.pack(side="left", padx=5)
        self.file_type = ctk.CTkOptionMenu(
            type_frame,
            values=["URDF", "OBJ", "STL"],
            command=self.on_file_type_change
        )
        self.file_type.pack(side="left", padx=5)
        
        # 文件选择框架
        file_frame = ctk.CTkFrame(self.load_frame, fg_color="transparent")
        file_frame.pack(fill="x", padx=10, pady=5)
        
        self.file_path_label = ctk.CTkLabel(file_frame, text=Config.current_lang["file_path"])
        self.file_path_label.pack(side="left", padx=5)
        self.file_path = ctk.CTkEntry(file_frame, width=150)
        self.file_path.pack(side="left", padx=5, fill="x")
        
        self.browse_button = ctk.CTkButton(
            file_frame, 
            text=Config.current_lang["browse"], 
            width=60,
            command=self.browse_file,
            hover_color="#41d054"
        )
        self.browse_button.pack(side="left", padx=5)
        
        # 添加文件路径提示按钮（在浏览按钮之后）
        self.file_path_question_button = ctk.CTkButton(
            file_frame,
            text="",
            image=self.question_icon,
            width=20,
            height=20,
            fg_color="transparent",
            hover_color="#B3B3B3"
        )
        self.file_path_question_button.pack(side="left", padx=2)
        
        # 添加工具提示
        ToolTip(self.file_path_question_button, "Use ASCII file paths only (English characters).")
        
        # 位置框架（毫米）
        pos_frame = ctk.CTkFrame(self.load_frame, fg_color="transparent")
        pos_frame.pack(fill="x", padx=10, pady=5)
        
        self.load_pos_x_label = ctk.CTkLabel(pos_frame, text=Config.current_lang["position"])
        self.load_pos_x_label.pack(side="left", padx=5)
        self.load_pos_x = ctk.CTkEntry(pos_frame, width=60, placeholder_text="X")
        self.load_pos_x.pack(side="left", padx=2)
        self.load_pos_x.insert(0, "0")
        self.load_pos_y = ctk.CTkEntry(pos_frame, width=60, placeholder_text="Y")
        self.load_pos_y.pack(side="left", padx=2)
        self.load_pos_y.insert(0, "0")
        self.load_pos_z = ctk.CTkEntry(pos_frame, width=60, placeholder_text="Z")
        self.load_pos_z.pack(side="left", padx=2)
        self.load_pos_z.insert(0, "0")
        
        # 旋转框架（度）
        rot_frame = ctk.CTkFrame(self.load_frame, fg_color="transparent")
        rot_frame.pack(fill="x", padx=10, pady=5)
        
        self.load_rot_label = ctk.CTkLabel(rot_frame, text=Config.current_lang["orientation"])
        self.load_rot_label.pack(side="left", padx=5)
        self.load_rot_r = ctk.CTkEntry(rot_frame, width=60, placeholder_text="Roll")
        self.load_rot_r.pack(side="left", padx=2)
        self.load_rot_r.insert(0, "0")
        self.load_rot_p = ctk.CTkEntry(rot_frame, width=60, placeholder_text="Pitch")
        self.load_rot_p.pack(side="left", padx=2)
        self.load_rot_p.insert(0, "0")
        self.load_rot_y = ctk.CTkEntry(rot_frame, width=60, placeholder_text="Yaw")
        self.load_rot_y.pack(side="left", padx=2)
        self.load_rot_y.insert(0, "0")
        
        # 缩放框架
        scale_frame = ctk.CTkFrame(self.load_frame, fg_color="transparent")
        scale_frame.pack(fill="x", padx=10, pady=5)
        
        self.scale_factor_label = ctk.CTkLabel(scale_frame, text=Config.current_lang["scale_factor"])
        self.scale_factor_label.pack(side="left", padx=5)
        self.scale_factor = ctk.CTkEntry(scale_frame, width=60)
        self.scale_factor.pack(side="left", padx=5)
        self.scale_factor.insert(0, "1.0")
        
        # 固定对象选项
        fixed_frame = ctk.CTkFrame(self.load_frame, fg_color="transparent")
        fixed_frame.pack(fill="x", padx=10, pady=5)
        
        self.is_fixed = ctk.CTkCheckBox(fixed_frame, text=Config.current_lang["fixed_object"])
        self.is_fixed.pack(side="left", padx=5)
        self.is_fixed.select()  # 默认选中
        
        # 加载按钮
        self.load_button = ctk.CTkButton(self.load_frame, text=Config.current_lang["load_model"], command=self.load_model, hover_color="#41d054")
        self.load_button.pack(pady=10)

    def load_robot_profile(self):
        for group_name, group_data in ProfileManager.get_all_groups().items():
            if ProfileManager.is_end_effector_group(group_name):
                self.tool_group_includes = group_data["includes"]
            else:
                self.main_group_includes = group_data["includes"]

        # 从robot_state获取初始状态，如果没有则使用默认值
        self.joint_angles = self.robot_state.get_state("joint_angles") if self.robot_state.get_state("joint_angles") is not None else [0, 0, 0, 0]
        self.target_position = self.robot_state.get_state("target_position") if self.robot_state.get_state("target_position") is not None else [0, 0, 0]
        self.target_orientation = self.robot_state.get_state("target_orientation") if self.robot_state.get_state("target_orientation") is not None else [0, 0, 0, 1]
        self.base_position = self.robot_state.get_state("base_position") if self.robot_state.get_state("base_position") is not None else np.array([0, 0, 0])
        self.base_orientation = self.robot_state.get_state("base_orientation") if self.robot_state.get_state("base_orientation") is not None else np.array([0, 0, 0, 1])
        
        # TCP偏移量处理：只有位置(xyz)需要转换为毫米，姿态(rpy)保持不变
        tcp_offset_raw = self.robot_state.get_state("tcp_offset")
        if tcp_offset_raw is not None:
            tcp_offset_raw = np.array(tcp_offset_raw)
            self.tcp_offset = np.array([
                tcp_offset_raw[0] * 1000,  # x (米转毫米)
                tcp_offset_raw[1] * 1000,  # y (米转毫米) 
                tcp_offset_raw[2] * 1000,  # z (米转毫米)
                tcp_offset_raw[3],         # roll (度，不变)
                tcp_offset_raw[4],         # pitch (度，不变)
                tcp_offset_raw[5]          # yaw (度，不变)
            ])
        else:
            self.tcp_offset = np.array([0, 0, 0, 0, 0, 0])
            
        self.end_effector_link = self.robot_state.get_state("end_effector_link") if self.robot_state.get_state("end_effector_link") is not None else 0
        self.tool_state = self.robot_state.get_state("tool_state") if self.robot_state.get_state("tool_state") is not None else []
        
        # 触发离线参数更新，通知multiprocess GUI关于profile变化
        self.trigger_offline_params_update()

    def update_ui(self):
        """更新UI中的输入框值"""
        try:
            # 获取基座位姿
            base_pos, base_orn = p.getBasePositionAndOrientation(self.robot_id, physicsClientId=self.client_id)
            base_pos = [p * 1000 for p in base_pos]  # 转换为毫米
            base_rpy = p.getEulerFromQuaternion(base_orn)  # 弧度
            base_rpy_deg = [math.degrees(angle) for angle in base_rpy]  # 转换为角度
            
            # 更新基座位置输入框
            self.base_x_pos.delete(0, 'end')
            self.base_x_pos.insert(0, f"{base_pos[0]:.2f}")
            
            self.base_y_pos.delete(0, 'end')
            self.base_y_pos.insert(0, f"{base_pos[1]:.2f}")
            
            self.base_z_pos.delete(0, 'end')
            self.base_z_pos.insert(0, f"{base_pos[2]:.2f}")
            
            # 更新基座姿态输入框
            self.base_roll.delete(0, 'end')
            self.base_roll.insert(0, f"{base_rpy_deg[0]:.2f}")

            self.base_pitch.delete(0, 'end')
            self.base_pitch.insert(0, f"{base_rpy_deg[1]:.2f}")

            self.base_yaw.delete(0, 'end')
            self.base_yaw.insert(0, f"{base_rpy_deg[2]:.2f}")

            # 更新self变量和机器人状态中的基座位姿（米为单位）
            base_pos_meters = np.array(base_pos) / 1000.0
            self.base_position = base_pos_meters
            self.base_orientation = np.array(base_orn)
            self.robot_state.update_state("base_position", self.base_position, sender=self)
            self.robot_state.update_state("base_orientation", self.base_orientation, sender=self)

            # 更新末端执行器偏移输入框
            self.ee_x_pos.delete(0, 'end')
            self.ee_x_pos.insert(0, f"{self.tcp_offset[0]:.2f}")
            
            self.ee_y_pos.delete(0, 'end')
            self.ee_y_pos.insert(0, f"{self.tcp_offset[1]:.2f}")
            
            self.ee_z_pos.delete(0, 'end')
            self.ee_z_pos.insert(0, f"{self.tcp_offset[2]:.2f}")
            
            self.ee_roll.delete(0, 'end')
            self.ee_roll.insert(0, f"{self.tcp_offset[3]:.2f}")
            
            self.ee_pitch.delete(0, 'end')
            self.ee_pitch.insert(0, f"{self.tcp_offset[4]:.2f}")
            
            self.ee_yaw.delete(0, 'end')
            self.ee_yaw.insert(0, f"{self.tcp_offset[5]:.2f}")
            
        except Exception as e:
            self.log_message(f"更新UI失败: {str(e)}")

    def browse_file(self):
        """打开文件浏览对话框"""
        from tkinter import filedialog
        
        file_type = self.file_type.get()
        file_types = []
        
        if file_type == "URDF":
            file_types = [("URDF 文件", "*.urdf")]
        elif file_type == "OBJ":
            file_types = [("OBJ 文件", "*.obj")]
        elif file_type == "STL":
            file_types = [("STL 文件", "*.stl")]
        
        file_path = filedialog.askopenfilename(
            title=f"Select {file_type} file",
            filetypes=file_types + [("所有文件", "*.*")]
        )
        
        if file_path:
            self.file_path.delete(0, 'end')
            self.file_path.insert(0, file_path)

    def on_file_type_change(self, file_type):
        if file_type == "STL":
            self.scale_factor.delete(0, 'end')
            self.scale_factor.insert(0, "0.001")
        else:
            self.scale_factor.delete(0, 'end')
            self.scale_factor.insert(0, "1.0")

    def load_model(self):
        """加载模型文件"""
        file_path = self.file_path.get()
        if not file_path or not os.path.exists(file_path):
            self.log_message("Please select a valid file")
            return
        
        try:
            # 获取位置（从毫米转换为米）
            pos = [
                float(self.load_pos_x.get() or 0) / 1000.0,
                float(self.load_pos_y.get() or 0) / 1000.0,
                float(self.load_pos_z.get() or 0) / 1000.0
            ]
            
            # 将角度转换为弧度的四元数
            rpy = np.radians([
                float(self.load_rot_r.get() or 0),
                float(self.load_rot_p.get() or 0),
                float(self.load_rot_y.get() or 0)
            ])
            orn = rpy_to_quaternion(*rpy).tolist()
            
            # 获取缩放和固定参数
            scale = float(self.scale_factor.get())
            is_fixed = self.is_fixed.get()
            
            # 获取文件类型
            file_type = os.path.splitext(file_path)[1].upper().replace('.', '')
            
            shape_data = None
            
            if file_type == "URDF" or file_type == "XACRO":
                # 使用物理引擎加载URDF模型
                shape_data = self.physics_engine.load_urdf_model(
                    file_path,
                    position=pos,
                    orientation=orn,
                    client_name=self.client_name
                )
            elif file_type == "OBJ":
                # 使用物理引擎加载OBJ模型
                shape_data = self.physics_engine.load_obj_model(
                    file_path,
                    scale=scale,
                    mass=0 if is_fixed else 1.0,
                    position=pos,
                    orientation=orn,
                    client_name=self.client_name
                )
            elif file_type == "STL":
                # 使用物理引擎加载STL模型
                shape_data = self.physics_engine.load_stl_model(
                    file_path,
                    scale=scale,
                    mass=0 if is_fixed else 1.0,
                    position=pos,
                    orientation=orn,
                    client_name=self.client_name
                )
            else:
                self.log_message(f"不支持的文件类型: {file_type}")
                return
            
            if shape_data:
                # 更新形状列表显示
                self.update_shapes_list()
                self.log_message(f"已加载{file_type}模型: {os.path.basename(file_path)}")
            else:
                self.log_message(f"加载{file_type}模型失败")
            
        except ValueError as e:
            self.log_message(f"输入值无效: {str(e)}")
        except Exception as e:
            self.log_message(f"加载模型失败: {str(e)}")

    def setup_collision_frame(self):
        """设置碰撞形状框架的内容"""
        # 形状类型选择
        type_frame = ctk.CTkFrame(self.collision_frame, fg_color="transparent")
        type_frame.pack(fill="x", padx=10, pady=5)
        
        self.shape_type_label = ctk.CTkLabel(type_frame, text=Config.current_lang["shape_type"])
        self.shape_type_label.pack(side="left", padx=5)
        self.shape_type = ctk.CTkOptionMenu(
            type_frame,
            values=["sphere", "box", "cylinder", "capsule"],
            command=self.on_shape_type_change
        )
        self.shape_type.pack(side="left", padx=5)

        # 参数框架
        self.params_frame = ctk.CTkFrame(self.collision_frame, fg_color="transparent")
        self.params_frame.pack(fill="x", padx=10, pady=5)

        # 位置框架 - 修改单位标签为毫米
        pos_frame = ctk.CTkFrame(self.collision_frame, fg_color="transparent")
        pos_frame.pack(fill="x", padx=10, pady=5)
        
        self.collision_pos_x_label = ctk.CTkLabel(pos_frame, text=Config.current_lang["position"])
        self.collision_pos_x_label.pack(side="left", padx=5)
        self.pos_x = ctk.CTkEntry(pos_frame, width=60, placeholder_text="X")
        self.pos_x.pack(side="left", padx=2)
        self.pos_y = ctk.CTkEntry(pos_frame, width=60, placeholder_text="Y")
        self.pos_y.pack(side="left", padx=2)
        self.pos_z = ctk.CTkEntry(pos_frame, width=60, placeholder_text="Z")
        self.pos_z.pack(side="left", padx=2)

        # 旋转框架
        rot_frame = ctk.CTkFrame(self.collision_frame, fg_color="transparent")
        rot_frame.pack(fill="x", padx=10, pady=5)
        
        self.collision_rot_label = ctk.CTkLabel(rot_frame, text=Config.current_lang["orientation"])
        self.collision_rot_label.pack(side="left", padx=5)
        self.rot_r = ctk.CTkEntry(rot_frame, width=60, placeholder_text="Roll")
        self.rot_r.pack(side="left", padx=2)
        self.rot_p = ctk.CTkEntry(rot_frame, width=60, placeholder_text="Pitch")
        self.rot_p.pack(side="left", padx=2)
        self.rot_y = ctk.CTkEntry(rot_frame, width=60, placeholder_text="Yaw")
        self.rot_y.pack(side="left", padx=2)

        # 固定对象选项
        fixed_frame = ctk.CTkFrame(self.collision_frame, fg_color="transparent")
        fixed_frame.pack(fill="x", padx=10, pady=5)
        
        self.collision_is_fixed = ctk.CTkCheckBox(fixed_frame, text=Config.current_lang["fixed_object"])
        self.collision_is_fixed.pack(side="left", padx=5)
        self.collision_is_fixed.select()  # 默认选中

        # 创建按钮
        self.collision_create_button = ctk.CTkButton(
            self.collision_frame,
            text=Config.current_lang["create"],
            command=self.create_collision_shape
        )
        self.collision_create_button.pack(pady=10)

        # 默认显示sphere参数
        self.show_sphere_params()

    def on_shape_type_change(self, shape_type):
        """当形状类型改变时更新参数显示"""
        # 清除现有参数
        for widget in self.params_frame.winfo_children():
            widget.destroy()

        # 根据选择的形状类型显示相应参数
        if shape_type == "sphere":
            self.show_sphere_params()
        elif shape_type == "box":
            self.show_box_params()
        elif shape_type == "cylinder":
            self.show_cylinder_params()
        elif shape_type == "capsule":
            self.show_capsule_params()

    def show_sphere_params(self):
        """显示sphere参数"""
        self.sphere_radius_label = ctk.CTkLabel(self.params_frame, text=Config.current_lang["radius"] + " (m):")
        self.sphere_radius_label.pack(side="left", padx=5)
        self.radius = ctk.CTkEntry(self.params_frame, width=60)
        self.radius.pack(side="left", padx=5)
        self.radius.insert(0, "0.1")

    def show_box_params(self):
        """显示box参数"""
        self.box_dimensions_label = ctk.CTkLabel(self.params_frame, text=Config.current_lang["size"] + " (m):")
        self.box_dimensions_label.pack(side="left", padx=5)
        self.length = ctk.CTkEntry(self.params_frame, width=60, placeholder_text=Config.current_lang["length"])
        self.length.pack(side="left", padx=2)
        self.length.insert(0, "0.1")
        self.width = ctk.CTkEntry(self.params_frame, width=60, placeholder_text=Config.current_lang["width"])
        self.width.pack(side="left", padx=2)
        self.width.insert(0, "0.1")
        self.height = ctk.CTkEntry(self.params_frame, width=60, placeholder_text=Config.current_lang["height"])
        self.height.pack(side="left", padx=2)
        self.height.insert(0, "0.1")

    def show_cylinder_params(self):
        """显示cylinder参数"""
        self.cylinder_radius_label = ctk.CTkLabel(self.params_frame, text=Config.current_lang["radius"] + " (m):")
        self.cylinder_radius_label.pack(side="left", padx=5)
        self.radius = ctk.CTkEntry(self.params_frame, width=60)
        self.radius.pack(side="left", padx=5)
        self.radius.insert(0, "0.1")
        
        self.cylinder_height_label = ctk.CTkLabel(self.params_frame, text=Config.current_lang["height"] + " (m):")
        self.cylinder_height_label.pack(side="left", padx=5)
        self.height = ctk.CTkEntry(self.params_frame, width=60)
        self.height.pack(side="left", padx=5)
        self.height.insert(0, "0.2")

    def show_capsule_params(self):
        """显示capsule参数"""
        self.capsule_radius_label = ctk.CTkLabel(self.params_frame, text=Config.current_lang["radius"] + " (m):")
        self.capsule_radius_label.pack(side="left", padx=5)
        self.radius = ctk.CTkEntry(self.params_frame, width=60)
        self.radius.pack(side="left", padx=5)
        self.radius.insert(0, "0.1")
        
        self.capsule_height_label = ctk.CTkLabel(self.params_frame, text=Config.current_lang["height"] + " (m):")
        self.capsule_height_label.pack(side="left", padx=5)
        self.height = ctk.CTkEntry(self.params_frame, width=60)
        self.height.pack(side="left", padx=5)
        self.height.insert(0, "0.2")

    def create_collision_shape(self):
        """创建碰撞形状"""
        try:
            # 获取位置（从毫米转换为米）
            pos = [
                float(self.pos_x.get() or 0) / 1000.0,
                float(self.pos_y.get() or 0) / 1000.0,
                float(self.pos_z.get() or 0) / 1000.0
            ]
            
            # 将角度转换为弧度的四元数
            rpy = np.radians([
                float(self.rot_r.get() or 0),
                float(self.rot_p.get() or 0),
                float(self.rot_y.get() or 0)
            ])
            orn = rpy_to_quaternion(*rpy).tolist()

            shape_type = self.shape_type.get()
            
            # 获取固定状态
            is_fixed = self.collision_is_fixed.get()
            
            # 准备形状参数
            params = self.get_shape_parameters(shape_type)
            params['position'] = pos
            params['orientation'] = orn
            params['mass'] = 0 if is_fixed else 1.0  # 根据is fixed设置质量
            
            # 使用物理引擎创建碰撞形状
            shape_data = self.physics_engine.create_collision_shape(shape_type, params, self.client_name)
            
            if shape_data:
                # 更新形状列表显示
                self.update_shapes_list()
                self.log_message(f"创建{shape_type}碰撞形状成功，ID: {shape_data['id']}")
            else:
                self.log_message(f"创建碰撞形状失败")
            
        except ValueError as e:
            self.log_message(f"输入值无效: {str(e)}")
        except Exception as e:
            self.log_message(f"创建碰撞形状失败: {str(e)}")

    def get_shape_parameters(self, shape_type):
        """获取当前形状的参数"""
        params = {}
        if shape_type == "sphere":
            params['radius'] = float(self.radius.get())
        elif shape_type == "box":
            params['length'] = float(self.length.get())
            params['width'] = float(self.width.get())
            params['height'] = float(self.height.get())
        elif shape_type in ["cylinder", "capsule"]:
            params['radius'] = float(self.radius.get())
            params['height'] = float(self.height.get())
        return params

    def update_shapes_list(self):
        """更新形状列表显示"""
        # 清除当前列表
        for widget in self.shapes_scrollable_frame.winfo_children():
            widget.destroy()
            
        # 从物理引擎获取shapes列表
        shapes = self.physics_engine.get_shapes(self.client_name)
            
        # 重新添加所有形状
        for shape in shapes:
            shape_frame = ctk.CTkFrame(self.shapes_scrollable_frame)
            shape_frame.pack(fill="x", expand=True, padx=5, pady=5)
            
            if shape['type'].startswith('导入'):
                name_label = ctk.CTkLabel(shape_frame, text=f"{shape['name']}")
            else:
                name_label = ctk.CTkLabel(shape_frame, text=f"{shape['type']} ID:{shape['id']}")
            name_label.pack(side="left", padx=5, pady=5)
            
            menu_button = ctk.CTkButton(
                shape_frame,
                text="",
                image=self.edit_icon,
                width=25,
                height=25,
                hover_color="#41d054",
                fg_color="transparent"
            )
            menu_button.pack(side="right", padx=5, pady=5)
            
            # 创建菜单函数，确保正确捕获当前shape
            def create_menu_handler(current_shape):
                def show_menu(event):
                    menu = tk.Menu(self, tearoff=0)
                    menu.add_command(label="编辑位姿", command=lambda: self.edit_shape_pose(current_shape))
                    menu.add_command(label="复制", command=lambda: self.copy_shape(current_shape))
                    menu.add_command(label="删除", command=lambda: self.delete_shape(current_shape))
                    menu.post(event.x_root, event.y_root)
                return show_menu
            
            menu_button.bind("<Button-1>", create_menu_handler(shape))
        
        # 如果正在模拟，更新offline_params文件
        self.trigger_offline_params_update()

    def delete_shape(self, shape):
        """删除形状"""
        # 使用物理引擎删除形状
        if self.physics_engine.remove_shape(shape['id'], self.client_name):
            # 更新UI
            self.update_shapes_list()
            self.log_message(f"删除形状，ID: {shape['id']}")
        else:
            self.log_message(f"删除形状失败，ID: {shape['id']}")

    def setup_visual_frame(self):
        """设置视觉形状框架的内容"""
        # 形状类型选择
        type_frame = ctk.CTkFrame(self.visual_frame, fg_color="transparent")
        type_frame.pack(fill="x", padx=10, pady=5)
        
        self.visual_shape_type_label = ctk.CTkLabel(type_frame, text=Config.current_lang["shape_type"])
        self.visual_shape_type_label.pack(side="left", padx=5)
        self.visual_shape_type = ctk.CTkOptionMenu(
            type_frame,
            values=["sphere", "box", "cylinder", "capsule"],
            command=self.on_visual_shape_type_change
        )
        self.visual_shape_type.pack(side="left", padx=5)

        # 参数框架
        self.visual_params_frame = ctk.CTkFrame(self.visual_frame, fg_color="transparent")
        self.visual_params_frame.pack(fill="x", padx=10, pady=5)

        # 位置框架 - 毫米单位
        pos_frame = ctk.CTkFrame(self.visual_frame, fg_color="transparent")
        pos_frame.pack(fill="x", padx=10, pady=5)
        
        self.visual_pos_x_label = ctk.CTkLabel(pos_frame, text=Config.current_lang["position"])
        self.visual_pos_x_label.pack(side="left", padx=5)
        self.visual_pos_x = ctk.CTkEntry(pos_frame, width=60, placeholder_text="X")
        self.visual_pos_x.pack(side="left", padx=2)
        self.visual_pos_y = ctk.CTkEntry(pos_frame, width=60, placeholder_text="Y")
        self.visual_pos_y.pack(side="left", padx=2)
        self.visual_pos_z = ctk.CTkEntry(pos_frame, width=60, placeholder_text="Z")
        self.visual_pos_z.pack(side="left", padx=2)

        # 旋转框架
        rot_frame = ctk.CTkFrame(self.visual_frame, fg_color="transparent")
        rot_frame.pack(fill="x", padx=10, pady=5)
        
        self.visual_rot_label = ctk.CTkLabel(rot_frame, text=Config.current_lang["orientation"])
        self.visual_rot_label.pack(side="left", padx=5)
        self.visual_rot_r = ctk.CTkEntry(rot_frame, width=60, placeholder_text="Roll")
        self.visual_rot_r.pack(side="left", padx=2)
        self.visual_rot_p = ctk.CTkEntry(rot_frame, width=60, placeholder_text="Pitch")
        self.visual_rot_p.pack(side="left", padx=2)
        self.visual_rot_y = ctk.CTkEntry(rot_frame, width=60, placeholder_text="Yaw")
        self.visual_rot_y.pack(side="left", padx=2)

        # 颜色框架
        color_frame = ctk.CTkFrame(self.visual_frame, fg_color="transparent")
        color_frame.pack(fill="x", padx=10, pady=5)
        
        self.visual_color_label = ctk.CTkLabel(color_frame, text=Config.current_lang["color"] + " (RGB):")
        self.visual_color_label.pack(side="left", padx=5)
        self.visual_color_r = ctk.CTkEntry(color_frame, width=60, placeholder_text="R (0-1)")
        self.visual_color_r.pack(side="left", padx=2)
        self.visual_color_r.insert(0, "1.0")
        self.visual_color_g = ctk.CTkEntry(color_frame, width=60, placeholder_text="G (0-1)")
        self.visual_color_g.pack(side="left", padx=2)
        self.visual_color_g.insert(0, "0.0")
        self.visual_color_b = ctk.CTkEntry(color_frame, width=60, placeholder_text="B (0-1)")
        self.visual_color_b.pack(side="left", padx=2)
        self.visual_color_b.insert(0, "0.0")
        
        # 透明度框架
        alpha_frame = ctk.CTkFrame(self.visual_frame, fg_color="transparent")
        alpha_frame.pack(fill="x", padx=10, pady=5)
        
        self.visual_alpha_label = ctk.CTkLabel(alpha_frame, text=Config.current_lang["alpha"] + " (0-1):")
        self.visual_alpha_label.pack(side="left", padx=5)
        self.visual_alpha = ctk.CTkEntry(alpha_frame, width=60)
        self.visual_alpha.pack(side="left", padx=5)
        self.visual_alpha.insert(0, "1.0")

        # 创建按钮
        self.visual_create_button = ctk.CTkButton(
            self.visual_frame,
            text=Config.current_lang["create"],
            command=self.create_visual_shape
        )
        self.visual_create_button.pack(pady=10)

        # 默认显示sphere参数
        self.show_visual_sphere_params()

    def on_visual_shape_type_change(self, shape_type):
        """当视觉形状类型改变时更新参数显示"""
        # 清除现有参数
        for widget in self.visual_params_frame.winfo_children():
            widget.destroy()

        # 根据选择的形状类型显示相应参数
        if shape_type == "sphere":
            self.show_visual_sphere_params()
        elif shape_type == "box":
            self.show_visual_box_params()
        elif shape_type == "cylinder":
            self.show_visual_cylinder_params()
        elif shape_type == "capsule":
            self.show_visual_capsule_params()

    def show_visual_sphere_params(self):
        """显示sphere参数"""
        self.visual_radius_label = ctk.CTkLabel(self.visual_params_frame, text=Config.current_lang["radius"] + " (m):")
        self.visual_radius_label.pack(side="left", padx=5)
        self.visual_radius = ctk.CTkEntry(self.visual_params_frame, width=60)
        self.visual_radius.pack(side="left", padx=5)
        self.visual_radius.insert(0, "0.1")

    def show_visual_box_params(self):
        """显示box参数"""
        self.visual_length_label = ctk.CTkLabel(self.visual_params_frame, text=Config.current_lang["size"] + " (m):")
        self.visual_length_label.pack(side="left", padx=5)
        self.visual_length = ctk.CTkEntry(self.visual_params_frame, width=60, placeholder_text=Config.current_lang["length"])
        self.visual_length.pack(side="left", padx=2)
        self.visual_length.insert(0, "0.1")
        self.visual_width = ctk.CTkEntry(self.visual_params_frame, width=60, placeholder_text=Config.current_lang["width"])
        self.visual_width.pack(side="left", padx=2)
        self.visual_width.insert(0, "0.1")
        self.visual_height = ctk.CTkEntry(self.visual_params_frame, width=60, placeholder_text=Config.current_lang["height"])
        self.visual_height.pack(side="left", padx=2)
        self.visual_height.insert(0, "0.1")

    def show_visual_cylinder_params(self):
        """显示cylinder参数"""
        self.visual_radius_label = ctk.CTkLabel(self.visual_params_frame, text=Config.current_lang["radius"] + " (m):")
        self.visual_radius_label.pack(side="left", padx=5)
        self.visual_radius = ctk.CTkEntry(self.visual_params_frame, width=60)
        self.visual_radius.pack(side="left", padx=5)
        self.visual_radius.insert(0, "0.1")
        
        self.visual_height_label = ctk.CTkLabel(self.visual_params_frame, text=Config.current_lang["height"] + " (m):")
        self.visual_height_label.pack(side="left", padx=5)
        self.visual_height = ctk.CTkEntry(self.visual_params_frame, width=60)
        self.visual_height.pack(side="left", padx=5)
        self.visual_height.insert(0, "0.2")

    def show_visual_capsule_params(self):
        """显示capsule参数"""
        self.visual_radius_label = ctk.CTkLabel(self.visual_params_frame, text=Config.current_lang["radius"] + " (m):")
        self.visual_radius_label.pack(side="left", padx=5)
        self.visual_radius = ctk.CTkEntry(self.visual_params_frame, width=60)
        self.visual_radius.pack(side="left", padx=5)
        self.visual_radius.insert(0, "0.1")
        
        self.visual_height_label = ctk.CTkLabel(self.visual_params_frame, text=Config.current_lang["height"] + " (m):")
        self.visual_height_label.pack(side="left", padx=5)
        self.visual_height = ctk.CTkEntry(self.visual_params_frame, width=60)
        self.visual_height.pack(side="left", padx=5)
        self.visual_height.insert(0, "0.2")

    def create_visual_shape(self):
        """创建视觉形状"""
        try:
            # 获取位置（从毫米转换为米）
            pos = [
                float(self.visual_pos_x.get() or 0) / 1000.0,
                float(self.visual_pos_y.get() or 0) / 1000.0,
                float(self.visual_pos_z.get() or 0) / 1000.0
            ]
            
            # 将角度转换为弧度的四元数
            rpy = np.radians([
                float(self.visual_rot_r.get() or 0),
                float(self.visual_rot_p.get() or 0),
                float(self.visual_rot_y.get() or 0)
            ])
            orn = rpy_to_quaternion(*rpy).tolist()

            # 获取颜色和透明度
            rgba = [
                float(self.visual_color_r.get() or 1.0),
                float(self.visual_color_g.get() or 0.0),
                float(self.visual_color_b.get() or 0.0),
                float(self.visual_alpha.get() or 1.0)
            ]

            shape_type = self.visual_shape_type.get()
            
            # 准备形状参数
            params = self.get_visual_shape_parameters(shape_type)
            params['position'] = pos
            params['orientation'] = orn
            params['rgba_color'] = rgba
            
            # 使用物理引擎创建视觉形状
            shape_data = self.physics_engine.create_visual_shape(shape_type, params, self.client_name)
            
            if shape_data:
                # 更新形状列表显示
                self.update_shapes_list()
                self.log_message(f"创建{shape_type}视觉形状成功，ID: {shape_data['id']}")
            else:
                self.log_message(f"创建视觉形状失败")
            
        except ValueError as e:
            self.log_message(f"输入值无效: {str(e)}")
        except Exception as e:
            self.log_message(f"创建视觉形状失败: {str(e)}")

    def get_visual_shape_parameters(self, shape_type):
        """获取当前视觉形状的参数"""
        params = {}
        if shape_type == "sphere":
            params['radius'] = float(self.visual_radius.get())
        elif shape_type == "box":
            params['length'] = float(self.visual_length.get())
            params['width'] = float(self.visual_width.get())
            params['height'] = float(self.visual_height.get())
        elif shape_type in ["cylinder", "capsule"]:
            params['radius'] = float(self.visual_radius.get())
            params['height'] = float(self.visual_height.get())
        return params

    def switch_shape_view(self, view_name):
        """切换不同的形状视图"""
        # 隐藏所有框架
        self.load_frame.pack_forget()
        self.collision_frame.pack_forget()
        self.visual_frame.pack_forget()

        # 隐藏所有下划线
        self.load_underline.grid_remove()
        self.collision_underline.grid_remove()
        self.visual_underline.grid_remove()

        # 显示选中的框架并更新下划线状态
        if view_name == "load":
            self.load_frame.pack(fill="both", expand=True)
            self.load_underline.grid()
        elif view_name == "collision":
            self.collision_frame.pack(fill="both", expand=True)
            self.collision_underline.grid()
        elif view_name == "visual":
            self.visual_frame.pack(fill="both", expand=True)
            self.visual_underline.grid()

    def setup_terminal(self):
        """设置终端窗口"""
        self.terminal_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.terminal_frame.grid(row=4, column=0, padx=10, pady=10, sticky="nsew")

        self.terminal_text = ScrolledText(self.terminal_frame, state=tk.DISABLED, wrap=tk.WORD, 
                                          background="#000000", foreground="#41d054",
                                          width=50, height=10)
        self.terminal_text.pack(padx=10, pady=10, fill="both", expand=True)

    def log_message(self, message):
        """记录消息到终端"""
        self.terminal_text.configure(state=tk.NORMAL)
        self.terminal_text.insert(tk.END, message + "\n")
        self.terminal_text.yview(tk.END)
        self.terminal_text.configure(state=tk.DISABLED)

    def save_world(self):
        """保存当前世界状态到文件"""
        try:
            # 打开文件对话框
            file_path = tk.filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON文件", "*.json")],
                title="保存世界"
            )
            
            if not file_path:
                return
            
            # 从物理引擎获取当前形状列表
            shapes = self.physics_engine.get_shapes(self.client_name)
            
            # 准备保存的数据
            world_data = {'shapes': shapes}
            
            # 保存到文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(world_data, f, ensure_ascii=False, indent=4)
            
            self.log_message(f"已保存世界状态到: {file_path}")
        except Exception as e:
            self.log_message(f"保存世界失败: {str(e)}")

    def edit_shape_pose(self, shape):
        """编辑形状位姿（位置和旋转）"""
        edit_window = ctk.CTkToplevel(self)
        edit_window.title("编辑位姿")
        edit_window.geometry("300x450")
        edit_window.resizable(False, False)
        
        # 设置窗口始终显示在最上层
        edit_window.transient(self)  # 设置为主窗口的临时窗口
        edit_window.grab_set()  # 模态窗口，阻止与其他窗口的交互
        
        # 获取当前位置（米转毫米）
        current_pos = shape['parameters']['position']
        pos_mm = [p * 1000 for p in current_pos]
        
        # 获取当前朝向，并转换为欧拉角（度）
        current_orn = shape['parameters']['orientation']
        current_rpy = np.degrees(quaternion_to_rpy(current_orn))
        
        frame = ctk.CTkFrame(edit_window)
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 标题
        title_label = ctk.CTkLabel(frame, text="编辑位姿", font=("Arial", 14, "bold"))
        title_label.pack(pady=10)
        
        # 位置部分
        pos_title = ctk.CTkLabel(frame, text="位置 (毫米)", font=("Arial", 12, "bold"))
        pos_title.pack(pady=(10, 5))
        
        # X坐标
        x_frame = ctk.CTkFrame(frame, fg_color="transparent")
        x_frame.pack(fill="x", padx=10, pady=5)
        x_label = ctk.CTkLabel(x_frame, text="X:", width=30)
        x_label.pack(side="left", padx=5)
        x_entry = ctk.CTkEntry(x_frame)
        x_entry.pack(side="left", fill="x", expand=True, padx=5)
        x_entry.insert(0, str(pos_mm[0]))
        
        # Y坐标
        y_pos_frame = ctk.CTkFrame(frame, fg_color="transparent")
        y_pos_frame.pack(fill="x", padx=10, pady=5)
        y_pos_label = ctk.CTkLabel(y_pos_frame, text="Y:", width=30)
        y_pos_label.pack(side="left", padx=5)
        y_pos_entry = ctk.CTkEntry(y_pos_frame)
        y_pos_entry.pack(side="left", fill="x", expand=True, padx=5)
        y_pos_entry.insert(0, str(pos_mm[1]))
        
        # Z坐标
        z_frame = ctk.CTkFrame(frame, fg_color="transparent")
        z_frame.pack(fill="x", padx=10, pady=5)
        z_label = ctk.CTkLabel(z_frame, text="Z:", width=30)
        z_label.pack(side="left", padx=5)
        z_entry = ctk.CTkEntry(z_frame)
        z_entry.pack(side="left", fill="x", expand=True, padx=5)
        z_entry.insert(0, str(pos_mm[2]))
        
        # 旋转部分
        rot_title = ctk.CTkLabel(frame, text="旋转 (度)", font=("Arial", 12, "bold"))
        rot_title.pack(pady=(15, 5))
        
        # Roll
        roll_frame = ctk.CTkFrame(frame, fg_color="transparent")
        roll_frame.pack(fill="x", padx=10, pady=5)
        roll_label = ctk.CTkLabel(roll_frame, text="Roll:", width=30)
        roll_label.pack(side="left", padx=5)
        roll_entry = ctk.CTkEntry(roll_frame)
        roll_entry.pack(side="left", fill="x", expand=True, padx=5)
        roll_entry.insert(0, str(round(current_rpy[0], 2)))
        
        # Pitch
        pitch_frame = ctk.CTkFrame(frame, fg_color="transparent")
        pitch_frame.pack(fill="x", padx=10, pady=5)
        pitch_label = ctk.CTkLabel(pitch_frame, text="Pitch:", width=30)
        pitch_label.pack(side="left", padx=5)
        pitch_entry = ctk.CTkEntry(pitch_frame)
        pitch_entry.pack(side="left", fill="x", expand=True, padx=5)
        pitch_entry.insert(0, str(round(current_rpy[1], 2)))
        
        # Yaw
        yaw_frame = ctk.CTkFrame(frame, fg_color="transparent")
        yaw_frame.pack(fill="x", padx=10, pady=5)
        yaw_label = ctk.CTkLabel(yaw_frame, text="Yaw:", width=30)
        yaw_label.pack(side="left", padx=5)
        yaw_entry = ctk.CTkEntry(yaw_frame)
        yaw_entry.pack(side="left", fill="x", expand=True, padx=5)
        yaw_entry.insert(0, str(round(current_rpy[2], 2)))
        
        # 按钮框架
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        def apply_pose():
            try:
                # 获取新位置（毫米转米）
                new_pos = [
                    float(x_entry.get()) / 1000.0,
                    float(y_pos_entry.get()) / 1000.0,
                    float(z_entry.get()) / 1000.0
                ]

                rpy = np.radians([
                    float(roll_entry.get() or 0),
                    float(pitch_entry.get() or 0),
                    float(yaw_entry.get() or 0)
                ])
                
                new_orn = rpy_to_quaternion(*rpy).tolist()
                
                # 使用物理引擎同时更新形状位置和朝向
                if self.physics_engine.update_shape_pose(shape['id'], new_pos, new_orn, self.client_name):
                    self.log_message(f"更新位姿成功，ID: {shape['id']}")
                else:
                    self.log_message(f"更新位姿失败，ID: {shape['id']}")
                
                # 关闭窗口
                edit_window.destroy()
                
                # 更新列表
                self.update_shapes_list()
                
            except ValueError as e:
                self.log_message(f"输入值无效: {str(e)}")
            except Exception as e:
                self.log_message(f"更新位姿失败: {str(e)}")
        
        # 确定按钮
        apply_btn = ctk.CTkButton(btn_frame, text="确定", command=apply_pose, hover_color="#41d054")
        apply_btn.pack(side="left", padx=5, pady=5, fill="x", expand=True)
        
        # 取消按钮
        cancel_btn = ctk.CTkButton(btn_frame, text="取消", command=edit_window.destroy, hover_color="#000000")
        cancel_btn.pack(side="left", padx=5, pady=5, fill="x", expand=True)

    def copy_shape(self, shape):
        """复制形状"""
        try:
            # 使用物理引擎复制形状
            new_shape = self.physics_engine.copy_shape(shape['id'], [0.05, 0.05, 0], self.client_name)
            
            if new_shape:
                # 更新形状列表显示
                self.update_shapes_list()
                self.log_message(f"复制形状成功，新ID: {new_shape['id']}")
            else:
                self.log_message(f"复制形状失败")
        except Exception as e:
            self.log_message(f"复制形状失败: {str(e)}")

    def toggle_simulation(self):
        """切换模拟状态（开始/停止）"""
        if self.is_simulating:
            # 当前正在模拟，需要停止
            if self.operating_system == "Windows":
                self.close_pybullet_simulation()
            else:  # MacOS and Linux
                self.close_pybullet_simulation_multiprocess()
                
            self.start_simulation_button.configure(text=Config.current_lang["start_simulation"])
            self.start_simulation_button.configure(hover_color="#41d054")
            self.is_simulating = False
        else:
            try:        
                self.is_simulating = True
                
                # 根据操作系统选择合适的仿真方法
                if self.operating_system == "Windows":
                    self.simulation_thread = threading.Thread(target=self.open_pybullet_simulation)
                    self.simulation_thread.daemon = True
                    self.simulation_thread.start()
                else: # MacOS and Linux
                    self.start_pybullet_simulation_multiprocess()
                
                # 更改按钮文本为停止模拟
                self.start_simulation_button.configure(text=Config.current_lang.get("stop_simulation", "停止模拟"))
                self.start_simulation_button.configure(hover_color="#E74C3C")
                    
            except Exception as e:
                self.is_simulating = False
                messagebox.showerror("错误", f"启动PyBullet仿真失败: {str(e)}")
                self.log_message(f"启动仿真失败: {str(e)}")

    def __del__(self):
        """析构函数，确保所有资源被释放"""
        try:
            # 关闭所有可能的仿真
            if hasattr(self, 'is_simulating') and self.is_simulating:
                if self.operating_system == "Windows":
                    # 如果使用的是内部线程模式
                    self.close_pybullet_simulation()
                else:
                    # 如果使用的是多进程模式
                    self.close_pybullet_simulation_multiprocess()
        except Exception as e:
            print(f"关闭仿真资源时出错: {str(e)}")

    def start_pybullet_simulation_multiprocess(self):
        """使用multiprocessing启动PyBullet GUI"""
        try:
            # Ensure freeze_support is called for PyInstaller compatibility
            multiprocessing.freeze_support()

            if self.operating_system == "Linux":
                multiprocessing.set_start_method('spawn', force=True)
            
            # 创建multiprocessing队列和事件
            self.robot_state_queue = multiprocessing.Queue()
            self.offline_params_queue = multiprocessing.Queue()
            self.shutdown_event = multiprocessing.Event()
            
            # 启动PyBullet GUI进程
            self.gui_process = multiprocessing.Process(
                target=pybullet_gui_process,
                args=(self.robot_state_queue, self.offline_params_queue, self.shutdown_event)
            )
            self.gui_process.daemon = True
            self.gui_process.start()
            
            # 发送初始的离线参数
            self.send_offline_params()
            
            # 发送初始的机器人状态
            self.send_robot_state()
            
            # 启动更新线程来定期发送状态更新
            self.update_thread = threading.Thread(target=self.update_robot_state_multiprocess)
            self.update_thread.daemon = True
            self.update_thread.start()
            
            # 启动监控线程
            self.monitor_thread = threading.Thread(target=self.monitor_multiprocess)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
            
            self.log_message("PyBullet GUI进程启动中(MacOS/Linux多线程模式较为缓慢)")
            
        except Exception as e:
            # 确保在出错时更新状态
            self.is_simulating = False
            self.start_simulation_button.configure(text=Config.current_lang["start_simulation"])
            self.start_simulation_button.configure(hover_color="#41d054")
            
            self.log_message(f"启动PyBullet仿真失败: {str(e)}")
            self.log_message(traceback.format_exc())

    def send_robot_state(self):
        """发送机器人状态到队列"""
        try:
            # 辅助函数，处理不同类型的数据结构
            def safe_convert_to_list(value):
                if value is None:
                    return []
                if hasattr(value, 'tolist'):  # 处理NumPy数组
                    return value.tolist()
                elif isinstance(value, (list, tuple)):  # 处理列表和元组
                    return list(value)
                else:  # 处理其他类型
                    return [value]
            
            # 创建状态数据
            robot_state = {
                'joint_angles': safe_convert_to_list(self.joint_angles),
                'tool_state': safe_convert_to_list(self.tool_state),
                'target_position': safe_convert_to_list(self.target_position) or [0, 0, 0],
                'target_orientation': safe_convert_to_list(self.target_orientation) or [0, 0, 0, 1]
            }
            
            # 发送到队列（非阻塞）
            if self.robot_state_queue is not None:
                try:
                    # 清空队列中的旧数据，只保留最新的
                    while not self.robot_state_queue.empty():
                        try:
                            self.robot_state_queue.get_nowait()
                        except queue.Empty:
                            break
                    
                    self.robot_state_queue.put_nowait(robot_state)
                except queue.Full:
                    pass  # 如果队列满了，丢弃这次更新
            
        except Exception as e:
            self.log_message(f"发送机器人状态失败: {str(e)}")

    def send_offline_params(self):
        """发送离线参数到队列"""
        try:
            # 递归函数来处理嵌套数据结构中的NumPy数组
            def convert_numpy_to_list(obj):
                if hasattr(obj, 'tolist'):  # NumPy数组
                    return obj.tolist()
                elif isinstance(obj, dict):
                    return {key: convert_numpy_to_list(value) for key, value in obj.items()}
                elif isinstance(obj, (list, tuple)):
                    return [convert_numpy_to_list(item) for item in obj]
                else:
                    return obj
            
            # 获取当前所有形状并转换NumPy数组
            current_shapes = self.physics_engine.get_shapes(self.client_name)
            current_shapes = convert_numpy_to_list(current_shapes)
            
            # 获取URDF路径
            urdf_path = self.physics_engine._clients[self.client_name]['urdf_path']
            
            # 处理tcp_offset：需要将位置从毫米转换为米，保持姿态不变
            tcp_offset_for_queue = [0, 0, 0, 0, 0, 0]
            if hasattr(self, 'tcp_offset') and self.tcp_offset is not None:
                tcp_offset_for_queue = [
                    self.tcp_offset[0] / 1000,  # x (毫米转米)
                    self.tcp_offset[1] / 1000,  # y (毫米转米)
                    self.tcp_offset[2] / 1000,  # z (毫米转米)
                    self.tcp_offset[3],         # roll (度，不变)
                    self.tcp_offset[4],         # pitch (度，不变)
                    self.tcp_offset[5]          # yaw (度，不变)
                ]
            
            # 获取关节组配置和关节类型信息
            joint_config = {
                'main_group_includes': list(self.main_group_includes),
                'tool_group_includes': list(self.tool_group_includes),
                'joint_types': {}
            }
            
            # 获取工具组关节的类型信息
            for joint_index in self.tool_group_includes:
                joint_info = ProfileManager.get_joint_by_index(joint_index)
                if joint_info:
                    # 使用字符串键以保持与 JSON 序列化后的一致性
                    joint_config['joint_types'][str(joint_index)] = joint_info.get("type", "unknown")
            
            # 使用self变量中的基座位姿
            base_position = self.base_position.tolist()
            base_orientation = self.base_orientation.tolist()
            
            # 创建离线参数数据
            offline_params = {
                'tcp_offset': tcp_offset_for_queue,
                'shapes': current_shapes,
                'urdf_path': urdf_path,
                'joint_config': joint_config,
                'is_simulating': self.is_simulating,
                'base_position': base_position,
                'base_orientation': base_orientation
            }
            
            # 发送到队列（非阻塞）
            if self.offline_params_queue is not None:
                try:
                    # 清空队列中的旧数据，只保留最新的
                    while not self.offline_params_queue.empty():
                        try:
                            self.offline_params_queue.get_nowait()
                        except queue.Empty:
                            break
                    
                    self.offline_params_queue.put_nowait(offline_params)
                except queue.Full:
                    pass  # 如果队列满了，丢弃这次更新
            
        except Exception as e:
            self.log_message(f"发送离线参数失败: {str(e)}")

    def update_robot_state_multiprocess(self):
        """定期更新机器人状态队列"""
        try:
            last_offline_update = 0
            while self.is_simulating and self.gui_process and self.gui_process.is_alive():
                # 更新频繁变化的机器人状态
                self.send_robot_state()
                
                # 每500ms检查一次是否需要更新离线参数
                current_time = time.time()
                if current_time - last_offline_update > 0.5:
                    self.send_offline_params()
                    last_offline_update = current_time
                
                # 60hz
                time.sleep(1.0/60.0)
        except Exception as e:
            self.log_message(f"更新机器人状态队列失败: {str(e)}")

    def monitor_multiprocess(self):
        """监控多进程是否还在运行，如果进程退出，则更新UI状态"""
        try:
            if self.gui_process is not None:
                # 等待进程退出
                self.gui_process.join()
                
                # 进程已退出，更新UI状态
                self.log_message("PyBullet GUI进程已退出")
                
                # 在主线程中更新UI
                if self.master.winfo_exists():  # 确保主窗口仍然存在
                    self.master.after(0, self.update_ui_after_multiprocess_exit)
        except Exception as e:
            self.log_message(f"监控多进程时出错: {str(e)}")

    def update_ui_after_multiprocess_exit(self):
        """在多进程退出后更新UI状态"""
        # 更新状态
        self.is_simulating = False
        self.start_simulation_button.configure(text=Config.current_lang["start_simulation"])
        self.start_simulation_button.configure(hover_color="#41d054")
        
        self.log_message("PyBullet GUI已关闭")

    def close_pybullet_simulation_multiprocess(self):
        """关闭多进程中运行的PyBullet GUI"""
        try:
            # 停止仿真状态
            self.is_simulating = False
            
            # 更新按钮状态
            self.start_simulation_button.configure(text=Config.current_lang["start_simulation"])
            self.start_simulation_button.configure(hover_color="#41d054")
            
            # 发送停止信号
            if self.shutdown_event is not None:
                self.shutdown_event.set()
                self.log_message("已发送停止信号到PyBullet GUI进程")
            
            # 发送最后的离线参数更新，通知进程关闭
            self.send_offline_params()
            
            # 给进程一些时间来停止
            time.sleep(0.2)
            
            # 检查进程是否存在并正在运行
            if self.gui_process is not None:
                # 尝试正常终止进程
                self.log_message("正在关闭PyBullet GUI进程...")
                
                if self.gui_process.is_alive():
                    # 尝试正常终止
                    self.gui_process.terminate()
                    
                    # 给进程一些时间来终止
                    try:
                        self.gui_process.join(timeout=5)
                    except:
                        pass
                    
                    # 如果进程仍在运行，强制终止
                    if self.gui_process.is_alive():
                        self.log_message("PyBullet GUI进程未响应，强制终止...")
                        self.gui_process.kill()
                        self.gui_process.join()
                
                # 清除进程引用
                self.gui_process = None
                
                self.log_message("PyBullet GUI已关闭")
            
            # 清理队列和事件
            if self.robot_state_queue is not None:
                self.robot_state_queue.close()
                self.robot_state_queue = None
            
            if self.offline_params_queue is not None:
                self.offline_params_queue.close()
                self.offline_params_queue = None
            
            if self.shutdown_event is not None:
                self.shutdown_event = None
            
        except Exception as e:
            # 确保在出错时也更新状态
            self.is_simulating = False
            self.start_simulation_button.configure(text=Config.current_lang["start_simulation"])
            self.start_simulation_button.configure(hover_color="#41d054")
            
            self.log_message(f"关闭PyBullet GUI进程失败: {str(e)}")
            self.log_message(traceback.format_exc())


    def update(self, state):
        self.joint_angles = state["joint_angles"]
        self.target_position = state["target_position"]
        self.target_orientation = state["target_orientation"]
        self.end_effector_link = state["end_effector_link"]
        self.tool_state = state["tool_state"]
        
        # 正确处理TCP偏移量：只有位置需要从米转换为毫米
        tcp_offset_raw = np.array(state["tcp_offset"])
        new_tcp_offset = np.array([
            tcp_offset_raw[0] * 1000,  # x (米转毫米)
            tcp_offset_raw[1] * 1000,  # y (米转毫米)
            tcp_offset_raw[2] * 1000,  # z (米转毫米)
            tcp_offset_raw[3],         # roll (度，不变)
            tcp_offset_raw[4],         # pitch (度，不变)
            tcp_offset_raw[5]          # yaw (度，不变)
        ])
        
        if not np.array_equal(self.tcp_offset, new_tcp_offset):
            # 更新tcp_offset值
            self.tcp_offset = new_tcp_offset
            
            # 更新UI中的输入框条目
            self.ee_x_pos.delete(0, 'end')
            self.ee_x_pos.insert(0, f"{self.tcp_offset[0]:.2f}")
            
            self.ee_y_pos.delete(0, 'end')
            self.ee_y_pos.insert(0, f"{self.tcp_offset[1]:.2f}")
            
            self.ee_z_pos.delete(0, 'end')
            self.ee_z_pos.insert(0, f"{self.tcp_offset[2]:.2f}")
            
            self.ee_roll.delete(0, 'end')
            self.ee_roll.insert(0, f"{self.tcp_offset[3]:.2f}")
            
            self.ee_pitch.delete(0, 'end')
            self.ee_pitch.insert(0, f"{self.tcp_offset[4]:.2f}")
            
            self.ee_yaw.delete(0, 'end')
            self.ee_yaw.insert(0, f"{self.tcp_offset[5]:.2f}")
        
        # 如果使用的是内部线程模式，则直接更新仿真状态
        if self.operating_system == "Windows" and self.is_simulating:
            self.update_simulation_state(self.joint_angles, self.tool_state)
            self.update_tcp_markers(self.target_position, self.target_orientation)

    def update_simulation_state(self, joint_angles, tool_state):
        """更新仿真状态"""
        try:
            robot_id = self.physics_engine.get_robot_id(self.client_name)
            
            if robot_id is not None:
                # 更新所有机械臂关节
                
                for idx in self.main_group_includes:
                    # 将角度转换为弧度
                    angle_rad = np.radians(joint_angles[idx])
                    
                    # 使用位置控制器来保持关节位置，抵抗重力
                    p.setJointMotorControl2(
                        robot_id,
                        idx,
                        p.POSITION_CONTROL,
                        targetPosition=angle_rad,
                        force=1000.0,  # 足够大的力来抵抗重力
                        physicsClientId=self.client_id
                    )

                for i in range(len(tool_state)):
                    joint_index = self.tool_group_includes[i]
                    type = ProfileManager.get_joint_by_index(joint_index)["type"]
                    if type == "revolute":
                        value = np.radians(tool_state[i])
                    elif type == "prismatic":
                        value = tool_state[i]
                    elif type == "fixed":
                        # Fixed joints don't need control, skip them
                        continue
                    else:
                        value = -1

                    if value != -1: 
                        # 使用位置控制器来保持工具关节位置
                        p.setJointMotorControl2(
                            robot_id,
                            joint_index,
                            p.POSITION_CONTROL,
                            targetPosition=value,
                            force=500.0,  # 工具关节通常需要较小的力
                            physicsClientId=self.client_id
                        )
                    
                    
        except Exception as e:
            print(f"更新仿真状态时出错: {str(e)}")
            if hasattr(self, 'update_terminal'):
                self.update_terminal(f"更新仿真状态时出错: {str(e)}")

    def update_tcp_markers(self, target_position, target_orientation, axis_length=0.05):
        """更新坐标系标记"""
        try:
            robot_id = self.physics_engine.get_robot_id(self.client_name)
            
            if robot_id is not None:
                # 直接使用目标位置和方向，而不是从末端执行器获取
                position = target_position
                orientation = target_orientation

                # 计算旋转矩阵
                rot_matrix = p.getMatrixFromQuaternion(orientation)
                rot_matrix = np.array(rot_matrix).reshape(3, 3)
                
                # 如果是第一次创建标记或标记已被删除
                if not hasattr(self, 'marker_ids') or not self.marker_ids:
                    self.marker_ids = []
                    # 绘制新的坐标轴
                    colors = [[1,0,0], [0,1,0], [0,0,1]]
                    
                    for i in range(3):
                        axis_vector = rot_matrix[:, i] * axis_length
                        end_point = [
                            position[0] + axis_vector[0],
                            position[1] + axis_vector[1],
                            position[2] + axis_vector[2]
                        ]
                        
                        marker_id = p.addUserDebugLine(
                            position,
                            end_point,
                            colors[i],
                            lineWidth=2.0,
                            physicsClientId=self.client_id
                        )
                        self.marker_ids.append(marker_id)
                else:
                    # 更新现有标记的位置
                    colors = [[1,0,0], [0,1,0], [0,0,1]]
                    
                    for i in range(3):
                        axis_vector = rot_matrix[:, i] * axis_length
                        end_point = [
                            position[0] + axis_vector[0],
                            position[1] + axis_vector[1],
                            position[2] + axis_vector[2]
                        ]
                        
                        p.addUserDebugLine(
                            position,
                            end_point,
                            colors[i],
                            lineWidth=2.0,
                            replaceItemUniqueId=self.marker_ids[i],
                            physicsClientId=self.client_id
                        )
                    
        except Exception as e:
            self.update_terminal(f"更新坐标系标记时出错: {str(e)}")

    def update_terminal(self, message):
        """更新终端显示"""
        if hasattr(self, 'terminal_text') and self.terminal_text.winfo_exists():
            self.terminal_text.configure(state=tk.NORMAL)
            self.terminal_text.insert(tk.END, f"{message}\n")
            self.terminal_text.see(tk.END)
            self.terminal_text.configure(state=tk.DISABLED)

    def load_world(self):
        """从文件加载世界状态"""
        try:
            # 打开文件对话框
            file_path = tk.filedialog.askopenfilename(
                defaultextension=".json",
                filetypes=[("JSON文件", "*.json")],
                title="加载世界"
            )
            
            if not file_path:
                return
            
            # 打开并读取文件
            with open(file_path, 'r', encoding='utf-8') as f:
                world_data = json.load(f)
            
            # 清除当前的所有形状
            self.clear_all_shapes()
            
            # 加载形状
            shapes = world_data.get('shapes', [])
            for shape_data in shapes:
                shape_type = shape_data.get('type', '')
                params = shape_data.get('parameters', {})
                
                if shape_type.startswith('导入URDF'):
                    self.physics_engine.load_urdf_model(
                        shape_data.get('file_path'),
                        position=params.get('position', [0, 0, 0]),
                        orientation=params.get('orientation', [0, 0, 0, 1]),
                        client_name=self.client_name
                    )
                elif shape_type.startswith('导入OBJ'):
                    self.physics_engine.load_obj_model(
                        shape_data.get('file_path'),
                        scale=params.get('scale', 1.0),
                        mass=params.get('mass', 1.0),
                        position=params.get('position', [0, 0, 0]),
                        orientation=params.get('orientation', [0, 0, 0, 1]),
                        client_name=self.client_name
                    )
                elif shape_type.startswith('导入STL'):
                    self.physics_engine.load_stl_model(
                        shape_data.get('file_path'),
                        scale=params.get('scale', 1.0),
                        mass=params.get('mass', 1.0),
                        position=params.get('position', [0, 0, 0]),
                        orientation=params.get('orientation', [0, 0, 0, 1]),
                        client_name=self.client_name
                    )
                elif shape_type.startswith('视觉_'):
                    visual_shape_type = shape_type.replace('视觉_', '')
                    params['rgba_color'] = shape_data.get('color', [1, 0, 0, 1])
                    self.physics_engine.create_visual_shape(visual_shape_type, params, self.client_name)
                else:
                    # 普通碰撞形状
                    self.physics_engine.create_collision_shape(shape_type, params, self.client_name)
            
            # 更新形状列表显示
            self.update_shapes_list()
            
            self.log_message(f"已加载世界状态从: {file_path}")
        except Exception as e:
            self.log_message(f"加载世界失败: {str(e)}")

    def clear_all_shapes(self):
        """清除所有现有形状"""
        try:
            # 使用物理引擎清除所有形状
            if self.physics_engine.remove_all_shapes(self.client_name):
                # 更新形状列表显示
                self.update_shapes_list()
                self.log_message("已清除所有现有形状")
            else:
                self.log_message("清除形状失败")
        except Exception as e:
            self.log_message(f"清除形状失败: {str(e)}")

    def open_pybullet_simulation(self):
        """打开PyBullet可视化窗口并更新机器人状态"""
        try:
            # 为可视化创建新的GUI模式客户端
            self.physics_engine.switch_client_mode(self.client_name, p.GUI)
            
            # 配置可视化器
            p.configureDebugVisualizer(p.COV_ENABLE_GUI, 1, physicsClientId=self.client_id)
            p.configureDebugVisualizer(p.COV_ENABLE_RENDERING, 1, physicsClientId=self.client_id)
            p.configureDebugVisualizer(p.COV_ENABLE_MOUSE_PICKING, 1, physicsClientId=self.client_id)
            p.configureDebugVisualizer(p.COV_ENABLE_RGB_BUFFER_PREVIEW, 0, physicsClientId=self.client_id)
            p.configureDebugVisualizer(p.COV_ENABLE_DEPTH_BUFFER_PREVIEW, 0, physicsClientId=self.client_id)
            p.configureDebugVisualizer(p.COV_ENABLE_SEGMENTATION_MARK_PREVIEW, 0, physicsClientId=self.client_id)
            
            # 设置相机视角
            p.resetDebugVisualizerCamera(
                cameraDistance=0.3,
                cameraYaw=50,
                cameraPitch=-35,
                cameraTargetPosition=[0, 0, 0],
                physicsClientId=self.client_id
            )

            # 创建末端执行器坐标系marker的线条ID列表
            self.marker_ids = []
            
            self.update_simulation_state(self.joint_angles, self.tool_state)
            self.update_tcp_markers(self.target_position, self.target_orientation)
            
            # 开始更新循环
            while p.isConnected(physicsClientId=self.client_id):
                p.stepSimulation(physicsClientId=self.client_id)  # 启用物理仿真步进
                time.sleep(1./240.)  # 240Hz
            
            # 无论如何都要确保状态被正确更新
            self.is_simulating = False
            
            # 更新按钮状态
            self.start_simulation_button.configure(text=Config.current_lang["start_simulation"])
            self.start_simulation_button.configure(hover_color="#41d054")
            
            try:
                # 尝试切换回DIRECT模式
                self.physics_engine.switch_client_mode(self.client_name, p.DIRECT)
            except Exception as e:
                print(f"切换回DIRECT模式失败: {str(e)}")

        except Exception as e:
            # 确保在出错时也更新状态
            self.is_simulating = False
            self.start_simulation_button.configure(text=Config.current_lang["start_simulation"])
            self.start_simulation_button.configure(hover_color="#41d054")
            
            messagebox.showerror("错误", f"打开PyBullet仿真失败: {str(e)}")
            self.update_terminal(f"错误: {str(e)}")

    def close_pybullet_simulation(self):
        """关闭PyBullet仿真"""
        try:
            # 停止仿真
            self.is_simulating = False
            
            # 更新按钮状态
            self.start_simulation_button.configure(text=Config.current_lang["start_simulation"])
            self.start_simulation_button.configure(hover_color="#41d054")
            
            # 清除所有marker
            if hasattr(self, 'marker_ids'):
                for marker_id in self.marker_ids:
                    try:
                        p.removeUserDebugItem(marker_id, physicsClientId=self.client_id)
                    except:
                        pass
                self.marker_ids.clear()
            
            # 断开GUI客户端连接
            self.physics_engine.switch_client_mode(self.client_name, p.DIRECT)
            
        except Exception as e:
            # 确保在出错时也更新状态
            self.is_simulating = False
            self.start_simulation_button.configure(text=Config.current_lang["start_simulation"])
            self.start_simulation_button.configure(hover_color="#41d054")
            
            self.update_terminal(f"关闭仿真时出错: {str(e)}")
    
    def trigger_offline_params_update(self):
        """触发离线参数更新（仅在模拟时）"""
        if self.is_simulating:
            # For non-Windows systems using multiprocessing
            if self.operating_system != "Windows" and self.offline_params_queue is not None:
                self.send_offline_params()

    def update_texts(self):
        """更新文本"""
        current_lang = Config.current_lang
        self.frame_label.configure(text=current_lang["simulator"])
        self.engine_label.configure(text=current_lang["simulator"])
        
        # 更新机器人状态框文本
        self.base_status_label.configure(text=current_lang["robot_status"])
        self.ee_status_label.configure(text=current_lang["end_effector_offset"])

        self.base_position_label.configure(text=current_lang["position"])
        self.base_orientation_label.configure(text=current_lang["orientation"])
        self.ee_position_label.configure(text=current_lang["position"])
        self.ee_orientation_label.configure(text=current_lang["orientation"])
        self.set_base_pose_button.configure(text=current_lang["set_base_pose"])
        self.ee_position_button.configure(text=current_lang["set_end_position"])
        self.save_world_button.configure(text=current_lang["save_world"])
        self.load_world_button.configure(text=current_lang["load_world"])
        
        # 根据模拟状态更新切换按钮文本
        if self.is_simulating:
            self.start_simulation_button.configure(text=current_lang["stop_simulation"])
        else:
            self.start_simulation_button.configure(text=current_lang["start_simulation"])
        
        # 更新形状管理按钮文本
        if hasattr(self, 'load_shape_button') and self.load_shape_button.winfo_exists():
            self.load_shape_button.configure(text=current_lang["load_shapes"])
            
        if hasattr(self, 'create_collision_shape_button') and self.create_collision_shape_button.winfo_exists():
            self.create_collision_shape_button.configure(text=current_lang["collision_shapes"])
            
        if hasattr(self, 'create_visual_shape_button') and self.create_visual_shape_button.winfo_exists():
            self.create_visual_shape_button.configure(text=current_lang["visual_shapes"])
        
        if hasattr(self, 'file_type_label') and self.file_type_label.winfo_exists():
            self.file_type_label.configure(text=current_lang["file_type"])
        
        if hasattr(self, 'file_path_label') and self.file_path_label.winfo_exists():
            self.file_path_label.configure(text=current_lang["file_path"])

        if hasattr(self, 'browse_button') and self.browse_button.winfo_exists():
            self.browse_button.configure(text=current_lang["browse"])

        if hasattr(self, 'load_pos_x_label') and self.load_pos_x_label.winfo_exists():
            self.load_pos_x_label.configure(text=current_lang["position"])

        if hasattr(self, 'load_rot_label') and self.load_rot_label.winfo_exists():
            self.load_rot_label.configure(text=current_lang["orientation"])

        if hasattr(self, 'scale_factor_label') and self.scale_factor_label.winfo_exists():
            self.scale_factor_label.configure(text=current_lang["scale_factor"])

        if hasattr(self, 'is_fixed') and self.is_fixed.winfo_exists():
            self.is_fixed.configure(text=current_lang["fixed_object"])

        if hasattr(self, 'collision_is_fixed') and self.collision_is_fixed.winfo_exists():
            self.collision_is_fixed.configure(text=current_lang["fixed_object"])

        if hasattr(self, 'load_button') and self.load_button.winfo_exists():
            self.load_button.configure(text=current_lang["load_model"])

        if hasattr(self, 'shape_type_label') and self.shape_type_label.winfo_exists():
            self.shape_type_label.configure(text=current_lang["shape_type"])

        if hasattr(self, 'collision_pos_x_label') and self.collision_pos_x_label.winfo_exists():
            self.collision_pos_x_label.configure(text=current_lang["position"])

        if hasattr(self, 'collision_rot_label') and self.collision_rot_label.winfo_exists():
            self.collision_rot_label.configure(text=current_lang["orientation"])

        if hasattr(self, 'sphere_radius_label') and self.sphere_radius_label.winfo_exists():
            self.sphere_radius_label.configure(text=current_lang["radius"] + " (m):")

        if hasattr(self, 'box_dimensions_label') and self.box_dimensions_label.winfo_exists():
            self.box_dimensions_label.configure(text=current_lang["size"])

        if hasattr(self, 'cylinder_radius_label') and self.cylinder_radius_label.winfo_exists():
            self.cylinder_radius_label.configure(text=current_lang["radius"] + " (m):")

        if hasattr(self, 'cylinder_height_label') and self.cylinder_height_label.winfo_exists():
            self.cylinder_height_label.configure(text=current_lang["height"])

        if hasattr(self, 'capsule_radius_label') and self.capsule_radius_label.winfo_exists():
            self.capsule_radius_label.configure(text=current_lang["radius"] + " (m):")

        if hasattr(self, 'visual_shape_type_label') and self.visual_shape_type_label.winfo_exists():
            self.visual_shape_type_label.configure(text=current_lang["shape_type"])

        if hasattr(self, 'visual_pos_x_label') and self.visual_pos_x_label.winfo_exists():
            self.visual_pos_x_label.configure(text=current_lang["position"])

        if hasattr(self, 'visual_rot_label') and self.visual_rot_label.winfo_exists():
            self.visual_rot_label.configure(text=current_lang["orientation"])

        if hasattr(self, 'visual_color_label') and self.visual_color_label.winfo_exists():
            self.visual_color_label.configure(text=current_lang["color"])

        if hasattr(self, 'visual_alpha_label') and self.visual_alpha_label.winfo_exists():
            self.visual_alpha_label.configure(text=current_lang["alpha"])

        if hasattr(self, 'collision_create_button') and self.collision_create_button.winfo_exists():
            self.collision_create_button.configure(text=current_lang["create"])

        if hasattr(self, 'visual_create_button') and self.visual_create_button.winfo_exists():
            self.visual_create_button.configure(text=current_lang["create"])

        if hasattr(self, 'visual_radius_label') and self.visual_radius_label.winfo_exists():
            self.visual_radius_label.configure(text=current_lang["radius"] + " (m):")

        if hasattr(self, 'visual_length_label') and self.visual_length_label.winfo_exists():
            self.visual_length_label.configure(text=current_lang["size"] + " (m):")

        if hasattr(self, 'visual_height_label') and self.visual_height_label.winfo_exists():
            self.visual_height_label.configure(text=current_lang["height"] + " (m):")
