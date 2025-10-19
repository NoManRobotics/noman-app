import os
import re
import time
import numpy as np
import tkinter as tk
import customtkinter as ctk
import matplotlib
import matplotlib.pyplot as plt
from threading import Thread
from tkinter import filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from PIL import Image

from utils.config import Config
from utils.resource_loader import ResourceLoader
from ui.kinematicsUI.gcodeUI.text2gcode import Text2GCode
from noman.gcode_controller import GCodeController

# Only import VTK on Windows/Linux
if Config.operating_system != "Darwin":
    import vtk
    from vtk.util import numpy_support

class GCodeUI:
    def __init__(self, kinematics_frame):
        self.kinematics_frame = kinematics_frame
        self.dialog = None

        self.gcode_terminal = None
        self.is_executing = False
        self.pause_execution = False
        self.is_compiled = False

        self.compiled_commands = []
        self.cartesian_commands = []

        self.target_position = None
        self.target_orientation = None

        self.current_cline = 0
        self.total_clines = 0

        self.gcode_controller = GCodeController(self.kinematics_frame.robot_state, 
                                                self.kinematics_frame.planner, 
                                                self.kinematics_frame.traj_optimiser,
                                                self.kinematics_frame.traj_constraints,
                                                self.kinematics_frame.workspace)
        self.text2gcode_window = Text2GCode(self, self.gcode_controller)

        self.demo_gcode = """--main
HOME; 回到原点
VEL J1=50%, J2=75%, J3=100%; 设置关节速度限制
PTP X=0.03 Y=0.0008 Z=0.12; 起始位置
JTJ J1=20, J2=10, J3=340, vel{J1:30%,J2:50%,J3:60%}; 关节空间移动
LIN X=0.05 Y=0.0008 Z=0.128510 B=0; 下一个位置
CIRC X=0.1 Y=0.0008 Z=0.128510 I=0.02 J=0.02 K=0 B=0; 圆弧
DELAY MS=100; 延迟100毫秒
HOME; 回到原点
"""

        self.load_icons()

    def load_icons(self):
        """Load all icon images used in the interface"""
        self.editor_icon = self.load_icon("editor.png", (18, 18))
        self.commands_icon = self.load_icon("commands.png", (18, 18))
        self.lookup_icon = self.load_icon("lookup.png", (18, 18))
        self.pause_icon = self.load_icon("pause.png", (12, 12))
        self.continue_icon = self.load_icon("continue.png", (15, 15))
        self.stop_icon = self.load_icon("stop.png", (15, 15))
        self.clear_icon = self.load_icon("clear.png", (16, 16))

    def load_icon(self, filename, size):
        """Helper method to load an icon with the given filename and size"""
        path = ResourceLoader.get_asset_path(os.path.join("icons", filename))
        return ctk.CTkImage(Image.open(path).convert("RGBA"), size=size)

    def create_window(self):
        """Create G-code controller window"""
        self.dialog = ctk.CTkToplevel(self.kinematics_frame)
        self.dialog.title(Config.current_lang["gcode_controller"])
        
        # set window position
        main_window_x = self.kinematics_frame.winfo_rootx()
        main_window_y = self.kinematics_frame.winfo_rooty()
        main_window_width = self.kinematics_frame.winfo_width()
        dialog_x = main_window_x + main_window_width + 10
        dialog_y = main_window_y - 35
        self.dialog.geometry(f"850x650+{dialog_x}+{dialog_y}")

        self.dialog.wait_visibility()
        
        # create main frame
        self.main_frame = ctk.CTkFrame(self.dialog, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # left G-code editor area
        self.left_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.left_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        
        # Create toggle buttons frame
        self.toggle_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent", corner_radius=0, height=30)
        self.toggle_frame.pack(fill="x", padx=(5,0))
        self.toggle_frame.pack_propagate(False)

        self.editor_button = ctk.CTkButton(self.toggle_frame, 
                                        image=self.editor_icon,
                                        text=Config.current_lang["rcl_editor"],
                                        text_color="black",
                                        command=lambda: self.switch_view("editor"),
                                        fg_color="#f9f9fa", 
                                        hover_color="#f9f9fa",
                                        corner_radius=0,
                                        width=120,
                                        height=31)
        self.editor_button.pack(side="left")

        self.joint_button = ctk.CTkButton(self.toggle_frame, 
                                        image=self.commands_icon,
                                        text=Config.current_lang["commands"],
                                        text_color="black", 
                                        command=lambda: self.switch_view("joint"),
                                        fg_color="transparent",
                                        hover_color="#41d054", 
                                        corner_radius=0,
                                        width=120,
                                        height=31)
        self.joint_button.pack(side="left")

        self.lookup_button = ctk.CTkButton(self.toggle_frame, 
                                        image=self.lookup_icon,
                                        text=Config.current_lang["lookup"],
                                        text_color="black", 
                                        command=lambda: self.switch_view("lookup"),
                                        fg_color="transparent",
                                        hover_color="#41d054", 
                                        corner_radius=0,
                                        width=120,
                                        height=31)
        self.lookup_button.pack(side="left")
        
        # Create text container frame
        self.text_container = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        self.text_container.pack(fill="both", expand=True, padx=5, pady=(0,5))
        
        # Create textboxes for both views
        self.gcode_text = ctk.CTkTextbox(self.text_container, wrap="none", corner_radius=0, padx=5)
        self.joint_text = ctk.CTkTextbox(self.text_container, wrap="none", corner_radius=0, padx=5)
        
        # Create lookup textbox for command help
        self.lookup_text = ctk.CTkTextbox(self.text_container, wrap="word", corner_radius=0, padx=5)
        
        # Add text change listener to gcode_text
        self.gcode_text.bind('<<Modified>>', self._on_text_modified)
        self.gcode_text.pack(fill="both", expand=True)
        self.gcode_text.insert("1.0", self.demo_gcode)
        
        # Setup syntax highlighting for G-code editor
        self._setup_syntax_highlighting()
        
        # Apply initial syntax highlighting
        self._apply_syntax_highlighting()
        
        # Initialize lookup content
        self._initialize_lookup_content()
        
        # Initially hide joint commands view and lookup view
        self.current_view = "editor"
        self.joint_text.pack_forget()
        self.lookup_text.pack_forget()
        
        self.button_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        self.button_frame.pack(fill="x", padx=5, pady=5)
        
        self.load_button = ctk.CTkButton(self.button_frame, text=Config.current_lang["load_gcode"], 
                                   command=self.load_gcode,
                                   width=110,
                                   hover_color="#41d054")
        self.load_button.pack(side="left", padx=5)
        
        self.save_button = ctk.CTkButton(self.button_frame, text=Config.current_lang["save_gcode"],
                                   command=self.save_gcode,
                                   width=110,
                                   hover_color="#41d054")
        self.save_button.pack(side="left", padx=5)
        
        self.text2gcode_button = ctk.CTkButton(self.button_frame, text=Config.current_lang["text2gcode"],
                                         command=self.text2gcode,
                                         width=110,
                                         hover_color="#41d054")
        self.text2gcode_button.pack(side="left", padx=5)
        
        # 在button_frame右侧添加光标行号显示
        self.cursor_line_label = ctk.CTkLabel(self.button_frame, text="L-1",
                                           anchor="e", width=60, 
                                           font=("Arial", 10), text_color="gray")
        self.cursor_line_label.pack(side="right", padx=10)
        
        self.right_frame = ctk.CTkFrame(self.main_frame, width=300, fg_color="transparent")
        self.right_frame.pack(side="right", fill="both", padx=5, pady=0)
        self.right_frame.pack_propagate(False)
        
        # print settings
        self.settings_frame = ctk.CTkFrame(self.right_frame)
        self.settings_frame.pack(fill="x", padx=5, pady=5)
        
        # work area settings
        self.work_range_label = ctk.CTkLabel(self.settings_frame, text=Config.current_lang["work_range"])
        self.work_range_label.pack()
        
        self.area_frame = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        self.area_frame.pack(fill="x", padx=5, pady=5)
        
        # 获取workspace bounds或使用默认值
        if self.kinematics_frame.workspace['analyzed']:
            bounds = self.kinematics_frame.workspace['bounds']
            x_range = abs(bounds['x']['max'] - bounds['x']['min'])
            y_range = abs(bounds['y']['max'] - bounds['y']['min'])
            z_range = abs(bounds['z']['max'] - bounds['z']['min'])
            
            self.x_var = tk.StringVar(value=f"{x_range:.3f}")
            self.y_var = tk.StringVar(value=f"{y_range:.3f}")
            self.z_var = tk.StringVar(value=f"{z_range:.3f}")
        else:
            self.x_var = tk.StringVar(value="n/a")
            self.y_var = tk.StringVar(value="n/a") 
            self.z_var = tk.StringVar(value="n/a")
        
        self.workspace_x = ctk.CTkLabel(self.area_frame, text="X:").pack(side="left")
        x_entry = ctk.CTkEntry(self.area_frame, width=60, textvariable=self.x_var)
        x_entry.pack(side="left", padx=8)
        
        self.workspace_y = ctk.CTkLabel(self.area_frame, text="Y:").pack(side="left")
        y_entry = ctk.CTkEntry(self.area_frame, width=60, textvariable=self.y_var)
        y_entry.pack(side="left", padx=8)
        
        self.workspace_z = ctk.CTkLabel(self.area_frame, text="Z:").pack(side="left")
        z_entry = ctk.CTkEntry(self.area_frame, width=60, textvariable=self.z_var)
        z_entry.pack(side="left", padx=8)
        
        # control buttons frame
        self.control_frame = ctk.CTkFrame(self.right_frame)
        self.control_frame.pack(fill="x", padx=5, pady=5)
        
        # create top and bottom button frames
        self.top_button_frame = ctk.CTkFrame(self.control_frame, fg_color="transparent")
        self.top_button_frame.pack(fill="x", padx=5, pady=5)
        
        self.bottom_button_frame = ctk.CTkFrame(self.control_frame, fg_color="transparent") 
        self.bottom_button_frame.pack(fill="x", padx=5, pady=5)

        # first row buttons
        self.preview_button = ctk.CTkButton(self.top_button_frame, text=Config.current_lang["preview"],
                                      command=self.preview_gcode,
                                      width=120,
                                      hover_color="#41d054")
        self.preview_button.pack(side="left", padx=(8,15))

        self.complie_button = ctk.CTkButton(self.top_button_frame, text=Config.current_lang["compile"],
                                      command=self.compile_gcode,
                                      width=120,
                                      hover_color="#41d054")
        self.complie_button.pack(side="left", padx=5)
        
        self.execute_button = ctk.CTkButton(self.bottom_button_frame, text=Config.current_lang["execute"],
                                      command=self.execute_gcode,
                                      width=120,
                                      hover_color="#41d054",
                                      state="disabled")  # 初始状态为禁用
        self.execute_button.pack(side="left", padx=(8,15))
        
        self.simulate_button = ctk.CTkButton(self.bottom_button_frame, text=Config.current_lang["simulate"],
                                       command=lambda: self.execute_gcode(simulate=True),
                                       width=120,
                                       hover_color="#41d054",
                                       state="disabled")  # 初始状态为禁用
        self.simulate_button.pack(side="left", padx=5)
        
        # status display
        self.status_frame = ctk.CTkFrame(self.right_frame)
        self.status_frame.pack(fill="x", padx=5, pady=5)
        
        self.status_label = ctk.CTkLabel(self.status_frame, text=Config.current_lang["status_ready"])
        self.status_label.pack(pady=2)
        
        self.line_counter_label = ctk.CTkLabel(self.status_frame, text=f"{Config.current_lang['line_counter']}: 0/0")
        self.line_counter_label.pack(pady=2)
        
        # Add control buttons and progress bar to same frame
        self.control_progress_frame = ctk.CTkFrame(self.status_frame, fg_color="transparent")
        self.control_progress_frame.pack(fill="x", padx=5, pady=2)
        
        # Add buttons to left side
        self.button_frame = ctk.CTkFrame(self.control_progress_frame, fg_color="transparent")
        self.button_frame.pack(side="left", padx=0)
        
        self.pause_button = ctk.CTkButton(self.button_frame, 
                                        text="",
                                        image=self.pause_icon,
                                        command=self.pause_resume_execution,
                                        width=20,
                                        fg_color="transparent",
                                        hover_color="#41d054")
        self.pause_button.pack(side="left", padx=(2,0))
        
        self.stop_button = ctk.CTkButton(self.button_frame, 
                                       text="",
                                       image=self.stop_icon,
                                       command=self.stop_execution,
                                       width=20,
                                       fg_color="transparent",
                                       hover_color="#41d054")
        self.stop_button.pack(side="left", padx=2)
        
        # Add progress bar to right side
        self.progress_bar = ctk.CTkProgressBar(self.control_progress_frame)
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=5)
        self.progress_bar.set(0)

        # add terminal output frame
        self.terminal_frame = ctk.CTkFrame(self.right_frame, fg_color='transparent')
        self.terminal_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.gcode_terminal = ScrolledText(self.terminal_frame, 
                                         state=tk.DISABLED,
                                         wrap=tk.WORD,
                                         background="#000000",
                                         foreground="#41d054",
                                         width=30,
                                         height=10)
        self.gcode_terminal.pack(fill="both", expand=True, pady=5)

        # add clear terminal button
        self.clear_button = ctk.CTkButton(self.terminal_frame, 
                                    text="",
                                    image=self.clear_icon,
                                    command=self.clear_gcode_terminal,
                                    width=20,
                                    fg_color="transparent",
                                    hover_color="#41d054")
        self.clear_button.pack(side='right', padx=(0,15), pady=5)

        # 添加光标位置监听器
        self.gcode_text.bind('<ButtonRelease-1>', self._update_cursor_position)
        self.gcode_text.bind('<KeyRelease>', self._update_cursor_position)
        
        # 为joint_text也添加光标位置监听器
        self.joint_text.bind('<ButtonRelease-1>', self._update_cursor_position)
        self.joint_text.bind('<KeyRelease>', self._update_cursor_position)
        
        # 为lookup_text也添加光标位置监听器
        self.lookup_text.bind('<ButtonRelease-1>', self._update_cursor_position)
        self.lookup_text.bind('<KeyRelease>', self._update_cursor_position)
        
        # 添加Ctrl+F快捷键绑定到gcode_text (支持大小写)
        self.gcode_text._textbox.bind('<Control-f>', self._auto_fill_parameters)
        self.gcode_text._textbox.bind('<Control-F>', self._auto_fill_parameters)

    def _setup_syntax_highlighting(self):
        """Setup syntax highlighting tags for G-code editor"""
        # Get the underlying tkinter Text widget
        tk_text = self.gcode_text._textbox
        
        # Configure syntax highlighting tags
        tk_text.tag_configure("command", foreground="#a65c4a", font=("Consolas", 12, "bold"))
        tk_text.tag_configure("comment", foreground="#808080", font=("Consolas", 12, "italic"))
        tk_text.tag_configure("parameter", foreground="#0066cc")
        tk_text.tag_configure("value", foreground="#008000")
        tk_text.tag_configure("label", foreground="#800080", font=("Consolas", 12, "bold"))

    def _apply_syntax_highlighting(self):
        """Apply syntax highlighting to G-code text"""
        # Get the underlying tkinter Text widget
        tk_text = self.gcode_text._textbox
        
        # Remove all existing tags first
        for tag in ["command", "comment", "parameter", "value", "label"]:
            tk_text.tag_remove(tag, "1.0", "end")
        
        # Get text content
        content = self.gcode_text.get("1.0", "end-1c")
        lines = content.split('\n')
        
        # G-code commands to highlight
        gcode_commands = ["HOME", "LIN", "PTP", "JTJ", "CIRC", "DELAY", "TOOL", "EXEC", "VEL", "M280"]
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            
            line_start = f"{line_num}.0"
            
            # Handle comments (everything after semicolon)
            if ';' in line:
                comment_start = line.find(';')
                comment_pos = f"{line_num}.{comment_start}"
                comment_end = f"{line_num}.end"
                tk_text.tag_add("comment", comment_pos, comment_end)
                # Only process the part before the comment for other highlighting
                line = line[:comment_start].strip()
            
            # Handle labels (lines starting with --)
            if line.startswith('--'):
                tk_text.tag_add("label", line_start, f"{line_num}.end")
                continue
            
            # Process G-code commands
            if line:
                parts = line.split()
                if parts:
                    first_word = parts[0].upper()
                    
                    # Check if it's a G-code command
                    if first_word in gcode_commands:
                        # Highlight the command
                        word_start = line.find(parts[0])
                        word_pos_start = f"{line_num}.{word_start}"
                        word_pos_end = f"{line_num}.{word_start + len(parts[0])}"
                        tk_text.tag_add("command", word_pos_start, word_pos_end)
                        
                        # Highlight parameters and values
                        for part in parts[1:]:
                            if part.strip():
                                part_start = line.find(part, word_start + len(parts[0]))
                                if part_start != -1:
                                    part_pos_start = f"{line_num}.{part_start}"
                                    
                                    # Check if it's a parameter (starts with letter) or value
                                    if part[0].isalpha():
                                        # Parameter like X, Y, Z, I, J, K, A, B, C
                                        param_end = 1
                                        while param_end < len(part) and part[param_end].isalpha():
                                            param_end += 1
                                        
                                        param_pos_end = f"{line_num}.{part_start + param_end}"
                                        tk_text.tag_add("parameter", part_pos_start, param_pos_end)
                                        
                                        # Value part (after the parameter letters)
                                        if param_end < len(part):
                                            value_pos_start = f"{line_num}.{part_start + param_end}"
                                            value_pos_end = f"{line_num}.{part_start + len(part)}"
                                            tk_text.tag_add("value", value_pos_start, value_pos_end)
                                    else:
                                        # Pure value
                                        part_pos_end = f"{line_num}.{part_start + len(part)}"
                                        tk_text.tag_add("value", part_pos_start, part_pos_end)

    def clear_gcode_terminal(self):
        """Clear G-code terminal content"""
        self.gcode_terminal.configure(state=tk.NORMAL)
        self.gcode_terminal.delete(1.0, tk.END)
        self.gcode_terminal.configure(state=tk.DISABLED)

    def update_gcode_terminal(self, text):
        """Update G-code terminal display"""
        self.gcode_terminal.configure(state=tk.NORMAL)
        self.gcode_terminal.insert(tk.END, text + "\n")
        self.gcode_terminal.see(tk.END)
        self.gcode_terminal.configure(state=tk.DISABLED)

    def load_gcode(self):
        """Load G-code file"""
        file_path = filedialog.askopenfilename(
            filetypes=[("G-code files", "*.gcode *.nc"), ("All files", "*.*")])
        if file_path:
            with open(file_path, 'r') as file:
                self.gcode_text.delete("1.0", tk.END)
                self.gcode_text.insert("1.0", file.read())
                # Apply syntax highlighting after loading
                self._apply_syntax_highlighting()

    def save_gcode(self):
        """Save G-code file"""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".gcode",
            filetypes=[("G-code files", "*.gcode"), ("All files", "*.*")])
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write(self.gcode_text.get("1.0", tk.END))
                self.update_gcode_terminal(f"文件已保存到: {file_path}")
            except Exception as e:
                error_msg = f"保存文件失败: {str(e)}"
                self.update_gcode_terminal(error_msg)
                messagebox.showerror("错误", error_msg)

    def pause_resume_execution(self):
        """Pause or resume G-code execution"""
        self.pause_execution = not self.pause_execution
        status_text = Config.current_lang["status_paused"] if self.pause_execution else Config.current_lang["status_running"]
        self.status_label.configure(text=status_text)
        self.pause_button.configure(image=self.continue_icon if self.pause_execution else self.pause_icon)

    def stop_execution(self):
        """Stop G-code execution"""
        self.is_executing = False
        self.pause_execution = False
        self.status_label.configure(text=Config.current_lang["status_stopped"])
        self.pause_button.configure(image=self.pause_icon)
        self.update_gcode_terminal("Execution stopped")

    def switch_view(self, view):
        """Switch between editor and joint commands view
        
        Args:
            view (str): Either "editor" or "joint"
        """
        if view == self.current_view:
            return
            
        if view == "editor":
            self.joint_text.pack_forget()
            self.lookup_text.pack_forget()
            self.gcode_text.pack(fill="both", expand=True)
            self.editor_button.configure(fg_color="#f9f9fa", hover_color="#f9f9fa")
            self.joint_button.configure(fg_color="transparent", hover_color="#41d054")
            self.lookup_button.configure(fg_color="transparent", hover_color="#41d054")
        elif view == "joint":
            # Check if code needs to be compiled before switching to joint view
            if not self.is_compiled:
                self.compile_gcode()
                if not self.is_compiled:  # If compilation failed
                    return
                
            self.gcode_text.pack_forget()
            self.lookup_text.pack_forget()
            self.joint_text.pack(fill="both", expand=True)
            self.editor_button.configure(fg_color="transparent", hover_color="#41d054")
            self.joint_button.configure(fg_color="#f9f9fa", hover_color="#f9f9fa")
            self.lookup_button.configure(fg_color="transparent", hover_color="#41d054")
        elif view == "lookup":
            self.gcode_text.pack_forget()
            self.joint_text.pack_forget()
            self.lookup_text.pack(fill="both", expand=True)
            self.editor_button.configure(fg_color="transparent", hover_color="#41d054")
            self.joint_button.configure(fg_color="transparent", hover_color="#41d054")
            self.lookup_button.configure(fg_color="#f9f9fa", hover_color="#f9f9fa")
        
        self.current_view = view
        # 切换视图后立即更新光标位置显示
        self._update_cursor_position()

    def _on_text_modified(self, event):
        """Handle text modification events"""
        if self.gcode_text.edit_modified():  # Check if text was actually modified
            self.is_compiled = False  # Reset compiled state
            self.execute_button.configure(state="disabled")  # Disable execute button
            self.simulate_button.configure(state="disabled")  # Disable simulate button
            self.gcode_text.edit_modified(False)  # Reset modified flag
            
            # Apply syntax highlighting
            self._apply_syntax_highlighting()

            # Switch back to editor view if we're in joint or lookup view
            if self.current_view in ["joint", "lookup"]:
                self.switch_view("editor")

    def compile_gcode(self):
        gcode = self.gcode_text.get("1.0", "end-1c")

        self.compiled_commands = []
        self.cartesian_commands = []
        success, self.compiled_commands, error_msg = self.gcode_controller.compile_gcode(gcode)

        if not success:
            self.update_gcode_terminal(error_msg)
            return
        
        # record commands in cartesian space for visualisation
        self.cartesian_commands = self.gcode_controller.interpret2cartesian(self.compiled_commands)
        
        self.update_gcode_terminal(f"G代码编译完成")
        
        self.is_compiled = True
        self.execute_button.configure(state="normal")  # 启用执行按钮
        self.simulate_button.configure(state="normal") # 启用模拟按钮

        self.joint_text.delete("1.0", tk.END)
        for cmd in self.compiled_commands:
            self.joint_text.insert(tk.END, cmd)
        self.switch_view("joint")
        
        self.update_gcode_terminal(f"G代码编译完成")
                
    def execute_gcode(self, simulate=False):
        """Execute G-code command
        
        Args:
            simulate (bool): whether to run in simulation mode
        """
        if not self.is_compiled:
            messagebox.showwarning("警告", "请先编译G代码")
            return
        
        if self.is_executing:
            messagebox.showwarning("警告", "G代码正在执行中")
            return
        
        try:
            self.is_executing = True
            self.pause_execution = False
            
            execution_thread = Thread(target=self._execute_gcode_thread, 
                                args=(simulate,))
            execution_thread.daemon = True
            execution_thread.start()
            
            # start progress update
            self.dialog.after(100, self._update_execution_status)
            
        except Exception as e:
            self.is_executing = False
            error_msg = f"启动G代码执行失败: {str(e)}"
            self.update_gcode_terminal(error_msg)
            messagebox.showerror("错误", error_msg)

    def _execute_gcode_thread(self, simulate=False):
        """Execute G-code in a separate thread
        
        Args:
            simulate (bool): whether to run in simulation mode
        """
        try:
            self.update_gcode_terminal("开始执行Commands代码...")
            self.total_clines = len(self.compiled_commands)
            self.current_cline = 0
            
            # 执行主要部分
            for command in self.compiled_commands:
                if not self.is_executing:
                    break
                    
                while self.pause_execution:
                    time.sleep(0.1)
                    if not self.is_executing:
                        break
                        
                try:
                    # 跳过空行和注释
                    command = command.strip()
                    if not command:
                        continue
                    
                    self.current_cline += 1
                    self.current_command = command
                    self.update_gcode_terminal(f"> 执行: {command}")
                    
                    parts = command.split(',')
                    cmd_type = parts[0]
                    if simulate:
                        if cmd_type == 'EXEC':
                            joint_angles = np.degrees([float(angle) for angle in parts[1:]])
                            for i, (slider, value_label) in enumerate(self.kinematics_frame.joint_entries):
                                if i < len(joint_angles):
                                    angle = joint_angles[i]
                                    slider.set(angle)
                                    value_label.configure(text=f"{angle:.1f}°")
                            self.kinematics_frame.joint_angles = joint_angles
                            self.kinematics_frame.update_q(joint_angles)
                        elif cmd_type == 'DELAY':
                            delay = 0
                            param = parts[1].strip().upper()
                            if param.startswith('MS'):
                                delay = float(param[2:]) / 1000.0
                            elif param.startswith('S'):
                                delay = float(param[1:])
                            time.sleep(delay)
                        elif cmd_type == 'SPD':
                            # Handle velocity command in simulation (just log it)
                            self.update_gcode_terminal(f"  ** 设置关节速度: {','.join(parts[1:])}")
                            pass
                        elif cmd_type == 'M280':
                            # Handle gripper command in simulation
                            if len(parts) > 1:
                                # 支持多个值，parts[1:]包含所有状态值
                                state_values = [float(val) for val in parts[1:]]
                                
                                # 更新kinematics frame中的工具组件状态
                                self._update_tool_state(state_values)
                                
                                if len(state_values) == 1:
                                    self.update_gcode_terminal(f"  ** 模拟工具状态: {state_values[0]}")
                                else:
                                    self.update_gcode_terminal(f"  ** 模拟工具状态: {state_values}")
                            pass
                        
                    else:
                        if cmd_type == 'EXEC':
                            joint_angles = np.degrees([float(angle) for angle in parts[1:]])
                            joint_angles = [angle for angle in joint_angles]
                            if self.kinematics_frame.protocol_class.is_connected():
                                command = ",".join(f"{angle:.2f}" for angle in joint_angles)+'\n'
                                
                                # 重试机制：如果队列满，等待并重试
                                max_retries = 2
                                retry_count = 0
                                start_time = time.time()
                                
                                while retry_count < max_retries:
                                    self.kinematics_frame.protocol_class.send(b"EXEC\n")
                                    self.kinematics_frame.protocol_class.send(command)
                                    response, isReplied = self.kinematics_frame.protocol_class.receive(timeout=5, expected_signal="CP0")
                                    
                                    if isReplied:
                                        # 命令成功进入队列
                                        break
                                    elif response and any("QFULL" in str(r) for r in response):
                                        # 队列满，等待后重试
                                        retry_count += 1
                                        time.sleep(0.05)  # 等待50ms让队列有机会处理
                                    else:
                                        # 其他错误，抛出异常
                                        raise Exception(f"执行超时 - 第{self.current_cline}行: {self.current_command}")
                                
                                if retry_count >= max_retries:
                                    raise Exception(f"队列持续满载，无法执行 - 第{self.current_cline}行: {self.current_command}")
                                
                                end_time = time.time()
                                execution_time = end_time - start_time
                                self.update_gcode_terminal(f"  ** 耗时: {execution_time:.4f} s")
                        elif cmd_type == 'DELAY':
                            delay = 0
                            param = parts[1].strip().upper()
                            command = ""
                            if param.startswith('MS'):
                                delay = int(float(param[2:]))
                                command = f"DELAY,MS{delay}\n"
                            elif param.startswith('S'):
                                delay = float(param[1:])
                                command = f"DELAY,S{delay}\n"
                            self.kinematics_frame.protocol_class.send(command)
                        elif cmd_type == 'SPD':
                            # Handle velocity command for real robot
                            if self.kinematics_frame.protocol_class.is_connected():
                                spd_command = command if command.endswith('\n') else command + '\n'
                                self.kinematics_frame.protocol_class.send(spd_command)
                                self.update_gcode_terminal(f"  ** 设置关节速度: {','.join(parts[1:])}")
                                
                        elif cmd_type.startswith('TOOL['):  # 添加对TOOL命令的实际处理
                            if self.kinematics_frame.protocol_class.is_connected():
                                # 确保命令以换行符结尾
                                tool_command = command if command.endswith('\n') else command + '\n'
                                self.kinematics_frame.protocol_class.send(tool_command)
                                # 等待确认信号
                                _, isReplied = self.kinematics_frame.protocol_class.receive(timeout=5, expected_signal="CP2")
                                if not isReplied:
                                    raise Exception(f"工具切换超时 - 第{self.current_cline}行: {self.current_command}")
                        elif cmd_type == 'M280':
                            # Handle gripper command for real robot
                            if len(parts) > 1:
                                # 支持多个值，parts[1:]包含所有状态值
                                state_values = [float(val) for val in parts[1:]]
                                if self.kinematics_frame.protocol_class.is_connected():
                                    # Send M280 command to robot
                                    m280_command = command if command.endswith('\n') else command + '\n'
                                    self.kinematics_frame.protocol_class.send(m280_command)

                                    _, isReplied = self.kinematics_frame.protocol_class.receive(timeout=5, expected_signal="TP0")
                                    if not isReplied:
                                        self.update_gcode_terminal("M280 timeout")
                                    else:
                                        # 更新kinematics frame中的工具组件状态
                                        self._update_tool_state(state_values)
                                        
                                        if len(state_values) == 1:
                                            self.update_gcode_terminal(f"  ** 工具状态设置为: {state_values[0]}")
                                        else:
                                            self.update_gcode_terminal(f"  ** 工具状态设置为: {state_values}")
                                    
                                else:
                                    self.update_gcode_terminal("警告: 机器人未连接，无法执行夹爪命令")
                    
                except Exception as e:
                    error_msg = f"执行命令 '{command}' 时出错: {str(e)}"
                    self.update_gcode_terminal(error_msg)
                    if not messagebox.askretrycancel("错误", f"{error_msg}\n是否重试该指令?"):
                        break
            
            self.update_gcode_terminal("G代码执行完成")
                
        except Exception as e:
            self.update_gcode_terminal(f"G代码执行失败: {str(e)}")
        finally:
            self.is_executing = False
            self.current_command = None
            self.progress_bar.set(0)
            self.line_counter_label.configure(text=f"{Config.current_lang['line_counter']}: 0/0")
            self.status_label.configure(text=Config.current_lang["status_ready"])

    def _update_tool_state(self, state_values):
        """更新工具组件状态（适用于模拟和实际执行）
        
        Args:
            state_values (list): 工具状态值列表
        """
        try:
            # 获取kinematics frame的工具执行器类型
            actuation = self.kinematics_frame.actuation
            
            if actuation == "signal":
                # 信号控制型：更新开关状态并调用回调
                if hasattr(self.kinematics_frame, 'gripper_switch') and len(state_values) > 0:
                    # 将第一个值转换为布尔状态（非0为True）
                    switch_state = bool(state_values[0])
                    if switch_state:
                        self.kinematics_frame.gripper_switch.select()
                    else:
                        self.kinematics_frame.gripper_switch.deselect()
                    
                    # 调用现有的回调函数来更新状态
                    self.kinematics_frame.on_gripper_toggle()
                    
            elif actuation == "uniform movable":
                # 统一可移动执行器：设置滑块值并调用回调
                if hasattr(self.kinematics_frame, 'gripper_slider') and len(state_values) > 0:
                    value = state_values[0]
                    self.kinematics_frame.gripper_slider.set(value)
                    
                    # 调用现有的回调函数来更新状态
                    self.kinematics_frame.on_uniform_gripper_change(value)
                    
            elif actuation == "independent movable":
                # 独立可移动执行器：设置每个滑块值并调用回调
                if hasattr(self.kinematics_frame, 'gripper_sliders'):
                    for i, value in enumerate(state_values):
                        if i < len(self.kinematics_frame.gripper_sliders):
                            # 更新滑块
                            self.kinematics_frame.gripper_sliders[i].set(value)
                            
                            # 调用现有的回调函数来更新状态
                            self.kinematics_frame.on_independent_gripper_change(i)
            
        except Exception as e:
            self.update_gcode_terminal(f"更新工具模拟状态失败: {str(e)}")

    def _update_execution_status(self):
        """更新执行状态和进度"""
        try:
            if self.is_executing:
                # update progress bar
                if hasattr(self, 'total_clines') and self.total_clines > 0:
                    progress = (self.current_cline / self.total_clines)
                    self.progress_bar.set(progress)
                    self.line_counter_label.configure(text=f"{Config.current_lang['line_counter']}: {self.current_cline}/{self.total_clines}")
                
                # update status label
                status_text = Config.current_lang["status_paused"] if self.pause_execution else Config.current_lang["status_running"]
                if hasattr(self, 'current_command'):
                    status_text += f" - {self.current_command}"
                self.status_label.configure(text=status_text)
                
                # continue updating
                self.dialog.after(100, self._update_execution_status)
            else:
                # execution complete
                self.status_label.configure(text=Config.current_lang["status_complete"])
                self.progress_bar.set(1.0)
                self.pause_button.configure(image=self.pause_icon)
            
        except Exception as e:
            self.update_gcode_terminal(f"更新状态失败: {str(e)}")

    def text2gcode(self):
        """Convert text to GCode"""
        self.text2gcode_window.show_dialog()

    def preview_gcode(self):
        """预览G-code路径"""
        try:
            if Config.operating_system == "Darwin":
                self._run_matplotlib_preview()
            else:  # Windows/Linux
                preview_thread = Thread(target=self._run_vtk_preview)
                preview_thread.daemon = True
                preview_thread.start()
            
        except Exception as e:
            messagebox.showerror("错误", f"打开预览窗口失败: {str(e)}")

    def _run_matplotlib_preview(self):
        """使用 Matplotlib 运行预览窗口"""
        try:
            matplotlib.use('TkAgg')  # 使用 TkAgg 后端
            
            # 检查是否已编译
            if not self.is_compiled or not self.compiled_commands:
                if not self.compile_gcode():
                    self.update_gcode_terminal("无法预览：请先编译G代码")
                    return
            
            # 创建3D图形
            fig = plt.figure(figsize=(10, 10), dpi=100)
            ax = fig.add_subplot(111, projection='3d')
            
            # 设置标题和标签
            ax.set_title('Path preview')
            ax.set_xlabel('X-axis (m)')
            ax.set_ylabel('Y-axis (m)')
            ax.set_zlabel('Z-axis (m)')
            ax.grid(False)
            
            # 解析路径点
            path_points = []   # 所有路径点
            tool_change_points = []  # 工具切换点
            pose_data = []  # 位姿数据 [位置, 方向]
            
            # 获取当前位置作为起始点
            if self.kinematics_frame.target_position is not None:
                path_points.append(self.kinematics_frame.target_position)
            
            # 遍历笛卡尔坐标命令提取路径点
            for i, line in enumerate(self.cartesian_commands):
                line = line.strip()
                if not line:
                    continue
                
                # 解析EXEC命令（包含笛卡尔坐标）
                if line.startswith('EXEC'):
                    parts = line.split()
                    position = []
                    orientation = []
                    
                    for part in parts[1:]:
                        # 提取X、Y、Z坐标值
                        if part.startswith('X'):
                            position.append(float(part[1:]))
                        elif part.startswith('Y'):
                            position.append(float(part[1:]))
                        elif part.startswith('Z'):
                            position.append(float(part[1:]))
                        # 提取A、B、C姿态值    
                        elif part.startswith('A'):
                            orientation.append(float(part[1:]))
                        elif part.startswith('B'):
                            orientation.append(float(part[1:]))
                        elif part.startswith('C'):
                            orientation.append(float(part[1:]))
                    
                    # 添加路径点        
                    path_points.append(position)
                    # 保存位姿数据
                    pose_data.append((position, orientation))
                
                # 标记工具切换点
                elif line.startswith('TOOL'):
                    if path_points:  # 如果已有路径点
                        tool_change_points.append(path_points[-1])  # 在当前位置标记工具变化
            
            # 绘制工作空间边界
            if self.kinematics_frame.workspace_analyzed:
                bounds = self.kinematics_frame.workspace_bounds
            else:
                bounds = {
                    'x': {'min': -0.3, 'max': 0.3},
                    'y': {'min': -0.3, 'max': 0.3},
                    'z': {'min': 0.0, 'max': 0.4}
                }
            
            # 绘制边界框
            for edge in [
                [(bounds['x']['min'], bounds['y']['min'], bounds['z']['min']),
                (bounds['x']['max'], bounds['y']['min'], bounds['z']['min'])],
                [(bounds['x']['max'], bounds['y']['min'], bounds['z']['min']),
                (bounds['x']['max'], bounds['y']['max'], bounds['z']['min'])],
                [(bounds['x']['max'], bounds['y']['max'], bounds['z']['min']),
                (bounds['x']['min'], bounds['y']['max'], bounds['z']['min'])],
                [(bounds['x']['min'], bounds['y']['max'], bounds['z']['min']),
                (bounds['x']['min'], bounds['y']['min'], bounds['z']['min'])],
                [(bounds['x']['min'], bounds['y']['min'], bounds['z']['max']),
                (bounds['x']['max'], bounds['y']['min'], bounds['z']['max'])],
                [(bounds['x']['max'], bounds['y']['min'], bounds['z']['max']),
                (bounds['x']['max'], bounds['y']['max'], bounds['z']['max'])],
                [(bounds['x']['max'], bounds['y']['max'], bounds['z']['max']),
                (bounds['x']['min'], bounds['y']['max'], bounds['z']['max'])],
                [(bounds['x']['min'], bounds['y']['max'], bounds['z']['max']),
                (bounds['x']['min'], bounds['y']['min'], bounds['z']['max'])],
                [(bounds['x']['min'], bounds['y']['min'], bounds['z']['min']),
                (bounds['x']['min'], bounds['y']['min'], bounds['z']['max'])],
                [(bounds['x']['max'], bounds['y']['min'], bounds['z']['min']),
                (bounds['x']['max'], bounds['y']['min'], bounds['z']['max'])],
                [(bounds['x']['max'], bounds['y']['max'], bounds['z']['min']),
                (bounds['x']['max'], bounds['y']['max'], bounds['z']['max'])],
                [(bounds['x']['min'], bounds['y']['max'], bounds['z']['min']),
                (bounds['x']['min'], bounds['y']['max'], bounds['z']['max'])]
            ]:
                ax.plot3D(
                    [edge[0][0], edge[1][0]],
                    [edge[0][1], edge[1][1]],
                    [edge[0][2], edge[1][2]],
                    'gray', alpha=0.5
                )
            
            # 绘制路径
            if len(path_points) > 1:
                path_points = np.array(path_points)
                
                # 将路径点连接起来
                ax.plot3D(
                    path_points[:, 0],
                    path_points[:, 1],
                    path_points[:, 2],
                    'green', linewidth=2, label='Path trajectory'
                )
                
                # 绘制路径点
                ax.scatter(
                    path_points[:, 0],
                    path_points[:, 1],
                    path_points[:, 2],
                    color='blue', s=15, alpha=0.7
                )
            
            # 绘制工具切换点
            if tool_change_points:
                tool_change_points = np.array(tool_change_points)
                ax.scatter(
                    tool_change_points[:, 0],
                    tool_change_points[:, 1],
                    tool_change_points[:, 2],
                    color='red', marker='x', s=100, label='Tool change'
                )
            
            # 绘制起点
            if path_points.size > 0:
                ax.scatter(
                    [path_points[0, 0]], [path_points[0, 1]], [path_points[0, 2]],
                    color='yellow', marker='*', s=150, label='Start point'
                )
            
            # 姿态标记对象列表
            orientation_markers = []
                
            # 创建用于绘制姿态的函数
            def draw_orientation(show):
                # 清除现有姿态标记
                for marker in orientation_markers:
                    if marker in ax.collections:
                        marker.remove()
                orientation_markers.clear()
                
                if show and pose_data:
                    stride = 2 # interval of plotting
                    
                    for i in range(0, len(pose_data), stride):
                        pos, orient = pose_data[i]
                        
                        # 将RPY角度转换为方向向量（简化版本）
                        scale = Config.rcl_preview_axis_length  # 箭头长度比例因子
                        
                        # 将角度转换为弧度
                        roll, pitch, yaw = np.radians(orient)
                        
                        # X轴方向 (红色)
                        x_dir = np.array([np.cos(yaw) * np.cos(pitch),
                                        np.sin(yaw) * np.cos(pitch),
                                        -np.sin(pitch)]) * scale
                        
                        # Y轴方向 (绿色)
                        y_dir = np.array([-np.sin(yaw) * np.cos(roll) + np.cos(yaw) * np.sin(pitch) * np.sin(roll),
                                        np.cos(yaw) * np.cos(roll) + np.sin(yaw) * np.sin(pitch) * np.sin(roll),
                                        np.cos(pitch) * np.sin(roll)]) * scale
                        
                        # Z轴方向 (蓝色)
                        z_dir = np.array([np.sin(yaw) * np.sin(roll) + np.cos(yaw) * np.sin(pitch) * np.cos(roll),
                                        -np.cos(yaw) * np.sin(roll) + np.sin(yaw) * np.sin(pitch) * np.cos(roll),
                                        np.cos(pitch) * np.cos(roll)]) * scale
                        
                        # 绘制三个方向的箭头
                        x_arrow = ax.quiver(pos[0], pos[1], pos[2], x_dir[0], x_dir[1], x_dir[2], 
                                color='red', arrow_length_ratio=0.3, label='X' if i==0 else "")
                        y_arrow = ax.quiver(pos[0], pos[1], pos[2], y_dir[0], y_dir[1], y_dir[2], 
                                color='green', arrow_length_ratio=0.3, label='Y' if i==0 else "")
                        z_arrow = ax.quiver(pos[0], pos[1], pos[2], z_dir[0], z_dir[1], z_dir[2], 
                                color='blue', arrow_length_ratio=0.3, label='Z' if i==0 else "")
                        
                        orientation_markers.extend([x_arrow, y_arrow, z_arrow])
                    
                    # 添加图例
                    ax.legend()
                    
                # 刷新图形
                fig.canvas.draw_idle()
            
            # 添加用于切换姿态显示的按钮
            plt.subplots_adjust(bottom=0.15)  # 为按钮留出空间
            ax_button = plt.axes([0.85, 0.05, 0.12, 0.05])  # 位置和大小 [left, bottom, width, height]
            btn_orientation = matplotlib.widgets.Button(ax_button, 'show orientation', color='none', hovercolor='0.9')
            
            # 按钮点击事件处理函数
            def toggle_orientation(event):
                # 切换按钮文本和状态
                if btn_orientation.label.get_text() == 'show orientation':
                    btn_orientation.label.set_text('hide orientation')
                    draw_orientation(True)
                else:
                    btn_orientation.label.set_text('show orientation')
                    draw_orientation(False)
            
            # 绑定按钮点击事件
            btn_orientation.on_clicked(toggle_orientation)
            
            # 添加图例
            ax.legend()
            
            # 设置视角
            ax.view_init(elev=30, azim=45)
            
            # 设置坐标轴比例相等
            ax.set_box_aspect([1, 1, 1])
            
            # 显示图形
            plt.show()
            
        except Exception as e:
            error_msg = f"预览失败: {str(e)}"
            self.update_gcode_terminal(error_msg)
            messagebox.showerror("错误", error_msg)

    def _create_workspace_bounds(self, renderer):
        """创建工作空间边界框
        
        Args:
            renderer: VTK渲染器
        """
        # get workspace bounds
        if self.kinematics_frame.workspace['analyzed']:
            bounds = self.kinematics_frame.workspace['bounds']
        else:
            bounds = {
                'x': {'min': -0.3, 'max': 0.3},
                'y': {'min': -0.3, 'max': 0.3},
                'z': {'min': 0.0, 'max': 0.4}
            }
        
        # create 8 vertices of bounding box
        points = vtk.vtkPoints()
        points.InsertNextPoint(bounds['x']['min'], bounds['y']['min'], bounds['z']['min'])  # 0
        points.InsertNextPoint(bounds['x']['max'], bounds['y']['min'], bounds['z']['min'])  # 1
        points.InsertNextPoint(bounds['x']['max'], bounds['y']['max'], bounds['z']['min'])  # 2
        points.InsertNextPoint(bounds['x']['min'], bounds['y']['max'], bounds['z']['min'])  # 3
        points.InsertNextPoint(bounds['x']['min'], bounds['y']['min'], bounds['z']['max'])  # 4
        points.InsertNextPoint(bounds['x']['max'], bounds['y']['min'], bounds['z']['max'])  # 5
        points.InsertNextPoint(bounds['x']['max'], bounds['y']['max'], bounds['z']['max'])  # 6
        points.InsertNextPoint(bounds['x']['min'], bounds['y']['max'], bounds['z']['max'])  # 7
        
        # create 12 edges of bounding box
        lines = vtk.vtkCellArray()
        # bottom rectangle
        lines.InsertNextCell(2); lines.InsertCellPoint(0); lines.InsertCellPoint(1)
        lines.InsertNextCell(2); lines.InsertCellPoint(1); lines.InsertCellPoint(2)
        lines.InsertNextCell(2); lines.InsertCellPoint(2); lines.InsertCellPoint(3)
        lines.InsertNextCell(2); lines.InsertCellPoint(3); lines.InsertCellPoint(0)
        # top rectangle
        lines.InsertNextCell(2); lines.InsertCellPoint(4); lines.InsertCellPoint(5)
        lines.InsertNextCell(2); lines.InsertCellPoint(5); lines.InsertCellPoint(6)
        lines.InsertNextCell(2); lines.InsertCellPoint(6); lines.InsertCellPoint(7)
        lines.InsertNextCell(2); lines.InsertCellPoint(7); lines.InsertCellPoint(4)
        # vertical connecting lines
        lines.InsertNextCell(2); lines.InsertCellPoint(0); lines.InsertCellPoint(4)
        lines.InsertNextCell(2); lines.InsertCellPoint(1); lines.InsertCellPoint(5)
        lines.InsertNextCell(2); lines.InsertCellPoint(2); lines.InsertCellPoint(6)
        lines.InsertNextCell(2); lines.InsertCellPoint(3); lines.InsertCellPoint(7)
        
        # create PolyData
        polyData = vtk.vtkPolyData()
        polyData.SetPoints(points)
        polyData.SetLines(lines)
        
        # create Mapper and Actor
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(polyData)
        
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(0.5, 0.5, 1.0)  # 蓝色
        actor.GetProperty().SetLineWidth(1)
        
        renderer.AddActor(actor)

    def _create_grid(self, renderer):
        """创建参考网格
        
        Args:
            renderer: VTK渲染器
        """
        # create grid plane
        grid = vtk.vtkRectilinearGrid()
        
        # create coordinate arrays
        x = vtk.vtkFloatArray()
        y = vtk.vtkFloatArray()
        z = vtk.vtkFloatArray()
        
        # set grid range and spacing (50mm grid)
        for i in np.arange(-0.3, 0.31, 0.05):
            x.InsertNextValue(i)
            y.InsertNextValue(i)
        for i in np.arange(0, 0.41, 0.05):
            z.InsertNextValue(i)
        
        grid.SetXCoordinates(x)
        grid.SetYCoordinates(y)
        grid.SetZCoordinates(z)
        
        # create grid actor
        grid_mapper = vtk.vtkDataSetMapper()
        grid_mapper.SetInputData(grid)
        
        grid_actor = vtk.vtkActor()
        grid_actor.SetMapper(grid_mapper)
        grid_actor.GetProperty().SetRepresentationToWireframe()
        grid_actor.GetProperty().SetColor(0.8, 0.8, 0.8)  # light gray
        grid_actor.GetProperty().SetOpacity(0.3)  # semi-transparent
        
        renderer.AddActor(grid_actor)

    def _create_path_actor(self, points, color):
        """创建路径Actor
        
        Args:
            points: 路径点列表
            color: RGB颜色元组
            
        Returns:
            vtkActor: 路径Actor
        """
        if not points:
            return None
        
        # convert point data
        points_array = numpy_support.numpy_to_vtk(
            np.array(points), deep=True,
            array_type=vtk.VTK_FLOAT
        )
        
        # create point set
        points_vtk = vtk.vtkPoints()
        points_vtk.SetData(points_array)
        
        # create PolyData
        polydata = vtk.vtkPolyData()
        polydata.SetPoints(points_vtk)
        
        # create lines
        lines = vtk.vtkCellArray()
        for i in range(0, len(points), 2):
            line = vtk.vtkLine()
            line.GetPointIds().SetId(0, i)
            line.GetPointIds().SetId(1, i + 1)
            lines.InsertNextCell(line)
        
        polydata.SetLines(lines)
        
        # create Mapper
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(polydata)
        
        # create Actor
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(color)
        actor.GetProperty().SetLineWidth(2)
        
        return actor

    def _create_start_marker(self, position):
        """create start marker
        
        Args:
            position: start position coordinates
            
        Returns:
            vtkActor: marker actor
        """
        # create sphere source
        sphere = vtk.vtkSphereSource()
        sphere.SetCenter(position)
        sphere.SetRadius(Config.rcl_preview_point_radius * 3)  # start marker radius (5x larger than normal points)
        sphere.SetPhiResolution(16)
        sphere.SetThetaResolution(16)
        sphere.Update()
        
        # create Mapper
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(sphere.GetOutput())
        
        # create Actor
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(1, 1, 0)  # yellow
        
        return actor

    def _run_vtk_preview(self):
        """使用VTK运行预览窗口"""
        try:
            # 检查是否已编译
            if not self.is_compiled or not self.compiled_commands:
                if not self.compile_gcode():
                    self.update_gcode_terminal("无法预览：请先编译G代码")
                    return
            
            # 创建VTK渲染器和窗口
            renderer = vtk.vtkRenderer()
            render_window = vtk.vtkRenderWindow()
            render_window.AddRenderer(renderer)
            render_window.SetSize(800, 800)
            render_window.SetMultiSamples(0)  # 禁用MSAA
            render_window.SetLineSmoothing(1)  # 启用线条平滑
            render_window.SetWindowName("Path Preview")
            
            # 创建交互器
            interactor = vtk.vtkRenderWindowInteractor()
            interactor.SetRenderWindow(render_window)
            
            # 设置交互样式
            style = vtk.vtkInteractorStyleTrackballCamera()
            interactor.SetInteractorStyle(style)
            
            # 添加坐标轴
            axes = vtk.vtkAxesActor()
            axes.SetTotalLength(0.25, 0.25, 0.25)
            axes.SetShaftTypeToLine()
            axes.SetNormalizedShaftLength(0.85, 0.85, 0.85)
            axes.SetNormalizedTipLength(0.15, 0.15, 0.15) 
            
            # 设置坐标轴标签
            axes.GetXAxisCaptionActor2D().GetTextActor().SetTextScaleModeToNone()
            axes.GetYAxisCaptionActor2D().GetTextActor().SetTextScaleModeToNone()
            axes.GetZAxisCaptionActor2D().GetTextActor().SetTextScaleModeToNone()
            
            renderer.AddActor(axes)
            
            # 添加工作空间边界
            self._create_workspace_bounds(renderer)
            
            # 添加参考网格
            self._create_grid(renderer)
            
            # 解析轨迹点
            path_points = []  # 所有路径点
            tool_change_points = []  # 工具切换点
            pose_data = []  # 位姿数据 [位置, 方向]
            
            # 获取当前位置作为起始点
            if self.kinematics_frame.target_position is not None:
                path_points.append(self.kinematics_frame.target_position)
            
            # 遍历笛卡尔坐标命令提取路径点
            for i, line in enumerate(self.cartesian_commands):
                line = line.strip()
                if not line:
                    continue
                
                # 解析EXEC命令（包含笛卡尔坐标）
                if line.startswith('EXEC'):
                    parts = line.split()
                    position = []
                    orientation = []
                    
                    for part in parts[1:]:
                        # 提取X、Y、Z坐标值
                        if part.startswith('X'):
                            position.append(float(part[1:]))
                        elif part.startswith('Y'):
                            position.append(float(part[1:]))
                        elif part.startswith('Z'):
                            position.append(float(part[1:]))
                        # 提取A、B、C姿态值    
                        elif part.startswith('A'):
                            orientation.append(float(part[1:]))
                        elif part.startswith('B'):
                            orientation.append(float(part[1:]))
                        elif part.startswith('C'):
                            orientation.append(float(part[1:]))
                    
                    # 添加路径点        
                    path_points.append(position)
                    # 保存位姿数据
                    pose_data.append((position, orientation))
                
                # 标记工具切换点
                elif line.startswith('TOOL'):
                    if path_points:  # 如果已有路径点
                        tool_change_points.append(path_points[-1])  # 在当前位置标记工具变化
            
            # 创建路径线段
            if len(path_points) > 1:
                # 将连续的点转换为线段表示
                line_points = []
                for i in range(len(path_points) - 1):
                    line_points.extend([path_points[i], path_points[i+1]])
                
                # 创建路径Actor
                path_actor = self._create_path_actor(line_points, (0.2, 0.7, 0.2))  # 绿色
                renderer.AddActor(path_actor)
                
                # 创建并添加路径点标记
                for point in path_points:
                    sphere = vtk.vtkSphereSource()
                    sphere.SetCenter(point)
                    sphere.SetRadius(Config.rcl_preview_point_radius)
                    sphere.SetPhiResolution(12)
                    sphere.SetThetaResolution(12)
                    sphere.Update()
                    
                    mapper = vtk.vtkPolyDataMapper()
                    mapper.SetInputData(sphere.GetOutput())
                    
                    actor = vtk.vtkActor()
                    actor.SetMapper(mapper)
                    actor.GetProperty().SetColor(0.2, 0.2, 0.9)  # 蓝色
                    actor.GetProperty().SetOpacity(0.7)
                    
                    renderer.AddActor(actor)
            
            # 添加工具切换点标记
            for point in tool_change_points:
                # 创建十字形标记
                cross_points = vtk.vtkPoints()
                cross_size = 0.005  # 5mm大小
                cross_points.InsertNextPoint(point[0] - cross_size, point[1], point[2])
                cross_points.InsertNextPoint(point[0] + cross_size, point[1], point[2])
                cross_points.InsertNextPoint(point[0], point[1] - cross_size, point[2])
                cross_points.InsertNextPoint(point[0], point[1] + cross_size, point[2])
                cross_points.InsertNextPoint(point[0], point[1], point[2] - cross_size)
                cross_points.InsertNextPoint(point[0], point[1], point[2] + cross_size)
                
                lines = vtk.vtkCellArray()
                lines.InsertNextCell(2)
                lines.InsertCellPoint(0)
                lines.InsertCellPoint(1)
                lines.InsertNextCell(2)
                lines.InsertCellPoint(2)
                lines.InsertCellPoint(3)
                lines.InsertNextCell(2)
                lines.InsertCellPoint(4)
                lines.InsertCellPoint(5)
                
                polyData = vtk.vtkPolyData()
                polyData.SetPoints(cross_points)
                polyData.SetLines(lines)
                
                mapper = vtk.vtkPolyDataMapper()
                mapper.SetInputData(polyData)
                
                actor = vtk.vtkActor()
                actor.SetMapper(mapper)
                actor.GetProperty().SetColor(0.9, 0.2, 0.2)  # 红色
                actor.GetProperty().SetLineWidth(3)
                
                renderer.AddActor(actor)
            
            # 添加起点标记
            if path_points:
                start_marker = self._create_start_marker(path_points[0])
                start_marker.GetProperty().SetColor(0.7, 0.0, 0.7)  # purple
                renderer.AddActor(start_marker)
            
            # 创建姿态标记列表和图例
            orientation_actors = []
            orientation_legend_actors = []
                
            # 创建姿态图例文本
            legend_labels = ['X-axis', 'Y-axis', 'Z-axis']
            legend_colors = [(1, 0, 0), (0, 1, 0), (0, 0, 1)]  # 红、绿、蓝
            
            for i, (label, color) in enumerate(zip(legend_labels, legend_colors)):
                text_actor = vtk.vtkTextActor()
                text_actor.SetInput(label)
                text_actor.GetTextProperty().SetColor(color)
                text_actor.GetTextProperty().SetFontSize(12)
                text_actor.GetTextProperty().SetFontFamilyToArial()
                text_actor.GetPositionCoordinate().SetCoordinateSystemToNormalizedDisplay()
                text_actor.SetPosition(0.02, 0.8 - i * 0.04)
                text_actor.SetVisibility(0)  # 初始隐藏
                renderer.AddActor2D(text_actor)
                orientation_legend_actors.append(text_actor)
                
            # 创建姿态标记
            if pose_data:
                stride = 2 # interval of plotting
                for i in range(0, len(pose_data), stride):
                    pos, orient = pose_data[i]
                    
                    # 创建轴向标记
                    axes_actor = vtk.vtkAxesActor()
                    axes_actor.SetShaftTypeToCylinder()
                    axes_actor.SetCylinderRadius(0.02) # arrow radius
                    axes_actor.SetXAxisLabelText("")
                    axes_actor.SetYAxisLabelText("")
                    axes_actor.SetZAxisLabelText("")
                    
                    scale = Config.rcl_preview_axis_length # arrow length
                    axes_actor.SetTotalLength(scale, scale, scale)
                    
                    # 设置位置
                    transform = vtk.vtkTransform()
                    transform.Translate(pos)
                    
                    # 应用旋转 (ZYX顺序，对应yaw-pitch-roll)
                    transform.RotateZ(orient[2])  # Yaw
                    transform.RotateY(orient[1])  # Pitch
                    transform.RotateX(orient[0])  # Roll
                    
                    axes_actor.SetUserTransform(transform)
                    axes_actor.SetVisibility(0)  # 初始隐藏
                    
                    renderer.AddActor(axes_actor)
                    orientation_actors.append(axes_actor)
            
            # 创建按钮回调函数来切换姿态显示
            def toggle_orientation():
                # 获取第一个姿态标记的可见性并切换所有标记
                if not orientation_actors:
                    return
                    
                visible = not orientation_actors[0].GetVisibility()
                for actor in orientation_actors:
                    actor.SetVisibility(visible)
                for legend in orientation_legend_actors:
                    legend.SetVisibility(visible)
                
                # 更新按钮文本
                if visible:
                    toggle_button.GetTextActor().SetInput("Hide Orientation")
                else:
                    toggle_button.GetTextActor().SetInput("Show Orientation")
                    
                render_window.Render()
            
            # 创建按钮并设置回调
            toggle_button = vtk.vtkTextWidget()
            toggle_button_rep = vtk.vtkTextRepresentation()
            toggle_button_rep.GetPositionCoordinate().SetValue(0.85, 0.05)
            toggle_button_rep.GetPosition2Coordinate().SetValue(0.14, 0.04)
            toggle_button_rep.SetShowBorder(1)
            
            toggle_button.SetRepresentation(toggle_button_rep)
            toggle_button.SetInteractor(interactor)
            
            # 创建文本actor并设置属性
            text_actor = vtk.vtkTextActor()
            text_actor.SetInput("Show Orientation")
            text_actor.SetTextScaleModeToNone()
            text_actor.GetTextProperty().SetColor(0.0, 0.0, 0.0)
            text_actor.GetTextProperty().SetFontSize(10)
            text_actor.GetTextProperty().SetFontFamilyToArial()
            text_actor.GetTextProperty().SetJustificationToCentered()
            text_actor.GetTextProperty().SetVerticalJustificationToCentered()
            text_actor.GetTextProperty().SetBackgroundColor(0.8, 0.8, 0.8)
            text_actor.GetTextProperty().SetBackgroundOpacity(0.3)
            
            toggle_button.SetTextActor(text_actor)
            toggle_button.On()
            
            # 向按钮添加观察者
            toggle_button.AddObserver(vtk.vtkCommand.EndInteractionEvent, lambda obj, event: toggle_orientation())
            
            # Legend text
            legend_items = [
                ("● Path trajectory", (0.2, 0.7, 0.2)),  # Green
                ("● Path points", (0.2, 0.2, 0.9)),  # Blue 
                ("✕ Tool change points", (0.9, 0.2, 0.2)),  # Red
                ("★ Start point", (0.7, 0.0, 0.7))  # Purple
            ]
            
            # 创建图例文本actors
            text_actors = []
            for i, (text, color) in enumerate(legend_items):
                text_actor = vtk.vtkTextActor()
                text_actor.SetInput(text)
                text_actor.GetTextProperty().SetColor(color)
                text_actor.GetTextProperty().SetFontSize(12)
                text_actor.GetTextProperty().SetFontFamilyToArial()
                text_actor.GetPositionCoordinate().SetCoordinateSystemToNormalizedDisplay()
                text_actor.SetPosition(0.02, 0.97 - i * 0.04)
                renderer.AddActor2D(text_actor)
                text_actors.append(text_actor)
            
            # 设置相机位置
            renderer.ResetCamera()
            camera = renderer.GetActiveCamera()
            camera.SetPosition(1.0, 1.0, 1.0)
            camera.SetFocalPoint(0, 0, 0)
            camera.SetViewUp(0, 0, 1)
            
            # 设置背景颜色
            renderer.SetBackground(0.859, 0.859, 0.859)  # #dbdbdb
            
            # 开始交互
            render_window.Render()
            interactor.Initialize()
            interactor.Start()
            
        except Exception as e:
            error_msg = f"预览失败: {str(e)}"
            self.update_gcode_terminal(error_msg)
            messagebox.showerror("错误", error_msg)

    def _update_cursor_position(self, event=None):
        """更新显示光标当前所在的行号"""
        try:
            # 根据当前视图选择正确的文本框
            if self.current_view == "editor":
                position = self.gcode_text.index(ctk.INSERT)
            elif self.current_view == "joint":
                position = self.joint_text.index(ctk.INSERT)
            else:  # lookup view
                position = self.lookup_text.index(ctk.INSERT)
            
            line = int(position.split('.')[0])
            self.cursor_line_label.configure(text=f"L-{line}")
        except Exception as e:
            print(f"更新光标位置时出错: {str(e)}")

    def _auto_fill_parameters(self, event=None):
        """Ctrl+F快捷键：根据命令类型自动填充参数"""
        try:
            # 阻止默认的粘贴行为
            if event:
                # 获取当前光标位置
                cursor_pos = self.gcode_text.index(ctk.INSERT)
                line_num = int(cursor_pos.split('.')[0])
                
                # 获取当前行内容
                line_start = f"{line_num}.0"
                line_end = f"{line_num}.end"
                current_line = self.gcode_text.get(line_start, line_end).strip()
                
                # 解析命令类型
                if not current_line:
                    return "break"  # 阻止默认粘贴
                
                parts = current_line.split()
                if not parts:
                    return "break"
                
                command = parts[0].upper()
                
                # 检查是否只有命令，没有参数
                if len(parts) > 1:
                    self.update_gcode_terminal(f"信息: 行已包含参数，跳过自动填充")
                    return "break"
                
                # 根据命令类型生成参数
                parameters = ""
                
                if command in ["PTP", "LIN"]:
                    # PTP和LIN命令：使用目标位置和方向
                    if (hasattr(self.kinematics_frame, 'target_position') and 
                        self.kinematics_frame.target_position is not None and
                        hasattr(self.kinematics_frame, 'target_orientation') and 
                        self.kinematics_frame.target_orientation is not None):
                        
                        pos = self.kinematics_frame.target_position
                        orient = self.kinematics_frame.target_orientation
                        parameters = f" X={pos[0]:.4f} Y={pos[1]:.4f} Z={pos[2]:.4f} A={orient[0]:.2f} B={orient[1]:.2f} C={orient[2]:.2f}"
                    else:
                        self.update_gcode_terminal("警告: 无法获取目标位置和方向信息")
                        return "break"
                
                elif command == "CIRC":
                    # CIRC命令：使用目标位置、I=0 J=0 K=0和目标方向
                    if (hasattr(self.kinematics_frame, 'target_position') and 
                        self.kinematics_frame.target_position is not None and
                        hasattr(self.kinematics_frame, 'target_orientation') and 
                        self.kinematics_frame.target_orientation is not None):
                        
                        pos = self.kinematics_frame.target_position
                        orient = self.kinematics_frame.target_orientation
                        parameters = f" X={pos[0]:.4f} Y={pos[1]:.4f} Z={pos[2]:.4f} I=0 J=0 K=0 A={orient[0]:.2f} B={orient[1]:.2f} C={orient[2]:.2f}"
                    else:
                        self.update_gcode_terminal("警告: 无法获取目标位置和方向信息")
                        return "break"
                
                elif command == "JTJ":
                    # JTJ命令：使用当前关节角度
                    if (hasattr(self.kinematics_frame, 'joint_angles') and 
                        self.kinematics_frame.joint_angles is not None):
                        
                        angles = self.kinematics_frame.joint_angles
                        if len(angles) >= 3:
                            parameters = f" J1={angles[0]:.2f}, J2={angles[1]:.2f}, J3={angles[2]:.2f}"
                            # 如果有更多关节，继续添加
                            if len(angles) > 3:
                                for i in range(3, len(angles)):
                                    parameters += f", J{i+1}={angles[i]:.2f}"
                        else:
                            self.update_gcode_terminal("警告: 关节角度数量不足")
                            return "break"
                    else:
                        self.update_gcode_terminal("警告: 无法获取当前关节角度")
                        return "break"
                
                else:
                    # 不支持的命令类型
                    self.update_gcode_terminal(f"信息: 命令 '{command}' 不支持自动填充")
                    return "break"
                
                # 在当前行末尾插入参数
                if parameters:
                    self.gcode_text.insert(line_end, parameters)
                    
                    # 重新应用语法高亮
                    self._apply_syntax_highlighting()
                    
                    # 移动光标到行末
                    new_end = f"{line_num}.end"
                    self.gcode_text.mark_set(ctk.INSERT, new_end)
                    
                    self.update_gcode_terminal(f"已自动填充 {command} 命令参数")
                
                return "break"  # 阻止默认的粘贴行为
            
        except Exception as e:
            self.update_gcode_terminal(f"自动填充参数时出错: {str(e)}")
            return "break"

    def _setup_lookup_syntax_highlighting(self):
        """Setup syntax highlighting tags for lookup text"""
        # Get the underlying tkinter Text widget
        tk_text = self.lookup_text._textbox
        
        # Configure syntax highlighting tags
        tk_text.tag_configure("heading", foreground="#2c3e50", font=("Arial", 12, "bold"))
        tk_text.tag_configure("command", foreground="#a65c4a", font=("Consolas", 11, "bold"))
        tk_text.tag_configure("heading_command", foreground="#a65c4a", font=("Arial", 12, "bold"))  # Same as heading font but command color
        tk_text.tag_configure("parameter", foreground="#0066cc")
        tk_text.tag_configure("value", foreground="#0066cc")  # Same blue color as parameters
        tk_text.tag_configure("label", foreground="#800080", font=("Consolas", 12, "bold"))  # Same as editor label style

    def _apply_lookup_syntax_highlighting(self):
        """Apply syntax highlighting to lookup text"""
        # Get the underlying tkinter Text widget
        tk_text = self.lookup_text._textbox
        
        # Remove all existing tags first
        for tag in ["heading", "command", "heading_command", "parameter", "value", "label"]:
            tk_text.tag_remove(tag, "1.0", "end")
        
        # Get text content
        content = self.lookup_text.get("1.0", "end-1c")
        lines = content.split('\n')
        
        # First pass: apply highlighting and collect positions to remove markers
        markers_to_remove = []  # List of (line_num, start, end) tuples
        
        for line_num, line in enumerate(lines, 1):
            line_start = f"{line_num}.0"
            is_heading = False
            
            # Handle headings (lines starting with ##)
            if line.strip().startswith('##'):
                is_heading = True
                # Find the ## marker position
                marker_pos = line.find('##')
                if marker_pos != -1:
                    # Mark the ## for removal
                    markers_to_remove.append((line_num, marker_pos, marker_pos + 3))  # "## "
                    # Apply heading tag to the rest of the line (will be applied after command processing)
            
            # Handle label identifiers within @@ markers
            label_matches = list(re.finditer(r'@@([^@]+)@@', line))
            for match in label_matches:
                start_col = match.start()
                end_col = match.end()
                label_text = match.group(1)  # Get the label without @@
                
                # Mark the @@ markers for removal
                markers_to_remove.append((line_num, start_col, start_col + 2))  # First @@
                markers_to_remove.append((line_num, end_col - 2, end_col))     # Second @@
                
                # Apply label tag to just the label text
                label_start = f"{line_num}.{start_col + 2}"
                label_end = f"{line_num}.{end_col - 2}"
                tk_text.tag_add("label", label_start, label_end)
            
            # Handle commands within $$ markers (process for all lines, including headings)
            command_matches = list(re.finditer(r'\$\$([A-Z_0-9]+)\$\$', line))
            for match in command_matches:
                start_col = match.start()
                end_col = match.end()
                command_text = match.group(1)  # Get the command without $$
                
                # Mark the $$ markers for removal
                markers_to_remove.append((line_num, start_col, start_col + 2))  # First $$
                markers_to_remove.append((line_num, end_col - 2, end_col))     # Second $$
                
                # Apply command tag to just the command text
                command_start = f"{line_num}.{start_col + 2}"
                command_end = f"{line_num}.{end_col - 2}"
                
                # Use different tag for commands in headings vs regular commands
                if is_heading:
                    tk_text.tag_add("heading_command", command_start, command_end)
                else:
                    tk_text.tag_add("command", command_start, command_end)
            
            # Apply heading tag after command processing (if this is a heading line)
            if is_heading:
                # We'll apply the heading tag to the entire line after markers are removed
                # For now, just continue to skip parameter/value processing for heading lines
                continue
            
            # Handle parameters (letters followed by optional numbers and =)
            param_matches = re.finditer(r'([A-Za-z]+[0-9]*)=', line)
            for match in param_matches:
                start_col = match.start()
                end_col = match.start() + len(match.group(1))  # Only highlight the parameter part
                param_start = f"{line_num}.{start_col}"
                param_end = f"{line_num}.{end_col}"
                tk_text.tag_add("parameter", param_start, param_end)
            
            # Handle values in angle brackets
            value_matches = re.finditer(r'<[^>]+>', line)
            for match in value_matches:
                start_col = match.start()
                end_col = match.end()
                value_start = f"{line_num}.{start_col}"
                value_end = f"{line_num}.{end_col}"
                tk_text.tag_add("value", value_start, value_end)
            
            # Handle square brackets
            bracket_matches = re.finditer(r'\[[^\]]*\]', line)
            for match in bracket_matches:
                start_col = match.start()
                end_col = match.end()
                bracket_start = f"{line_num}.{start_col}"
                bracket_end = f"{line_num}.{end_col}"
                tk_text.tag_add("value", bracket_start, bracket_end)
        
        # Second pass: remove markers (in reverse order to maintain correct positions)
        markers_to_remove.sort(key=lambda x: (x[0], x[1]), reverse=True)
        heading_lines = []  # Track which lines were headings
        
        for line_num, start_col, end_col in markers_to_remove:
            start_pos = f"{line_num}.{start_col}"
            end_pos = f"{line_num}.{end_col}"
            
            # Check if this is a heading marker (## at the beginning)
            if start_col == 0 and end_col == 3:  # This is the "## " marker
                heading_lines.append(line_num)
            
            tk_text.delete(start_pos, end_pos)
        
        # Third pass: reapply heading formatting to lines that were headings
        for line_num in heading_lines:
            line_start = f"{line_num}.0"
            line_end = f"{line_num}.end"
            tk_text.tag_add("heading", line_start, line_end)

    def _initialize_lookup_content(self):
        """Initialize lookup content with G-code command help"""
        help_content = Config.current_lang["gcode_lookup"]
        
        # Setup syntax highlighting
        self._setup_lookup_syntax_highlighting()
        
        # Insert the help content and make it read-only
        self.lookup_text.insert("1.0", help_content.strip())
        self._apply_lookup_syntax_highlighting()
        self.lookup_text.configure(state="disabled")

    def update_texts(self):
        """Update all text labels with current language"""
        
        # Update window title if dialog exists
        self.dialog.title(Config.current_lang["gcode_controller"])
        
        self.editor_button.configure(text=Config.current_lang["rcl_editor"])
        self.joint_button.configure(text=Config.current_lang["commands"])
        self.lookup_button.configure(text=Config.current_lang["lookup"])
        self.load_button.configure(text=Config.current_lang["load_gcode"])
        self.save_button.configure(text=Config.current_lang["save_gcode"])
        self.text2gcode_button.configure(text=Config.current_lang["text2gcode"])
        self.work_range_label.configure(text=Config.current_lang["work_range"])
        self.preview_button.configure(text=Config.current_lang["preview"])
        self.complie_button.configure(text=Config.current_lang["compile"])
        self.execute_button.configure(text=Config.current_lang["execute"])
        self.simulate_button.configure(text=Config.current_lang["simulate"])
        
        # Update status labels - preserve current status state
        current_text = self.status_label.cget("text")
        if "Ready" in current_text or "就绪" in current_text or "準備完了" in current_text:
            self.status_label.configure(text=Config.current_lang["status_ready"])
        elif "Paused" in current_text or "暂停" in current_text or "一時停止" in current_text:
            self.status_label.configure(text=Config.current_lang["status_paused"])
        elif "Running" in current_text or "运行中" in current_text or "実行中" in current_text:
            self.status_label.configure(text=Config.current_lang["status_running"])
        elif "Stopped" in current_text or "已停止" in current_text or "停止" in current_text:
            self.status_label.configure(text=Config.current_lang["status_stopped"])
        elif "Complete" in current_text or "完成" in current_text or "完了" in current_text:
            self.status_label.configure(text=Config.current_lang["status_complete"])
        
        # Update line counter label - preserve current count
        current_text = self.line_counter_label.cget("text")
        # Extract the numbers from current text
        match = re.search(r'(\d+)/(\d+)', current_text)
        if match:
            current_line = match.group(1)
            total_lines = match.group(2)
            self.line_counter_label.configure(text=f"{Config.current_lang['line_counter']}: {current_line}/{total_lines}")
        else:
            self.line_counter_label.configure(text=f"{Config.current_lang['line_counter']}: 0/0")
        
        # Update lookup content
        self.lookup_text.configure(state="normal")
        self.lookup_text.delete("1.0", "end")
        self.lookup_text.insert("1.0", Config.current_lang["gcode_lookup"].strip())
        self._apply_lookup_syntax_highlighting()
        self.lookup_text.configure(state="disabled")
