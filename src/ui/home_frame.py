import os
import tkinter as tk
from PIL import Image
import customtkinter as ctk

from utils.config import Config
from utils.robot_state import RobotState
from utils.resource_loader import ResourceLoader
from utils.custom_optionmenu import CustomOptionMenu
from ui.profileUI.robot_profile_frame import RobotProfileFrame
from ui.controllerUI.controller_frame import ControllerFrame
from ui.controllerUI.anytroller_frame import AnytrollerFrame
from ui.rosUI.ros_frame import ROSFrame
from ui.kinematicsUI.kinematics_frame import KinematicsFrame
from ui.simulatorUI.simulator_frame import SimulatorFrame
from ui.firmwareUI.firmware_frame import FirmwareFrame
from ui.helperUI.help_frame import HelpFrame
from ui.majordomoUI.majordomo_dialog import MajordomoDialog
from ui.settingUI.settings_frame import SettingsFrame
from noman.profile_manager import ProfileManager
from noman.physics.bullet.physics_engine import PhysicsEngine

# Main App
class RobotArmApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("")
        self.resizable(False, False)
        self.operating_system = Config.operating_system
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        # set ui geometry and icon as per operating system
        if self.operating_system == "Windows":
            icon_path = ResourceLoader.get_asset_path(os.path.join("icons", "noman_logo.ico"))
            self.iconbitmap(icon_path)
        elif self.operating_system == "Darwin":  # macOS
            icon_path = ResourceLoader.get_asset_path(os.path.join("icons", "noman_logo.png"))
            icon = tk.Image("photo", file=icon_path)
            self.tk.call('wm', 'iconphoto', self._w, icon)
        elif self.operating_system == "Linux":
            icon_path = ResourceLoader.get_asset_path(os.path.join("icons", "noman_logo.png"))
            icon = tk.PhotoImage(file=icon_path)
            self.tk.call('wm', 'iconphoto', self._w, icon)
        
        self.geometry(Config.geometry)
        
        self.current_frame = None
        self.current_tool = "gripper"
        self.show_home()

    def show_home(self):
        if self.current_frame:
            self.current_frame.pack_forget()
        self.current_frame = HomeFrame(self, app=self)
        self.current_frame.pack(fill=tk.BOTH, expand=True)
        self.current_frame.update_texts()

