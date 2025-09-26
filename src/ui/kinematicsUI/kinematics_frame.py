import os
import time
import numpy as np
import pybullet as p
import tkinter as tk
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText
import customtkinter as ctk
from PIL import Image

from ui.kinematicsUI.gcodeUI.gcode_ui import GCodeUI
from ui.kinematicsUI.visionUI.vision_frame import VisionFrame
from utils.resource_loader import ResourceLoader
from utils.config import Config
from ui.kinematicsUI.task_board import TaskBoard
from ui.kinematicsUI.solver_manager import SolverManager
from ui.kinematicsUI.workspaceUI.workspace_frame import WorkspaceFrame
from noman.motion_planner.planner import Planner
from noman.motion_planner.coordinate_systems import CoordinateManager
from noman.profile_manager import ProfileManager
from noman.TrajOptimiser import TrajOptimiser, TrajConstraints
from protocol.serial_protocol import SerialProtocol, SerialCommands
from protocol.can_protocol import CanProtocol, CANCommands

class KinematicsFrame(ctk.CTkFrame):
    def __init__(self, master, robot_state):
        super().__init__(master)
        self.protocol_class = None
        self.operating_system = Config.operating_system

        self.grid_columnconfigure(0, weight=1)
        
        self.planner = None
        self.current_solver = "LevenbergMarquardt"
        self.planner_method = "Direct"

        self.main_group = None
        self.tool_group = None
        self.actuation = None
        
        self.joint_entries = []
        self.joint_limits = []
        self.home_values = [0, 0, 360, 0]  # home position
        self.joint_angles = np.array([0, 0, 360, 0])
        self.end_effector_link = 0
        self.num_joints = 4
        self.tool_command = []
        self.last_planner_result = None  # Store the last planner result for trajectory execution

        self.end_effector_home = np.array([0.011937, 0.000743, 0.111300])
        self.target_position = np.array([0.011937, 0.000743, 0.111300])
        self.target_orientation = np.array([0,0,0])
        self.orientation_constraints = [True, True, True]  # R, P, Y constraints, default all enabled
        self.current_coordinate = "Base"  # 当前坐标系，默认为base
        
        # initialize coordinate manager
        self.coordinate_manager = CoordinateManager()
        
        # initialize trajectory optimizer
        self.traj_optimiser = TrajOptimiser(dt=Config.dt)
        self.traj_constraints = None
        self.velocity_limits = []

        # add workspace boundary property
        self.workspace = {
            'analyzed': False,
            'bounds': {
                'x': {'min': None, 'max': None},
                'y': {'min': None, 'max': None},
                'z': {'min': None, 'max': None}
            }
        }

        self.question_icon = ctk.CTkImage(
            Image.open(ResourceLoader.get_asset_path(os.path.join("icons", "question_white.png"))).convert("RGBA"), 
            size=(15, 15)
        )

        self.robot_state = robot_state
        self.robot_state.add_observer(self)

        try:
            self.load_robot_profile(init=True)
        except FileNotFoundError:
            self.update_terminal("Warning: Default URDF file not found")

        self.setup_ui()
        self.update_ui(update_joint_control=False, update_entries=True)

    def setup_ui(self):
        self.setup_banner()
        self.setup_hyperparams_frame()
        self.setup_kinematics_frames()
        self.setup_advanced_frame()
        self.setup_log_frame()
        self.update_terminal("* Self-collision initalisation incomplete.\n* Workspace analysis incomplete.")

    def setup_banner(self):
        # upper frame
        self.banner_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.banner_frame.grid(row=0, column=0, padx=10, pady=(10,0), sticky="ew")
        self.banner_frame.grid_columnconfigure(1, weight=1)
        
        # upper left
        self.upper_left_frame = ctk.CTkFrame(self.banner_frame, fg_color="transparent")
        self.upper_left_frame.grid(row=0, column=0, sticky="w")
        
        self.frame_label = ctk.CTkLabel(self.upper_left_frame, text=Config.current_lang["kinematics"], font=("Arial", 16), anchor='w')
        self.frame_label.grid(row=0, column=0, padx=10, pady=(8,0), sticky="w")
        
        separator = ctk.CTkFrame(self.upper_left_frame, height=2, width=180, fg_color="black")
        separator.grid(row=1, column=0, sticky="w", padx=10, pady=(5,10))
        
        # upper right
        self.upper_right_frame = ctk.CTkFrame(self.banner_frame, fg_color="transparent")
        self.upper_right_frame.grid(row=0, column=1, sticky="e")

        self.taskboard_frame = ctk.CTkFrame(self.upper_right_frame, fg_color="transparent")
        self.taskboard_frame.grid(row=0, column=0, sticky="e")
        self.taskboard_label = ctk.CTkLabel(self.taskboard_frame, text="Task Board")
        self.taskboard_label.grid(row=0, column=0, sticky="w")
        
        # Task board switch
        self.task_var = tk.BooleanVar(value=False)
        self.task_switch = ctk.CTkSwitch(
            self.taskboard_frame,
            text="",
            variable=self.task_var,
            command=self.on_task_toggle,
            width=60
        )
        self.task_switch.grid(row=0, column=1, padx=(10,0), sticky="e")

    def setup_hyperparams_frame(self):
        """Hyperparameter frame"""
        self.hyperparams_frame = ctk.CTkFrame(self, fg_color="#B3B3B3", height=180)
        self.hyperparams_frame.grid(row=1, column=0, columnspan=2, padx=20, pady=(10,21), sticky="nsew")
        self.hyperparams_frame.grid_columnconfigure(0, weight=1)
        self.hyperparams_frame.grid_propagate(False)  

        # title
        self.hyperparams_label = ctk.CTkLabel(self.hyperparams_frame, text=Config.current_lang["solver_init"])
        self.hyperparams_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")

        # planner frame
        self.planner_frame = ctk.CTkFrame(self.hyperparams_frame, fg_color="#B3B3B3")
        self.planner_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        self.planner_frame.grid_columnconfigure(1, weight=1)

        self.planner_label = ctk.CTkLabel(self.planner_frame, text=Config.current_lang["planner"])
        self.planner_label.grid(row=0, column=0, padx=(5,10), pady=5, sticky="w")
        
        self.planner_var = ctk.StringVar(value="Direct")
        self.planner_menu = ctk.CTkOptionMenu(
            self.planner_frame,
            variable=self.planner_var,
            values=["Direct", "RRT", "CHOMP"],
            width=120
        )
        self.planner_menu.grid(row=0, column=1, padx=10, pady=5, sticky="w")


        # solver frame
        self.solver_label = ctk.CTkLabel(self.planner_frame, text=Config.current_lang["solver"])
        self.solver_label.grid(row=0, column=2, padx=(5,10), pady=5, sticky="w")
        self.solver_var = ctk.StringVar(value="LevenbergMarquardt")
        self.solver_menu = ctk.CTkOptionMenu(
            self.planner_frame, 
            variable=self.solver_var,
            values=self.get_available_solvers(),
            command=self.on_solver_change,
            width=250
        )
        self.solver_menu.grid(row=0, column=3, padx=10, pady=5, sticky="w")

        self.manage_solvers_button = ctk.CTkButton(
            self.planner_frame,
            text="+",
            command=self.show_solver_manager,
            width=30,
            hover_color="#41d054"
        )
        self.manage_solvers_button.grid(row=0, column=3, padx=(270,20), pady=5, sticky="w")

        # param frame with respect to chosen solver
        self.params_frame = ctk.CTkFrame(self.hyperparams_frame, fg_color="#B3B3B3")
        self.params_frame.grid(row=2, column=0, padx=10, pady=5, sticky="nsew")

        # Levenberg-Marquardt
        self.lm_params_frame = ctk.CTkFrame(self.params_frame, fg_color="#B3B3B3")
        self.lm_params_frame.grid(row=0, column=0, sticky="nsew")
        
        self.lm_lambda_label = ctk.CTkLabel(self.lm_params_frame, text="λ:")
        self.lm_lambda_label.grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.lm_lambda_entry = ctk.CTkEntry(self.lm_params_frame, width=60)
        self.lm_lambda_entry.grid(row=0, column=1, padx=(5,45), pady=5, sticky="w")
        self.lm_lambda_entry.insert(0, str(Config.lm_lambda))

        self.lm_epsilon_label = ctk.CTkLabel(self.lm_params_frame, text="ε:")
        self.lm_epsilon_label.grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.lm_epsilon_entry = ctk.CTkEntry(self.lm_params_frame, width=60)
        self.lm_epsilon_entry.grid(row=0, column=3, padx=(5,45), pady=5, sticky="w")
        self.lm_epsilon_entry.insert(0, str(Config.lm_epsilon))

        self.lm_max_iterations_label = ctk.CTkLabel(self.lm_params_frame, text=Config.current_lang["max_iterations"])
        self.lm_max_iterations_label.grid(row=0, column=4, padx=5, pady=5, sticky="e")
        self.lm_max_iterations_entry = ctk.CTkEntry(self.lm_params_frame, width=60)
        self.lm_max_iterations_entry.grid(row=0, column=5, padx=5, pady=5, sticky="w")
        self.lm_max_iterations_entry.insert(0, str(Config.lm_max_iterations))

        # Damped Least Square
        self.dls_params_frame = ctk.CTkFrame(self.params_frame, fg_color="#B3B3B3")
        self.dls_params_frame.grid(row=0, column=0, sticky="nsew")
        
        self.dls_damping_label = ctk.CTkLabel(self.dls_params_frame, text=Config.current_lang["dls_damping"])
        self.dls_damping_label.grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.dls_damping_entry = ctk.CTkEntry(self.dls_params_frame, width=60)
        self.dls_damping_entry.grid(row=0, column=1, padx=(5,45), pady=5, sticky="w")
        self.dls_damping_entry.insert(0, str(Config.dls_damping))

        self.dls_epsilon_label = ctk.CTkLabel(self.dls_params_frame, text=Config.current_lang["dls_epsilon"])
        self.dls_epsilon_label.grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.dls_epsilon_entry = ctk.CTkEntry(self.dls_params_frame, width=60)
        self.dls_epsilon_entry.grid(row=0, column=3, padx=(5,45), pady=5, sticky="w")
        self.dls_epsilon_entry.insert(0, str(Config.dls_epsilon))

        self.dls_max_iterations_label = ctk.CTkLabel(self.dls_params_frame, text=Config.current_lang["max_iterations"])
        self.dls_max_iterations_label.grid(row=0, column=4, padx=5, pady=5, sticky="e")
        self.dls_max_iterations_entry = ctk.CTkEntry(self.dls_params_frame, width=60)
        self.dls_max_iterations_entry.grid(row=0, column=5, padx=5, pady=5, sticky="w")
        self.dls_max_iterations_entry.insert(0, str(Config.dls_max_iterations))
        
        # TRAC-IK
        self.trac_ik_params_frame = ctk.CTkFrame(self.params_frame, fg_color="#B3B3B3")
        self.trac_ik_params_frame.grid(row=0, column=0, sticky="nsew")
        
        self.trac_ik_epsilon_label = ctk.CTkLabel(self.trac_ik_params_frame, text=Config.current_lang["trac_ik_epsilon"])
        self.trac_ik_epsilon_label.grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.trac_ik_epsilon_entry = ctk.CTkEntry(self.trac_ik_params_frame, width=60)
        self.trac_ik_epsilon_entry.grid(row=0, column=1, padx=(5,45), pady=5, sticky="w")
        self.trac_ik_epsilon_entry.insert(0, str(Config.trac_ik_epsilon))

        self.trac_ik_max_iterations_label = ctk.CTkLabel(self.trac_ik_params_frame, text=Config.current_lang["max_iterations"])
        self.trac_ik_max_iterations_label.grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.trac_ik_max_iterations_entry = ctk.CTkEntry(self.trac_ik_params_frame, width=60)
        self.trac_ik_max_iterations_entry.grid(row=0, column=3, padx=5, pady=5, sticky="w")
        self.trac_ik_max_iterations_entry.insert(0, str(Config.trac_ik_max_iterations))

        # Buttons
        self.button_frame = ctk.CTkFrame(self.hyperparams_frame, fg_color="transparent")
        self.button_frame.grid(row=3, column=0, padx=10, pady=5, sticky="nsew")
        self.button_frame.grid_columnconfigure(0, weight=1)
        self.button_frame.grid_columnconfigure(1, weight=1)


        self.pathpoint_frame = ctk.CTkFrame(self.button_frame, fg_color="transparent")
        self.pathpoint_frame.grid(row=0, column=0, padx=5, sticky="w")
        
        self.num_pathpoints_label = ctk.CTkLabel(self.pathpoint_frame, text=Config.current_lang["pathpoints"])
        self.num_pathpoints_label.grid(row=0, column=0, padx=(0,12), pady=2, sticky="w")
        
        self.num_pathpoints_entry = ctk.CTkEntry(self.pathpoint_frame, width=50)
        self.num_pathpoints_entry.insert(0, "1")
        self.num_pathpoints_entry.grid(row=0, column=1, padx=5, pady=2, sticky="w")

        self.buttons_container = ctk.CTkFrame(self.button_frame, fg_color="transparent")
        self.buttons_container.grid(row=0, column=1, columnspan=2, sticky="e")

        # self-collision button
        self.self_collision_button = ctk.CTkButton(
            self.buttons_container,
            text=Config.current_lang["self_collision_check"],
            command=self.on_self_collision_check,
            hover_color="#41d054"
        )
        self.self_collision_button.grid(row=0, column=1, padx=(0,10), pady=2, sticky="e")

        # apply button
        self.apply_hyperparams_button = ctk.CTkButton(self.buttons_container, 
                                                    text=Config.current_lang["apply"],
                                                    command=self.apply_hyperparams,
                                                    hover_color="#41d054")
        self.apply_hyperparams_button.grid(row=0, column=2, padx=10, pady=2, sticky="e")

        # hide other two frames
        self.dls_params_frame.grid_remove()
        self.trac_ik_params_frame.grid_remove()

    def setup_kinematics_frames(self):
        """Setup forward/inverse kinematics frame"""
        # 正向运动学框架
        self.kinematics_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.kinematics_frame.grid(row=2, column=0, padx=20, pady=21, sticky="nsew")
        self.kinematics_frame.grid_columnconfigure(0, weight=1)
        self.kinematics_frame.grid_columnconfigure(1, weight=1)

        self.fk_frame = ctk.CTkFrame(self.kinematics_frame, fg_color="#B3B3B3")
        self.fk_frame.grid(row=0, column=0, padx=(0,10), pady=0, sticky="nsew")
        self.fk_frame.grid_rowconfigure(1, weight=1)

        self.fk_label = ctk.CTkLabel(self.fk_frame, text=Config.current_lang["forward_kinematics"])
        self.fk_label.grid(row=0, column=0, columnspan=2, padx=10, pady=5, sticky="w")

        self.fk_top_frame = ctk.CTkFrame(self.fk_frame, fg_color="transparent")
        self.fk_top_frame.grid(row=1, column=0, padx=5, pady=0, sticky="nsew")
        
        self.fk_btm_frame = ctk.CTkFrame(self.fk_frame, fg_color="transparent")
        self.fk_btm_frame.grid(row=2, column=0, padx=5, pady=(0,10), sticky="ew")
        self.fk_btm_frame.grid_columnconfigure(0, weight=1)

        self.setup_joint_control(self.fk_top_frame, self.num_joints, self.joint_limits)
        self.setup_tools(self.fk_top_frame)

        self.set_home_button = ctk.CTkButton(self.fk_btm_frame,
                                          text=Config.current_lang["home"],
                                          command=self.home,
                                          width=80,
                                          hover_color="#41d054")
        self.set_home_button.grid(row=0, column=0, padx=(0,7), pady=(15,5), sticky="e")

        # 逆向运动学框架
        self.ik_frame = ctk.CTkFrame(self.kinematics_frame, fg_color="#B3B3B3")
        self.ik_frame.grid(row=0, column=1, padx=(20,0), pady=0, sticky="nsew")
        self.ik_frame.grid_rowconfigure(0, weight=1)
        
        self.ik_top_frame = ctk.CTkFrame(self.ik_frame, fg_color="transparent")
        self.ik_top_frame.grid(row=0, column=0, padx=3, pady=0, sticky="nsew")
        
        self.ik_btm_frame = ctk.CTkFrame(self.ik_frame, fg_color="transparent")
        self.ik_btm_frame.grid(row=1, column=0, padx=3, pady=(0,10), sticky="ew")
        self.ik_btm_frame.grid_columnconfigure(0, weight=1)

        self.ik_label = ctk.CTkLabel(self.ik_top_frame, text=Config.current_lang["inverse_kinematics"])
        self.ik_label.grid(row=0, column=0, columnspan=3, padx=10, pady=5, sticky="w")

        # 创建坐标系选择框架
        self.coordinate_frame = ctk.CTkFrame(self.ik_top_frame, fg_color="transparent")
        self.coordinate_frame.grid(row=1, column=0, columnspan=4, padx=10, pady=5, sticky="ew")
        
        self.coordinate_label = ctk.CTkLabel(self.coordinate_frame, text=Config.current_lang["coordinate_system"])
        self.coordinate_label.grid(row=0, column=0, padx=(0,10), pady=0, sticky="w")
        
        self.coordinate_var = ctk.StringVar(value="Base")
        self.coordinate_menu = ctk.CTkOptionMenu(
            self.coordinate_frame,
            variable=self.coordinate_var,
            values=["Base", "Tool0"],
            command=self.on_coordinate_change,
            width=100
        )
        self.coordinate_menu.grid(row=0, column=1, padx=0, pady=0, sticky="w")
        
        # 创建位姿输入框架
        self.pose_frame = ctk.CTkFrame(self.ik_top_frame, fg_color="transparent")
        self.pose_frame.grid(row=2, column=0, columnspan=4, padx=10, pady=5, sticky="ew")
        
        # 设置目标位置输入
        self.target_entries = []
        self.orientation_entries = []
        self.orientation_checkboxes = []  # 添加姿态约束复选框列表
        
        for i, axis in enumerate(['X-', 'Y-', 'Z-']):
            target_label = ctk.CTkLabel(self.pose_frame, text=f"{axis}")
            target_label.grid(row=i, column=0, padx=(0,5), pady=5, sticky="w")
            
            target_entry = ctk.CTkEntry(self.pose_frame, width=80)
            target_entry.grid(row=i, column=1, padx=(10,0), pady=5, sticky="w")
            target_entry.insert(0, f"{self.target_position[i]:.6f}")
            target_entry.bind('<Return>', lambda e, i=i: self.on_target_change())  # 添加回车回调
            self.target_entries.append(target_entry)
            
            # 添加加减按钮框架
            button_frame = ctk.CTkFrame(self.pose_frame, fg_color="transparent")
            button_frame.grid(row=i, column=2, padx=(15,0), pady=5)
            
            minus_button = ctk.CTkButton(button_frame, text="-", width=30, 
                                        command=lambda i=i: self.adjust_target_value(i, -Config.position_steps),
                                        hover_color="#41d054")
            minus_button.grid(row=0, column=0, padx=0)
            
            plus_button = ctk.CTkButton(button_frame, text="+", width=30,
                                       command=lambda i=i: self.adjust_target_value(i, Config.position_steps),
                                       hover_color="#41d054")
            plus_button.grid(row=0, column=1, padx=(1,0))

        # 姿态输入框
        for i, angle in enumerate(['R-', 'P-', 'Y-']):
            orientation_label = ctk.CTkLabel(self.pose_frame, text=f"{angle}")
            orientation_label.grid(row=i+3, column=0, padx=(0,5), pady=5, sticky="w")
            
            orientation_entry = ctk.CTkEntry(self.pose_frame, width=80)
            orientation_entry.grid(row=i+3, column=1, padx=(10,0), pady=5, sticky="w")
            orientation_entry.insert(0, f"{self.target_orientation[i]:.1f}")
            orientation_entry.bind('<Return>', lambda e, i=i: self.on_orientation_change())  # 添加回车回调
            self.orientation_entries.append(orientation_entry)
            
            # 添加加减按钮框架
            button_frame = ctk.CTkFrame(self.pose_frame, fg_color="transparent")
            button_frame.grid(row=i+3, column=2, padx=(15,0), pady=5)
            
            minus_button = ctk.CTkButton(button_frame, text="-", width=30,
                                        command=lambda i=i: self.adjust_orientation_value(i, -Config.orientation_steps),
                                        hover_color="#41d054")
            minus_button.grid(row=0, column=0, padx=0)
            
            plus_button = ctk.CTkButton(button_frame, text="+", width=30,
                                        command=lambda i=i: self.adjust_orientation_value(i, Config.orientation_steps),
                                        hover_color="#41d054")
            plus_button.grid(row=0, column=1, padx=(1,0))
            
            # 添加姿态约束复选框
            constraint_var = tk.BooleanVar(value=self.orientation_constraints[i])
            constraint_checkbox = ctk.CTkCheckBox(
                self.pose_frame,
                text="",
                variable=constraint_var,
                command=lambda i=i: self.on_orientation_constraint_change(i),
                width=30
            )
            constraint_checkbox.grid(row=i+3, column=3, padx=(5,0), sticky="w")
            self.orientation_checkboxes.append((constraint_checkbox, constraint_var))
        
        self.send_button = ctk.CTkButton(self.ik_btm_frame, 
                                      text=Config.current_lang["send_to_robot"], 
                                      command=self.send_to_robot, 
                                      width=80, 
                                      hover_color="#41d054")
        self.send_button.grid(row=0, column=0, padx=(0,7), pady=(15,5), sticky="e")

    def setup_advanced_frame(self):
        self.advanced_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.advanced_frame.grid(row=3, column=0, columnspan=2, padx=20, pady=10, sticky="nsew")
        # 配置列权重使按钮平均分布
        self.advanced_frame.grid_columnconfigure(0, weight=1)
        self.advanced_frame.grid_columnconfigure(1, weight=1)
        self.advanced_frame.grid_columnconfigure(2, weight=1)

        self.camera_controller_button = ctk.CTkButton(self.advanced_frame, text=Config.current_lang["control_with_vision"], 
                                                    command=self.open_camera_controller, width=80, height=41, hover_color="#41d054")
        self.camera_controller_button.grid(row=0, column=0, padx=(0,5), pady=5, sticky="ew")
        
        self.robot_language_button = ctk.CTkButton(self.advanced_frame, text=Config.current_lang["robot_control_language"], 
                                                    command=self.open_gcode_ui, width=80, height=41, hover_color="#41d054")
        self.robot_language_button.grid(row=0, column=1, padx=(5,5), pady=5, sticky="ew")

        self.workspace_button = ctk.CTkButton(self.advanced_frame, text=Config.current_lang["workspace_analyzer"],
                                        command=self.open_workspace_analyzer, width=80, height=41, hover_color="#41d054")
        self.workspace_button.grid(row=0, column=2, padx=(5,0), pady=5, sticky="ew")

    def setup_log_frame(self):
        self.command_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.command_frame.grid(row=4, column=0, columnspan=2, padx=20, pady=21, sticky="nsew")
        self.log_text = ScrolledText(self.command_frame, state=tk.DISABLED, wrap=tk.WORD, 
                                     background="#000000", foreground="#41d054",
                                     width=50, height=10)
        self.log_text.pack(fill="both", expand=True)

    def on_task_toggle(self):
        """处理Task Board开关状态改变"""
        if self.task_var.get():
            self.update_terminal("Task Board已启用")
            # 检查task_board属性是否存在，或者dialog是否已销毁
            if not hasattr(self, 'task_board') or not self.task_board.dialog or not self.task_board.dialog.winfo_exists():
                self.task_board = TaskBoard(self)
        else:
            self.update_terminal("Task Board已禁用")
            if hasattr(self, 'task_board'):
                self.task_board.destroy()
                delattr(self, 'task_board')
    
    def on_solver_change(self, solver):
        """处理求解器切换"""
        self.current_solver = solver
        if solver == "LevenbergMarquardt":
            self.lm_params_frame.grid(row=0, column=0, sticky="nsew")
            self.dls_params_frame.grid_remove()
            self.trac_ik_params_frame.grid_remove()
        elif solver == "DampedLeastSquares":
            self.lm_params_frame.grid_remove()
            self.dls_params_frame.grid(row=0, column=0, sticky="nsew")
            self.trac_ik_params_frame.grid_remove()
        elif solver == "TRAC-IK":
            self.lm_params_frame.grid_remove()
            self.dls_params_frame.grid_remove()
            self.trac_ik_params_frame.grid(row=0, column=0, sticky="nsew")

    def setup_joint_control(self, frame, num_joints, joint_limits):
        # 首先清除frame中已有的所有控件
        for widget in frame.winfo_children():
            widget.grid_forget()
            widget.destroy()
        
        self.joint_entries = []

        # 设置关节控制
        for i in range(num_joints):
            joint_label = ctk.CTkLabel(frame, text=f"Joint {i+1}:")
            joint_label.grid(row=i+1, column=0, padx=10, pady=5, sticky="w")
            
            joint_slider = ctk.CTkSlider(frame, 
                                        from_=joint_limits[i][0], to=joint_limits[i][1],  # 临时范围
                                        number_of_steps=180,
                                        width=135,
                                        command=lambda v, i=i: self.on_joint_change(i))  # 添加回调
            joint_slider.grid(row=i+1, column=1, padx=10, pady=5, sticky="w")
            
            initial_value = round(self.home_values[i], 2)
            joint_slider.set(initial_value)
            
            joint_value = ctk.CTkLabel(frame, text=f"{initial_value}°")
            joint_value.grid(row=i+1, column=2, padx=10, pady=5)
            
            fine_tune_frame = ctk.CTkFrame(frame, fg_color="transparent")
            fine_tune_frame.grid(row=i+1, column=3, padx=10, pady=5)
            
            minus_button = ctk.CTkButton(fine_tune_frame, text="-", width=30, 
                                    command=lambda i=i: self.fine_tune_joint(i, -1), hover_color="#41d054")
            minus_button.grid(row=0, column=0, padx=0)
            
            plus_button = ctk.CTkButton(fine_tune_frame, text="+", width=30, 
                                    command=lambda i=i: self.fine_tune_joint(i, 1), hover_color="#41d054")
            plus_button.grid(row=0, column=1, padx=(1,0))
            
            self.joint_entries.append((joint_slider, joint_value))

    def setup_tools(self, frame):
        """设置工具控制，根据工具组配置创建相应的控制界面"""
        # 清除现有的工具控件
        for widget in frame.winfo_children():
            if widget.grid_info().get('row', 0) > self.num_joints:
                widget.grid_forget()
                widget.destroy()
        
        if not self.tool_group:
            return
        
        self.tool_label = ctk.CTkLabel(frame, text=Config.current_lang["tool"])
        self.tool_label.grid(row=self.num_joints+1, column=0, padx=(10,0), pady=5, sticky="w")
        
        if self.actuation == "signal":
            # Simple toggle for signal-based control
            self.gripper_switch = ctk.CTkSwitch(frame, text="", command=self.on_gripper_toggle)
            self.gripper_switch.grid(row=self.num_joints+1, column=1, padx=10, pady=5, sticky="w")
            
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
                slider_steps = (max_limit - min_limit) * 1000 # per 2mm
            else:
                unit = ""
                slider_steps = 1
            
            self.gripper_slider = ctk.CTkSlider(
                frame,
                from_=min_limit,
                to=max_limit,
                number_of_steps=slider_steps,
                command=self.on_uniform_gripper_change,
                width=80
            )
            self.gripper_slider.set(initial_value)
            self.gripper_slider.grid(row=self.num_joints+1, column=1, padx=10, pady=5, sticky="w")
            
            self.gripper_value_label = ctk.CTkLabel(frame, text=f"{initial_value} {unit}")
            self.gripper_value_label.grid(row=self.num_joints+1, column=1, padx=(100,0), pady=5, sticky="w")
            
        elif self.actuation == "independent movable":
            # Individual sliders for each joint in tool group
            self.gripper_sliders = []
            self.gripper_labels = []
            
            for i, joint in enumerate(self.tool_group):
                # 只处理有limit属性的关节
                if "limit" not in joint:
                    continue
                    
                row_offset = self.num_joints + 1 + i  # Start after main joints
 
                slider_steps = 0
                if joint["type"] == "revolute":
                    unit = "°"
                    slider_steps = joint["limit"]["upper"] - joint["limit"]["lower"]
                elif joint["type"] == "prismatic":
                    unit = "m"
                    slider_steps = (joint["limit"]["upper"] - joint["limit"]["lower"]) * 1000 # per 2mm
                else:
                    continue  # 跳过不支持的关节类型
                
                # Joint label
                joint_label = ctk.CTkLabel(frame, text=f"{joint['name']}")
                joint_label.grid(row=row_offset, column=0, padx=10, pady=5, sticky="w")
                
                # Joint slider
                slider = ctk.CTkSlider(
                    frame,
                    from_=joint["limit"]["lower"],
                    to=joint["limit"]["upper"],
                    number_of_steps=int(slider_steps),
                    command=lambda v, idx=i: self.on_independent_gripper_change(idx),
                    width=80
                )
                slider.set(joint["home"])
                slider.grid(row=row_offset, column=1, padx=10, pady=5, sticky="w")
                
                # Value label
                value_label = ctk.CTkLabel(frame, text=f"{joint['home']} {unit}")
                value_label.grid(row=row_offset, column=1, padx=(100,0), pady=5, sticky="w")
                
                self.gripper_sliders.append(slider)
                self.gripper_labels.append(value_label)

    def fine_tune_joint(self, index, direction):
        """修改微调函数以包含自动更新"""
        slider, value_label = self.joint_entries[index]
        current_value = slider.get()
        
        # 根据关节限制设置范围
        lower_limit = self.joint_limits[index][0]
        upper_limit = self.joint_limits[index][1]
        new_value = max(lower_limit, min(upper_limit, current_value + direction))
        
        slider.set(new_value)
        self.on_joint_change(index)  # 触发自动更新

    def update_joint_value(self, index):
        slider, value_label = self.joint_entries[index]
        value = int(slider.get())
        value_label.configure(text=f"{value}°")


    def on_gripper_toggle(self):
        """处理信号控制型夹爪的开关"""
        if hasattr(self, 'gripper_switch'):
            gripper_open = self.gripper_switch.get()
            
            # 更新工具命令值
            tool_value = 1 if gripper_open else 0
            self.tool_command[0] = tool_value
            
            # 更新机器人状态
            self.robot_state.update_state('tool_state', self.tool_command, sender=self)

    def on_uniform_gripper_change(self, value):
        """处理统一可移动执行器的滑块变化"""       
        if hasattr(self, 'gripper_value_label') and self.tool_group:
            # 获取单位符号
            unit = "°" if self.tool_group[0]["type"] == "revolute" else "m"
            float_value = float(f"{value:.3f}")
            self.gripper_value_label.configure(text=f"{float_value} {unit}")
            
            # 更新所有工具关节的命令值（统一控制）
            for i in range(len(self.tool_command)):
                self.tool_command[i] = float_value
            
            # 更新机器人状态
            self.robot_state.update_state('tool_state', self.tool_command, sender=self)

    def on_independent_gripper_change(self, joint_index):
        """处理独立可移动执行器的滑块变化"""
        if not hasattr(self, 'gripper_sliders') or not hasattr(self, 'gripper_labels'):
            return
            
        if joint_index >= len(self.gripper_sliders) or joint_index >= len(self.tool_group):
            return
            
        slider = self.gripper_sliders[joint_index]
        label = self.gripper_labels[joint_index]
        joint = self.tool_group[joint_index]
        
        # 获取单位符号和值
        unit = "°" if joint["type"] == "revolute" else "m"
        float_value = float(f"{slider.get():.3f}")
        label.configure(text=f"{float_value} {unit}")
        
        # 设置对应索引的工具命令值
        self.tool_command[joint_index] = float_value
        
        # 更新机器人状态
        self.robot_state.update_state('tool_state', self.tool_command, sender=self)

    def adjust_target_value(self, index, delta):
        """调整目标位置值"""
        try:
            current_value = float(self.target_entries[index].get())
            new_value = current_value + delta
            self.target_entries[index].delete(0, tk.END)
            self.target_entries[index].insert(0, f"{new_value:.6f}")
            self.on_target_change()
        except ValueError:
            self.target_entries[index].delete(0, tk.END)
            self.target_entries[index].insert(0, "0.000000")
            self.on_target_change()

    def adjust_orientation_value(self, index, delta):
        """调整姿态角度值"""
        try:
            current_value = float(self.orientation_entries[index].get())
            new_value = current_value + delta
            # 将角度限制在-180到180度之间
            new_value = ((new_value + 180) % 360) - 180
            self.orientation_entries[index].delete(0, tk.END)
            self.orientation_entries[index].insert(0, f"{new_value:.1f}")
            # 添加对姿态变化的响应
            self.on_orientation_change()
        except ValueError:
            self.orientation_entries[index].delete(0, tk.END)
            self.orientation_entries[index].insert(0, "0.0")
            self.on_orientation_change()

    def on_joint_change(self, joint_index):
        """当关节角度改变时自动更新"""
        # 更新关节值显示
        self.update_joint_value(joint_index)
        
        # 只更新改变的关节角度
        slider, _ = self.joint_entries[joint_index]
        self.joint_angles[joint_index] = float(slider.get())
        
        # 使用update_q更新笛卡尔空间位置和姿态
        self.update_q(self.joint_angles)

    def on_target_change(self):
        """当目标位置改变时自动更新"""
        try:
            # 获取目标位置
            target_position = []
            for entry in self.target_entries:
                value = entry.get().strip()
                if not value:
                    return
                target_position.append(float(value))
            
            self.target_position = np.array(target_position)
            
            # 获取目标姿态
            rpy_angles = []
            for entry in self.orientation_entries:
                value = entry.get().strip()
                if not value:
                    return
                rpy_angles.append(float(value))
            
            self.target_orientation = np.array(rpy_angles)
            
            # 根据约束状态构建目标姿态
            target_orientation = np.radians(self.target_orientation.copy())
            for i, constrained in enumerate(self.orientation_constraints):
                if not constrained:
                    target_orientation[i] = np.nan  # 未约束的轴设为nan
            
            self.update_p(self.target_position, target_orientation)
        
        except Exception as e:
            self.update_terminal(f"自动更新位置时出错: {str(e)}")

    def on_orientation_change(self):
        """当姿态改变时自动更新"""
        try: 
            # 获取目标位置
            target_position = []
            for entry in self.target_entries:
                value = entry.get().strip()
                if not value:
                    return
                target_position.append(float(value))
            
            self.target_position = np.array(target_position)
            
            # 获取RPY角度
            rpy_angles = []
            for entry in self.orientation_entries:
                value = entry.get().strip()
                if not value:
                    return
                rpy_angles.append(float(value))
            
            self.target_orientation = np.array(rpy_angles)
            
            # 根据约束状态构建目标姿态
            target_orientation = np.radians(self.target_orientation.copy())
            for i, constrained in enumerate(self.orientation_constraints):
                if not constrained:
                    target_orientation[i] = np.nan  # 未约束的轴设为nan
            
            self.update_p(self.target_position, target_orientation)
        
        except Exception as e:
            self.update_terminal(f"自动更新姿态时出错: {str(e)}")

    def on_orientation_constraint_change(self, index):
        """处理姿态约束复选框状态改变"""
        _, constraint_var = self.orientation_checkboxes[index]
        self.orientation_constraints[index] = constraint_var.get()
        
        # 根据约束状态构建目标姿态
        target_orientation = np.radians(self.target_orientation.copy())
        for i, constrained in enumerate(self.orientation_constraints):
            if not constrained:
                target_orientation[i] = np.nan  # 未约束的轴设为nan

    def on_coordinate_change(self, coordinate_system):
        """处理坐标系选择变化"""
        try:
            # 获取当前目标位置和姿态
            current_position = self.target_position.copy()
            current_orientation = np.radians(self.target_orientation.copy())
            
            # 确定源坐标系和目标坐标系
            from_frame = self.current_coordinate
            to_frame = coordinate_system
            
            # 执行坐标变换
            if from_frame != to_frame:
                transformed_position, transformed_orientation = self.coordinate_manager.transform(
                    target_position=current_position,
                    target_orientation=current_orientation,
                    from_frame=from_frame,
                    to_frame=to_frame
                )
                
                # 更新目标位置和姿态
                self.target_position = transformed_position
                if transformed_orientation is not None:
                    self.target_orientation = np.degrees(transformed_orientation)
                
                # 更新XYZ输入框
                for i, entry in enumerate(self.target_entries):
                    entry.delete(0, tk.END)
                    entry.insert(0, f"{self.target_position[i]:.6f}")
                
                # 更新RPY输入框
                for i, entry in enumerate(self.orientation_entries):
                    entry.delete(0, tk.END)
                    entry.insert(0, f"{self.target_orientation[i]:.1f}")
                
                self.update_terminal(f"坐标已从 {from_frame} 变换到 {to_frame}")
                self.update_terminal(f"新位置: [{self.target_position[0]:.6f}, {self.target_position[1]:.6f}, {self.target_position[2]:.6f}]")
                self.update_terminal(f"新姿态: [{self.target_orientation[0]:.1f}°, {self.target_orientation[1]:.1f}°, {self.target_orientation[2]:.1f}°]")
            
            # 更新当前坐标系
            self.current_coordinate = coordinate_system
            self.update_terminal(f"当前坐标系: {coordinate_system}")
            
        except Exception as e:
            self.update_terminal(f"坐标系变换出错: {str(e)}")
            # 如果变换失败，恢复原来的坐标系选择
            if hasattr(self, 'coordinate_var'):
                self.coordinate_var.set(self.current_coordinate)

    def load_robot_profile(self, init=False):
        """加载指定配置文件中的URDF"""
        try:
            self.protocol_class = SerialProtocol if ProfileManager.current_profile["robot_type"] == "PWM/I2C" else CanProtocol
                
            # 重置工作空间分析状态
            self.workspace_analyzed = False
            self.workspace_bounds = {
                'x': {'min': None, 'max': None},
                'y': {'min': None, 'max': None},
                'z': {'min': None, 'max': None}
            }

            # Init robot state params
            self.joint_limits = []
            self.home_values = []
            self.velocity_limits = []
            self.tool_command = []
            
            for group_name, group_data in ProfileManager.get_all_groups().items():
                if ProfileManager.is_end_effector_group(group_name):
                    self.actuation = ProfileManager.get_end_effector(group_name)["actuation"]
                    self.tool_group = ProfileManager.get_joints_by_group(group_name)
                    for joint in self.tool_group:
                        if joint["home"] is not None:
                            self.tool_command.append(joint["home"])
                        else:
                            self.tool_command.append(0)
                else:
                    self.main_group = ProfileManager.get_joints_by_group(group_name)

            for joint in self.main_group:
                # 检查关节是否有limit属性
                if "limit" in joint:
                    self.joint_limits.append((joint["limit"]["lower"], joint["limit"]["upper"]))
                    self.home_values.append(joint["home"])
                    self.velocity_limits.append(joint["limit"]["velocity"])
            self.home_values = np.array(self.home_values)
            
            self.joint_angles = np.array(self.home_values)
            self.num_joints = len(self.joint_limits)
            self.end_effector_link = self.num_joints-1
            
            # 提取关节下限和上限（转换为弧度）
            joint_lower_limits = [np.radians(limit[0]) for limit in self.joint_limits]
            joint_upper_limits = [np.radians(limit[1]) for limit in self.joint_limits]

            #print(self.velocity_limits*np.array(ProfileManager.current_profile["joint_speeds"]))
            # 创建轨迹约束
            self.traj_constraints = TrajConstraints(
                max_vel=self.velocity_limits, 
                max_acc=2, 
                max_jerk=2,
                joint_lower_limits=joint_lower_limits,
                joint_upper_limits=joint_upper_limits
            )
            self.traj_constraints.set_vel(np.array(ProfileManager.current_profile["joint_speeds"]))
            
            if init:
                self.planner = Planner(init_planner="Direct", init_solver="LevenbergMarquardt")
            else:
                self.planner.load_profile()

            self.init_robot_state()
            
            # 初始化坐标系（在robot state之后）
            self.init_coordinate_systems()
            self.clear_terminal()
            self.update_terminal("* Self-collision initalisation incomplete.\n* Workspace analysis incomplete.")
                
        except Exception as e:
            self.update_terminal(f"加载模型时出错: {str(e)}")

    def init_coordinate_systems(self):
        """初始化坐标系，包括默认工具坐标系"""
        # 重新初始化坐标管理器（清除之前的坐标系）
        self.coordinate_manager = CoordinateManager()
        
        # 添加默认工具坐标系，使用当前TCP位置和姿态
        tool_position = self.target_position
        tool_orientation = np.radians(self.target_orientation)
        
        self.coordinate_manager.add_tool_frame("Tool0", tool_position, tool_orientation)

    def on_self_collision_check(self):
        """自碰撞检测按钮回调"""
        try:
            result = self.planner.generate_collision_matrix()
            always = result.get('always', [])
            never = result.get('never', [])
            sometimes = result.get('sometimes', [])
            if always:
                self.update_terminal(f"[always]: {len(always)}")
                for item in always:
                    i1, i2, n1, n2 = item
                    self.update_terminal(f"{n1} <-> {n2}")
            if never:
                self.update_terminal(f"\n[never]: {len(never)}")
                for item in never:
                    i1, i2, n1, n2 = item
                    self.update_terminal(f"{n1} <-> {n2}")
            if sometimes:
                self.update_terminal(f"\n[sometimes]: {len(sometimes)}")
                for item in sometimes:
                    i1, i2, n1, n2, freq = item
                    self.update_terminal(f"{n1} <-> {n2} likelihood: {freq:.2%}")
        except Exception as e:
            self.update_terminal(f"自碰撞检测出错: {str(e)}")

    def apply_hyperparams(self):
        """应用超参数设置"""
        solver_params = {}
        if self.current_solver == "LevenbergMarquardt":
            solver_params["lm_lambda"] = float(self.lm_lambda_entry.get())
            solver_params["lm_epsilon"] = float(self.lm_epsilon_entry.get())
            solver_params["lm_max_iterations"] = int(self.lm_max_iterations_entry.get())
            
        elif self.current_solver == "DampedLeastSquares":
            solver_params["dls_damping"] = float(self.dls_damping_entry.get())
            solver_params["dls_epsilon"] = float(self.dls_epsilon_entry.get())
            solver_params["dls_max_iterations"] = int(self.dls_max_iterations_entry.get())
            
        elif self.current_solver == "TRAC-IK":
            solver_params["trac_ik_epsilon"] = float(self.trac_ik_epsilon_entry.get())
            solver_params["trac_ik_max_iterations"] = int(self.trac_ik_max_iterations_entry.get())

        self.planner_method = self.planner_var.get()
        self.num_pathpoints = int(self.num_pathpoints_entry.get())
                
        self.planner.set_solver(self.current_solver, solver_params)
        self.planner.set_planner(self.planner_method)

        self.planner.setNumPathpoints(self.num_pathpoints)

    def init_robot_state(self):
        """初始化机器人状态，计算正向运动学并更新UI"""

        current_angles = np.radians(self.joint_angles)
        current_position, current_orientation, _ = self.planner.getPoseGlobal(current_angles, self.end_effector_link)
        
        if current_position is not None and current_orientation is not None:
            self.target_position = current_position
            self.target_orientation = np.degrees(current_orientation)
            self.set_end_effector_home(self.target_position)

        # 从tool_group中提取home值
        tool_home_values = []
        if self.tool_group is not None:
            for joint in self.tool_group:
                tool_home_values.append(joint.get("home", 0.0))
        
        self.robot_state.update_state('joint_angles', self.joint_angles, sender=self)
        self.robot_state.update_state('home_values', self.home_values, sender=self)
        self.robot_state.update_state('tool_state', tool_home_values, sender=self)
        self.robot_state.update_state('end_effector_link', self.end_effector_link, sender=self)
        self.robot_state.update_state('target_position', self.target_position, sender=self)
        self.robot_state.update_state('target_orientation', np.array(p.getQuaternionFromEuler(current_orientation)), sender=self)
        self.robot_state.update_state('tcp_offset', self.planner.ee_offset, sender=self)
                
        self.update_terminal("robot state initialisation successful.")

    def update_ui(self, update_joint_control=True, update_entries=True):
        """更新关节滑块控制器和位置输入框
        
        Args:
            update_joint_control: 是否更新关节控制器，默认为True
            update_entries: 是否更新位置和姿态输入框，默认为True
        """
        try:
            # 重新设置关节控制器
            if update_joint_control:
                self.setup_joint_control(self.fk_top_frame, self.num_joints, self.joint_limits)
                # 设置工具控制
                self.setup_tools(self.fk_top_frame)
            
            # 更新位置和姿态输入框
            if update_entries:
                for i, entry in enumerate(self.target_entries):
                    entry.delete(0, tk.END)
                    entry.insert(0, f"{self.target_position[i]:.6f}")

                for i, entry in enumerate(self.orientation_entries):
                    entry.delete(0, tk.END)
                    entry.insert(0, f"{self.target_orientation[i]:.1f}")
                
                # 更新姿态约束复选框状态
                if hasattr(self, 'orientation_checkboxes'):
                    for i, (checkbox, var) in enumerate(self.orientation_checkboxes):
                        if i < len(self.orientation_constraints):
                            var.set(self.orientation_constraints[i])
        
        except Exception as e:
            self.update_terminal(f"更新UI时出错: {str(e)}")

    def send_to_robot(self, use_traj=False):
        """发送关节角度到机器人"""

        tool_values = self.tool_command

        if use_traj and self.last_planner_result is not None:
            # Execute trajectory from saved planner result
            trajectory = self.last_planner_result.trajectory
            
            if not self.protocol_class.is_connected():
                self.update_terminal(f"No protocol connection. fake executing trajectory with {len(trajectory)} waypoints and tool: {tool_values}")
                return
            else:
                self.update_terminal(f"Executing trajectory with {len(trajectory)} waypoints...")
                
                for i, waypoint in enumerate(trajectory):
                    # Convert from radians to degrees
                    joint_angles_deg = np.degrees(waypoint)
                    
                    # Joint motion execution
                    self.protocol_class.send("EXEC\n")
                    joint_command = ",".join(f"{angle:.2f}" for angle in joint_angles_deg) + "\n"
                    self.protocol_class.send(joint_command)

                    # wait for joint execution completion
                    _, isReplied = self.protocol_class.receive(timeout=5, expected_signal="CP0")
                    if not isReplied:
                        self.update_terminal(f"joint execution timeout at waypoint {i+1}")
                        return
                    
                    self.update_terminal(f"Waypoint {i+1}/{len(trajectory)}: {[f'{angle:.2f}°' for angle in joint_angles_deg]}")
                
                # Tool motion execution after trajectory completion
                tool_command = f"M280,{','.join(str(v) for v in tool_values)}\n"
                self.protocol_class.send(tool_command)

                _, isReplied = self.protocol_class.receive(timeout=5, expected_signal="TP0")
                if not isReplied:
                    self.update_terminal("M280 timeout")
                else:
                    self.update_terminal(f"command M280,{','.join(str(v) for v in tool_values)}")
        else:
            # Execute single motion
            joint_angles = [angle for angle in self.joint_angles]

            if not self.protocol_class.is_connected():
                self.update_terminal(f"No protocol connection. fake executing single motion: {[f'{angle:.2f}°' for angle in joint_angles]} and tool: {tool_values}")
                return
            else:
                self.update_terminal(f"Executing single motion...")

                # Joint motion execution
                self.protocol_class.send("EXEC\n")
                joint_command = ",".join(f"{angle:.2f}" for angle in joint_angles) + "\n"
                self.protocol_class.send(joint_command)

                # wait for joint execution completion
                _, isReplied = self.protocol_class.receive(timeout=5, expected_signal="CP0")
                if not isReplied:
                    self.update_terminal("joint execution timeout")
                else:
                    self.update_terminal(f"joint angles: {[f'{angle:.2f}°' for angle in joint_angles]}\n")
                
                # Tool motion execution
                tool_command = f"M280,{','.join(str(v) for v in tool_values)}\n"
                self.protocol_class.send(tool_command)

                _, isReplied = self.protocol_class.receive(timeout=5, expected_signal="TP0")
                if not isReplied:
                    self.update_terminal("M280 timeout")
                else:  
                    self.update_terminal(f"tool command: M280,{','.join(str(v) for v in tool_values)}")

    def open_camera_controller(self):
        """打开相机控制器"""
        try:
            self.vision_ui = VisionFrame(self)
            self.vision_ui.create_window()
        except Exception as e:
            messagebox.showerror("错误", f"打开相机控制器失败: {str(e)}")

    def open_gcode_ui(self):
        """打开G代码控制器"""
        try:
            self.gcode_ui = GCodeUI(self)
            self.gcode_ui.create_window()
        except Exception as e:
            messagebox.showerror("错误", f"打开G代码控制器失败: {str(e)}")

    def open_workspace_analyzer(self):
        """打开工作空间分析器"""
        try:
            self.workspace_analyzer_ui = WorkspaceFrame(self)
            self.workspace_analyzer_ui.create_window()
        except Exception as e:
            messagebox.showerror("错误", f"打开工作空间分析器失败: {str(e)}")

    def clear_terminal(self):
        """清空终端"""
        if hasattr(self, 'log_text') and self.log_text.winfo_exists():
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.delete(1.0, tk.END)
            self.log_text.configure(state=tk.DISABLED)

    def update_terminal(self, message):
        """更新终端显示"""
        if hasattr(self, 'log_text') and self.log_text.winfo_exists():
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.insert(tk.END, f"{message}\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)

    def set_end_effector_home(self, position):
        """设置末端执行器的home位置"""
        self.end_effector_home = position
        self.update_terminal(f"Tool position set to: {[f'{x:.6f}' for x in self.end_effector_home]}")

    def home(self):
        """将机器人移动到home位置"""
        # 将关节角度设置为home值
        self.joint_angles = self.home_values.copy()
        
        # 更新所有关节滑块和值
        for i, (slider, value_label) in enumerate(self.joint_entries):
            if i < len(self.home_values):
                slider.set(self.home_values[i])
                value_label.configure(text=f"{int(self.home_values[i])}°")
        
        # 调用update_q更新笛卡尔空间位置和姿态
        self.update_q(self.joint_angles)
        
        # 更新终端显示
        self.update_terminal(f"机器人已移动到home位置: {[f'{angle:.1f}°' for angle in self.home_values]}")

    def get_available_solvers(self):
        """获取所有可用的求解器列表"""
        # 内置求解器
        built_in_solvers = [
            "LevenbergMarquardt",
            "DampedLeastSquares", 
            "TRAC-IK"
        ]
        
        # 获取自定义求解器
        custom_solvers = []
        
        base_dir = Config.get_path()
        custom_solvers_dir = os.path.join(base_dir, 'custom_solvers')
        
        if os.path.exists(custom_solvers_dir):
            for file in os.listdir(custom_solvers_dir):
                if file.endswith('.py'):
                    custom_solvers.append(file[:-3])
        
        # 合并所有求解器
        return built_in_solvers + custom_solvers

    def show_solver_manager(self):
        """显示求解器管理器窗口"""
        if not hasattr(self, 'solver_manager') or not self.solver_manager.winfo_exists():
            self.solver_manager = SolverManager(self)
            self.solver_manager.grab_set()  # 模态窗口

    def update_p(self, target_position, target_orientation):
        """更新关节角度（从笛卡尔空间到关节空间）
        
        Args:
            target_position: 目标位置 [x, y, z]
            target_orientation: 目标姿态(RPY弧度)，未约束的轴为nan
        """
        try:  
            # 如果当前坐标系不是base，需要先将目标位置和姿态变换到基坐标系
            if self.current_coordinate != "Base":
                # 将当前坐标系的位置和姿态变换到基坐标系
                base_position, base_orientation = self.coordinate_manager.transform(
                    target_position=target_position,
                    target_orientation=target_orientation if not np.isnan(target_orientation).all() else None,
                    from_frame=self.current_coordinate,
                    to_frame="Base"
                )
                solver_position = base_position
                solver_orientation = base_orientation
            else:
                solver_position = target_position
                solver_orientation = target_orientation if not np.isnan(target_orientation).all() else None
            
            # 计算IK解（使用基坐标系的位置和姿态）
            result = self.planner.plan(np.radians(self.joint_angles), 
                                                 solver_position, 
                                                 solver_orientation,
                                                 interpolation_method=Config.interpolation_method)
            
            # Save the result for potential trajectory execution
            self.last_planner_result = result
            
            j = 0
            self_collision = result.collision_stats["self_collide"]
            self_collision_info = result.collision_stats["self_collision_info"]
            collision = result.collision_stats["collision"]
            collision_info = result.collision_stats["collision_info"]

            self.update_terminal(f">> final error: {result.error:.4f}, planning time: {result.planning_time:.4f}秒")

            for i, solution in enumerate(result.trajectory):
                if self_collision[i]:
                    for j, collision_point in enumerate(self_collision_info[i]):
                        self.update_terminal(f"self collide: {collision_point['link_names'][0]} <-> {collision_point['link_names'][1]} {collision_point['distance']:.4f}m")
                if collision[i]:
                    for j, collision_point in enumerate(collision_info[i]):
                        self.update_terminal(f"collide: {collision_point['robot_link_name']} <-> {collision_point['object_name']} {collision_point['distance']:.4f}m")

                time.sleep(0.002)
                
                self.robot_state.update_state('joint_angles', np.degrees(solution), sender=self)
                j += 1
            
            self.joint_angles = np.degrees(result.trajectory[-1])

            # 更新关节滑块
            for i, (slider, value_label) in enumerate(self.joint_entries):
                if i < len(self.joint_angles):
                    slider.set(self.joint_angles[i])
                    value_label.configure(text=f"{self.joint_angles[i]:.1f}°")
            
            # update non-constrained orientation values
            if result.final_orientation is not None:
                # 如果当前坐标系不是base，需要将结果变换回当前坐标系显示
                if self.current_coordinate != "Base":
                    # 将基坐标系的最终姿态变换到当前坐标系
                    _, display_final_orientation = self.coordinate_manager.transform(
                        target_position=np.zeros(3),  # 只需要变换姿态
                        target_orientation=result.final_orientation,
                        from_frame="Base",
                        to_frame=self.current_coordinate
                    )
                    actual_orientation = np.degrees(display_final_orientation)
                else:
                    actual_orientation = np.degrees(result.final_orientation)

                # update non-constrained orientation values
                for i in range(len(self.target_orientation)):
                    if i < len(self.orientation_constraints):
                        if not self.orientation_constraints[i]:
                            self.target_orientation[i] = actual_orientation[i]
                
                # 更新姿态输入框显示
                for i, entry in enumerate(self.orientation_entries):
                    if i < len(self.target_orientation):
                        entry.delete(0, tk.END)
                        entry.insert(0, f"{self.target_orientation[i]:.1f}")
            
            # robot_state始终使用基坐标系的值
            if self.current_coordinate != "Base":
                self.robot_state.update_state('target_position', solver_position, sender=self)
            else:
                self.robot_state.update_state('target_position', self.target_position, sender=self)
            if result.final_orientation is not None:
                self.robot_state.update_state('target_orientation', np.array(p.getQuaternionFromEuler(result.final_orientation)), sender=self)
        
        except Exception as e:
            self.update_terminal(f"更新关节角度时出错: {str(e)}")

    def update_q(self, joint_angles, no_state_update=False):
        """更新笛卡尔空间位置和姿态（从关节空间到笛卡尔空间）
        
        Args:
            joint_angles: 关节角度列表
        """
        try:
            # 将角度转换为弧度并计算正向运动学
            current_joints = np.radians(joint_angles)
            current_position, current_orientation, collision_stats = self.planner.getPoseGlobal(current_joints)
            
            if current_position is not None and current_orientation is not None:
                # 如果当前坐标系不是base，需要进行坐标变换
                if self.current_coordinate != "Base":
                    # 将基坐标系的位置和姿态变换到当前坐标系
                    transformed_position, transformed_orientation = self.coordinate_manager.transform(
                        target_position=current_position,
                        target_orientation=current_orientation,
                        from_frame="Base",
                        to_frame=self.current_coordinate
                    )
                    display_position = transformed_position
                    display_orientation = np.degrees(transformed_orientation)
                else:
                    display_position = current_position
                    display_orientation = np.degrees(current_orientation)
                
                # 更新目标位置和姿态
                self.target_position = display_position
                for i, entry in enumerate(self.target_entries):
                    entry.delete(0, tk.END)
                    entry.insert(0, f"{display_position[i]:.6f}")

                self.target_orientation = display_orientation
                for i, entry in enumerate(self.orientation_entries):
                    entry.delete(0, tk.END)
                    entry.insert(0, f"{display_orientation[i]:.1f}")

                # 处理自碰撞信息（现在是列表字典格式）
                if collision_stats["self_collide"] and collision_stats["self_collision_info"]:
                    for collision_point in collision_stats["self_collision_info"]:
                        link_names = collision_point["link_names"]
                        distance = collision_point["distance"]
                        # 格式化输出碰撞信息
                        self.update_terminal(
                            f"self collide: {link_names[0]} <-> {link_names[1]} {distance:.4f}m"
                        )
                
                # 处理环境碰撞信息（现在是列表字典格式）
                if collision_stats["collision"] and collision_stats["collision_info"]:
                    for collision_point in collision_stats["collision_info"]:
                        robot_link = collision_point["robot_link_name"]
                        object_name = collision_point["object_name"]
                        distance = collision_point["distance"]
                        # 格式化输出碰撞信息
                        self.update_terminal(
                            f"collide: {robot_link} <-> {object_name} {distance:.4f}m"
                        )
                
                if not no_state_update:
                    self.robot_state.update_state('joint_angles', joint_angles, sender=self)
                    # 注意：robot_state始终使用基坐标系的值
                    self.robot_state.update_state('target_position', current_position, sender=self)
                    self.robot_state.update_state('target_orientation', np.array(p.getQuaternionFromEuler(current_orientation)), sender=self)
                
        except Exception as e:
            self.update_terminal(f"更新笛卡尔空间位置时出错: {str(e)}")

    def update(self, state):
        joint_angles = state['joint_angles']
        tcp_offset = state['tcp_offset']
        base_position = state.get('base_position')
        base_orientation = state.get('base_orientation')
        
        self.joint_angles = joint_angles.copy()
        
        # 更新滑块位置和标签
        for i, angle in enumerate(joint_angles):
            if i < len(self.joint_entries):
                slider, _ = self.joint_entries[i]
                slider.set(angle)
                self.update_joint_value(i)
        
        # 使用新的关节角度更新笛卡尔空间位置和姿态
        self.update_q(self.joint_angles, no_state_update=True)

        self.planner.set_ee_offset(tcp_offset)
        
        # 如果基座位置或姿态有更新，设置基座偏移
        if base_position is not None and base_orientation is not None:
            self.planner.set_base_offset(base_position, base_orientation)
        
        # 更新Tool0坐标系以反映新的TCP位置和姿态
        # 获取当前关节角度下的实际TCP位置和姿态
        current_joints = np.radians(self.joint_angles)
        tcp_position, tcp_orientation, _ = self.planner.getPoseGlobal(current_joints, self.end_effector_link)
        
        if tcp_position is not None and tcp_orientation is not None:
            tcp_pose = np.concatenate([tcp_position, tcp_orientation])
            self.coordinate_manager.update_tool_frame(tcp_pose, tool_name='Tool0')
            
            # 更新目标位置和姿态
            self.target_position = tcp_position
            self.target_orientation = np.degrees(tcp_orientation)
            
            # 使用update_p来更新UI显示和处理坐标变换
            self.update_p(tcp_position, tcp_orientation)

    def update_texts(self):
        """更新所有文本内容"""
        # Update language of existing labels
        self.frame_label.configure(text=Config.current_lang["kinematics"])
        self.hyperparams_label.configure(text=Config.current_lang["solver_init"])     
        self.solver_label.configure(text=Config.current_lang["solver"])  
        self.planner_label.configure(text=Config.current_lang["planner"])
        self.self_collision_button.configure(text=Config.current_lang["self_collision_check"])
        self.apply_hyperparams_button.configure(text=Config.current_lang["apply"])  
        self.fk_label.configure(text=Config.current_lang["forward_kinematics"])
        self.set_home_button.configure(text=Config.current_lang["home"])  
        self.ik_label.configure(text=Config.current_lang["inverse_kinematics"]) 
        self.num_pathpoints_label.configure(text=Config.current_lang["pathpoints"])   
        self.send_button.configure(text=Config.current_lang["send_to_robot"])

        self.camera_controller_button.configure(text=Config.current_lang["control_with_vision"])
        self.robot_language_button.configure(text=Config.current_lang["robot_control_language"])
        self.workspace_button.configure(text=Config.current_lang["workspace_analyzer"])
        self.coordinate_label.configure(text=Config.current_lang["coordinate_system"])

        # Update other widgets
        if hasattr(self, 'lm_lambda_label') and self.lm_lambda_label.winfo_exists():
            self.lm_lambda_label.configure(text=Config.current_lang["lm_lambda"])
            
        if hasattr(self, 'lm_epsilon_label') and self.lm_epsilon_label.winfo_exists():
            self.lm_epsilon_label.configure(text=Config.current_lang["lm_epsilon"])
            
        if hasattr(self, 'lm_max_iterations_label') and self.lm_max_iterations_label.winfo_exists():
            self.lm_max_iterations_label.configure(text=Config.current_lang["max_iterations"])
            
        if hasattr(self, 'dls_damping_label') and self.dls_damping_label.winfo_exists():
            self.dls_damping_label.configure(text=Config.current_lang["dls_damping"])
            
        if hasattr(self, 'dls_epsilon_label') and self.dls_epsilon_label.winfo_exists():
            self.dls_epsilon_label.configure(text=Config.current_lang["dls_epsilon"])
            
        if hasattr(self, 'dls_max_iterations_label') and self.dls_max_iterations_label.winfo_exists():
            self.dls_max_iterations_label.configure(text=Config.current_lang["max_iterations"])
            
        if hasattr(self, 'trac_ik_epsilon_label') and self.trac_ik_epsilon_label.winfo_exists():
            self.trac_ik_epsilon_label.configure(text=Config.current_lang["trac_ik_epsilon"])
            
        if hasattr(self, 'trac_ik_max_iterations_label') and self.trac_ik_max_iterations_label.winfo_exists():
            self.trac_ik_max_iterations_label.configure(text=Config.current_lang["max_iterations"])

        if hasattr(self, 'tool_label') and self.tool_label.winfo_exists():
            self.tool_label.configure(text=Config.current_lang["tool"])

        # update language for children ui.
        if hasattr(self, 'vision_ui') and self.vision_ui.dialog.winfo_exists():
            self.vision_ui.update_texts()

        if hasattr(self, 'workspace_analyzer_ui') and self.workspace_analyzer_ui.workspace_dialog.winfo_exists():
            self.workspace_analyzer_ui.update_texts()

        if hasattr(self, 'gcode_ui') and self.gcode_ui.dialog.winfo_exists():
            self.gcode_ui.update_texts()
    
    def on_trajectory_params_changed(self, param_name):
        """callback when trajOptimiser param changed
        
        Args:
            param_name: specific parameter name to update ('dt', 'speed', 'acceleration', 'jerk')
        """
        if param_name == 'dt':
            self.update_terminal(f"Trajectory optimizer dt updated to: {Config.dt}")
            self.traj_optimiser.set_dt(Config.dt)
            
        elif param_name == 'speed':
            if Config.joint_speeds:
                self.traj_constraints.set_vel(Config.joint_speeds)
                self.update_terminal(f"Joint speeds updated: {Config.joint_speeds}")
                
        elif param_name == 'acceleration':
            if Config.joint_accelerations:
                self.traj_constraints.set_acc(Config.joint_accelerations)
                self.update_terminal(f"Joint accelerations updated: {Config.joint_accelerations}")
                
        elif param_name == 'jerk':
            if Config.joint_jerks:
                self.traj_constraints.set_jerk(Config.joint_jerks)
                self.update_terminal(f"Joint jerks updated: {Config.joint_jerks}")
    
    def on_trajectory_method_changed(self):
        """callback when trajectory method change"""
        self.update_terminal(f"Trajectory method updated to: {Config.trajectory_method}")
        self.traj_optimiser.set_method(Config.trajectory_method)
    
    def on_interpolation_method_changed(self):
        """callback when interpolation method change"""
        self.update_terminal(f"Interpolation method updated to: {Config.interpolation_method}")
        self.planner.set_interpolation_method(Config.interpolation_method)