# Home Frame
class HomeFrame(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master)
        self.master = master
        self.app = app

        ProfileManager.initialize()
        
        self.robot_state = RobotState()

        # initialize physics engine
        self.physics_engine = PhysicsEngine.get_instance()
        self.physics_engine.load_urdf(ProfileManager.current_profile["urdf_path"], 'default')

        # Load all icons
        self.load_icons()

        # Set grid layout
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)

        # Create navigation frame
        self.navigation_frame = ctk.CTkFrame(self, corner_radius=0, width=190)
        self.navigation_frame.grid(row=0, column=0, sticky="nsew")
        self.navigation_frame.grid_rowconfigure(10, weight=1)
        self.navigation_frame.grid_propagate(False)

        # Create content frame
        self.content_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.content_frame.grid(row=0, column=1, sticky="nsew")
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)

        self.profile_container = ctk.CTkFrame(self.navigation_frame, fg_color="transparent")
        self.profile_container.grid(row=0, column=0, sticky='ew', padx=(15,25), pady=(21,30))
        self.profile_container.grid_columnconfigure(0, weight=1)
        self.profile_container.grid_columnconfigure(1, weight=0)

        self.profile_var = ctk.StringVar(value=ProfileManager.current_profile["name"])
        self.profile_dropdown = CustomOptionMenu(
            self.profile_container,
            variable=self.profile_var,
            values=ProfileManager.get_all_profile_names(),
            command=self.change_robot_profile,
            fg_color="#cfcfcf",
            button_color="#cfcfcf",
            button_hover_color=("gray75", "gray35"),
            width=115,
            corner_radius=0,
            text_color="black",
            dropdown_text_color="black",
            dropdown_fg_color="#cfcfcf",
            border_width=1,
            border_color="black",
            border_hover_color="green"
        )
        self.profile_dropdown.grid(row=0, column=0, sticky='ew')

        self.plus_button = ctk.CTkButton(
            self.profile_container,
            text="",
            image=self.plus_icon,
            width=30,
            height=30,
            command=self.add_new_profile,
            fg_color="#cfcfcf",
            hover_color=("gray75", "gray35")
        )
        self.plus_button.grid(row=0, column=1)

        # Profile button
        self.robot_profile_button = ctk.CTkButton(self.navigation_frame, corner_radius=0, height=40, border_spacing=10,
                                               text="Robot Profile", image=self.robot_profile_icon, fg_color="transparent", text_color=("gray10", "gray90"),
                                               hover_color=("gray70", "gray30"), anchor="w", command=self.show_robot_profile)
        self.robot_profile_button.grid(row=1, column=0, sticky="ew")

        # Navigation button
        self.controller_button = ctk.CTkButton(self.navigation_frame, corner_radius=0, height=40, border_spacing=10,
                                               text="Controller", image=self.controller_icon, fg_color="transparent", text_color=("gray10", "gray90"),
                                               hover_color=("gray70", "gray30"), anchor="w", command=self.show_controller)
        self.controller_button.grid(row=2, column=0, sticky="ew")

        # ROS button
        self.ros_button = ctk.CTkButton(self.navigation_frame, corner_radius=0, height=40, border_spacing=10,
                                        text="ROS", image=self.ros_icon, fg_color="transparent", text_color=("gray10", "gray90"),
                                        hover_color=("gray70", "gray30"), anchor="w", command=self.show_ros)
        self.ros_button.grid(row=3, column=0, sticky="ew")

        # Kinematics button
        self.kinematics_button = ctk.CTkButton(self.navigation_frame, corner_radius=0, height=40, border_spacing=10,
                                               text="Kinematics", image=self.kinematics_icon, fg_color="transparent", text_color=("gray10", "gray90"),
                                               hover_color=("gray70", "gray30"), anchor="w", command=self.show_kinematics)
        self.kinematics_button.grid(row=4, column=0, sticky="ew")

        # Simulator button
        self.simulator_button = ctk.CTkButton(self.navigation_frame, corner_radius=0, height=40, border_spacing=10,
                                              text="Simulator", image=self.simulator_icon, fg_color="transparent", 
                                              text_color=("gray10", "gray90"),
                                              hover_color=("gray70", "gray30"), anchor="w", command=self.show_simulator)
        self.simulator_button.grid(row=5, column=0, sticky="ew")

        # Add separator
        self.separator = ctk.CTkFrame(self.navigation_frame, height=2, fg_color="gray30")
        self.separator.grid(row=6, column=0, sticky="ew", padx=0, pady=(410,5))

        self.config_button = ctk.CTkButton(self.navigation_frame, corner_radius=0, height=40, border_spacing=10,
                                             text="Firmware", image=self.firmware_icon, fg_color="transparent", text_color=("gray10", "gray90"),
                                             hover_color=("gray70", "gray30"), anchor="w", command=self.show_firmware)
        self.config_button.grid(row=7, column=0, sticky="ew")

        self.help_button = ctk.CTkButton(self.navigation_frame, corner_radius=0, height=40, border_spacing=10,
                                         text="Help", image=self.help_icon, fg_color="transparent", text_color=("gray10", "gray90"),
                                         hover_color=("gray70", "gray30"), anchor="w", command=self.show_help)
        self.help_button.grid(row=8, column=0, sticky="ew")

        self.majordomo_button = ctk.CTkButton(self.navigation_frame, corner_radius=0, height=40, border_spacing=10,
                                         text="Majordomo", image=self.majordomo_icon, fg_color="transparent", 
                                         text_color=("gray10", "gray90"),
                                         hover_color=("gray70", "gray30"), anchor="w", 
                                         command=self.show_majordomo)
        self.majordomo_button.grid(row=9, column=0, sticky="ew")

        # Settings button
        self.settings_button = ctk.CTkButton(self.navigation_frame, corner_radius=0, height=40, border_spacing=10,
                                         text="Setting", image=self.settings_icon, fg_color="transparent", text_color=("gray10", "gray90"),
                                         hover_color=("gray70", "gray30"), anchor="w", 
                                         command=self.show_settings)
        self.settings_button.grid(row=10, column=0, sticky="new")

        # Initialize sub-frames
        self.robot_profile_frame = RobotProfileFrame(self.content_frame, app=self, robot_state=self.robot_state)

        if ProfileManager.is_profile_official():
            self.controller_frame = ControllerFrame(self.content_frame, self.robot_state)
        else:
            self.controller_frame = AnytrollerFrame(self.content_frame, self.robot_state)

        self.ros_frame = ROSFrame(self.content_frame)
        self.simulator_frame = SimulatorFrame(self.content_frame, self.robot_state, app=self.app)
        self.kinematics_frame = KinematicsFrame(self.content_frame, self.robot_state)
        self.firmware_frame = FirmwareFrame(self.content_frame, app=self.app)
        self.help_frame = None
        self.majordomo_dialog = None
        self.settings_frame = SettingsFrame(self.content_frame, app=self)

        self.show_robot_profile()

    def load_icons(self):
        """Load all icon images used in the interface"""
        self.robot_profile_icon = self.load_icon("robot.png", (20, 20))
        self.plus_icon = self.load_icon("plus.png", (20, 20))
        self.controller_icon = self.load_icon("options.png", (20, 20))
        self.ros_icon = self.load_icon("ros.png", (20, 20))
        self.kinematics_icon = self.load_icon("kinematics.png", (20, 20))
        self.firmware_icon = self.load_icon("download.png", (20, 20))
        self.help_icon = self.load_icon("help.png", (20, 20))
        self.majordomo_icon = self.load_icon("majordomo.png", (20, 20))
        self.simulator_icon = self.load_icon("simulator.png", (20, 20))
        self.settings_icon = self.load_icon("setting.png", (20, 20))

    def load_icon(self, filename, size):
        """Helper method to load an icon with the given filename and size"""
        path = ResourceLoader.get_asset_path(os.path.join("icons", filename))
        return ctk.CTkImage(Image.open(path).convert("RGBA"), size=size)

    def show_robot_profile(self):
        self.hide_all_frames()
        self.robot_profile_frame.grid(row=0, column=0, sticky="nsew")
        self.select_button(self.robot_profile_button)

    def show_controller(self):
        self.hide_all_frames()
        self.controller_frame.grid(row=0, column=0, sticky="nsew")
        self.select_button(self.controller_button)

    def show_ros(self):
        self.hide_all_frames()
        self.ros_frame.grid(row=0, column=0, sticky="nsew")
        self.select_button(self.ros_button)

    def show_kinematics(self):
        self.hide_all_frames()
        self.kinematics_frame.grid(row=0, column=0, sticky="nsew")
        self.select_button(self.kinematics_button)

    def show_simulator(self):
        """显示模拟器界面"""
        self.hide_all_frames()
        self.simulator_frame.grid(row=0, column=0, sticky="nsew")
        self.select_button(self.simulator_button)

    def show_firmware(self):
        self.hide_all_frames()
        self.firmware_frame.grid(row=0, column=0, sticky="nsew")
        self.select_button(self.config_button)

    def show_help(self):
        self.hide_all_frames()
        if not self.help_frame:
            self.help_frame = HelpFrame(self.content_frame)
        self.help_frame.grid(row=0, column=0, sticky="nsew")
        self.select_button(self.help_button)

    def show_majordomo(self):
        """show majordomo dialog"""
        if not self.majordomo_dialog:
            self.majordomo_dialog = MajordomoDialog(self)
        self.majordomo_dialog.show()

    def show_settings(self):
        """显示设置界面"""
        self.hide_all_frames()
        self.settings_frame.grid(row=0, column=0, sticky="nsew")
        self.select_button(self.settings_button)

    def add_new_profile(self):
        """add new robot profile"""
        # switch to robot profile page and load new profile
        self.show_robot_profile()
        self.robot_profile_frame.load_new_profile()

    def change_robot_profile(self, profile_name):
        """switch robot profile"""  
        success = ProfileManager.set_current_profile(profile_name)
        if success:
            self.physics_engine.load_urdf(ProfileManager.current_profile["urdf_path"], 'default')

            self.hide_all_frames()
            self.robot_profile_frame.load_profile()
            
            # destroy old ui
            if hasattr(self, 'controller_frame') and self.controller_frame:
                self.controller_frame.destroy()
            if hasattr(self, 'settings_frame') and self.settings_frame:
                self.settings_frame.destroy()
            
            if ProfileManager.is_profile_official(profile_name):
                self.controller_frame = ControllerFrame(self.content_frame, self.robot_state)
            else:
                self.controller_frame = AnytrollerFrame(self.content_frame, self.robot_state)
            
            self.kinematics_frame.load_robot_profile()
            self.kinematics_frame.update_ui()
            self.simulator_frame.load_robot_profile()
            self.simulator_frame.update_ui()
            self.firmware_frame.load_current_profile()
            self.settings_frame = SettingsFrame(self.content_frame, app=self)
            self.show_robot_profile()

    def hide_all_frames(self):
        for frame in [self.robot_profile_frame, self.controller_frame, self.kinematics_frame, self.simulator_frame, self.firmware_frame, self.help_frame, self.ros_frame, self.settings_frame]:
            if frame:
                frame.grid_forget()

    def select_button(self, button):
        for btn in [self.robot_profile_button, self.controller_button, self.kinematics_button, self.simulator_button, self.config_button, self.help_button, self.ros_button, self.settings_button]:
            btn.configure(fg_color="transparent" if btn != button else "gray75")

    def update_texts(self):
        """update ui texts"""
        current_lang = Config.get_current_lang()
        self.robot_profile_button.configure(text=current_lang["robot_profile"])
        self.controller_button.configure(text=current_lang["controller"])
        self.config_button.configure(text=current_lang["firmware"])
        self.help_button.configure(text=current_lang["help"])
        self.ros_button.configure(text=current_lang["ros"])
        self.kinematics_button.configure(text=current_lang["kinematics"])
        self.simulator_button.configure(text=current_lang["simulator"])
        self.majordomo_button.configure(text=current_lang["majordomo"])
        self.settings_button.configure(text=current_lang["setting"])
        
        # update texts of each sub-frame
        if self.robot_profile_frame:
            self.robot_profile_frame.update_texts()
        if self.controller_frame:
            self.controller_frame.update_texts()
        if self.firmware_frame:
            self.firmware_frame.update_texts()
        if self.simulator_frame:
            self.simulator_frame.update_texts()
        if self.help_frame:
            self.help_frame.update_texts()
        if self.ros_frame:
            self.ros_frame.update_texts()
        if self.kinematics_frame:
            self.kinematics_frame.update_texts()
        if self.majordomo_dialog:
            self.majordomo_dialog.update_texts()
        if self.settings_frame:
            self.settings_frame.update_texts()
