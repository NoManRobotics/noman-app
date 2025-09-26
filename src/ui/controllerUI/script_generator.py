import os
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox, filedialog

from utils.config import Config
from utils.resource_loader import ResourceLoader

class ScriptGenerator:
    def __init__(self, parent_frame):
        self.parent_frame = parent_frame
        self.servo_count = parent_frame.servo_count
        self.joint_limits = parent_frame.joint_limits
        self.home_angles = parent_frame.home_angles
        self.script_dialog = None

    def create_window(self):
        self.script_dialog = ctk.CTkToplevel(self.parent_frame)
        self.script_dialog.title(Config.current_lang["generate_script"])

        main_window_x = self.parent_frame.winfo_rootx()
        main_window_y = self.parent_frame.winfo_rooty()
        main_window_width = self.parent_frame.winfo_width()

        anytroller_x = main_window_x + main_window_width + 10
        anytroller_y = main_window_y - 38
        
        self.script_dialog.geometry(f"1080x920+{anytroller_x}+{anytroller_y}")
        self.script_dialog.resizable(False, False)
        
        self.script_dialog.grid_columnconfigure(0, weight=1)
        self.script_dialog.grid_columnconfigure(1, weight=10)
        self.script_dialog.grid_rowconfigure(0, weight=1)
        
        self.left_frame = ctk.CTkFrame(self.script_dialog)
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.left_frame.grid_rowconfigure(2, weight=1)
        
        self.script_right_frame = ctk.CTkFrame(self.script_dialog, fg_color="transparent")
        self.script_right_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        
        # 添加代码显示区域
        self.code_text = ctk.CTkTextbox(
            self.script_right_frame,
            wrap="word",
            fg_color="white",
            text_color="black",
            font=("Consolas", 12),
            width=800,
            height=800
        )
        self.code_text.pack(fill="both", expand=True)

        self.board_label = ctk.CTkLabel(self.left_frame, text=Config.current_lang["board_type"], font=("Arial", 12, "bold"))
        self.board_label.grid(row=0, column=0, padx=10, pady=(35,0), sticky="w")
        
        self.lib_label = ctk.CTkLabel(self.left_frame, text=Config.current_lang["library_type"], font=("Arial", 12, "bold"))
        self.lib_label.grid(row=1, column=0, padx=10, pady=(5,10), sticky="w")

        self.lib_var = tk.StringVar(value="Adafruit_PWMServoDriver")
        self.lib_selector = ctk.CTkOptionMenu(
            self.left_frame,
            values=["Adafruit_PWMServoDriver", "Servo Library"],
            variable=self.lib_var,
            command=self.on_board_selection_change
        )
        self.lib_selector.grid(row=1, column=0, padx=(88,10), pady=(5,10), sticky="w")

        self.dynamic_content_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        self.dynamic_content_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        
        self.caution_frame = ctk.CTkFrame(self.left_frame, fg_color="#F5F5F5") 
        self.caution_frame.grid(row=3, column=0, padx=10, pady=(10,15), sticky="ew")
        
        self.caution_label = ctk.CTkLabel(
            self.caution_frame,
            text=Config.current_lang["board_caution"],
            wraplength=240, 
            text_color="#666666",
            justify="left"
        )
        self.caution_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        self.show_pwm_content()

    def show_pwm_content(self):
        for widget in self.dynamic_content_frame.winfo_children():
            widget.destroy()
            
        # Configure grid weights
        self.dynamic_content_frame.grid_columnconfigure(0, weight=1)
        
        # Joint pins label
        self.joint_pins_label = ctk.CTkLabel(self.dynamic_content_frame, text=Config.current_lang["joint_pins"], font=("Arial", 12, "bold"))
        self.joint_pins_label.grid(row=0, column=0, pady=5, sticky="w")
        
        # Joint frame
        joint_frame = ctk.CTkFrame(self.dynamic_content_frame, fg_color="transparent") 
        joint_frame.grid(row=1, column=0, pady=5, sticky="w")
        
        max_label_width = max(len(f"{Config.current_lang['joint']} {i+1}") for i in range(self.servo_count))
        max_label_width = max(max_label_width, len(Config.current_lang["gripper_pin"]))
        
        # Joint entries
        self.joint_pin_entries = []
        for i in range(self.servo_count):
            joint_label = ctk.CTkLabel(joint_frame, text=f"{Config.current_lang['joint']} {i+1}", width=max_label_width*10)
            joint_label.grid(row=i, column=0, padx=(0, 32), pady=2, sticky="w")
            joint_entry = ctk.CTkEntry(joint_frame, width=70)
            joint_entry.grid(row=i, column=1, pady=2, sticky="w")
            self.joint_pin_entries.append(joint_entry)
        
        # Gripper frame
        gripper_frame = ctk.CTkFrame(self.dynamic_content_frame, fg_color="transparent")
        gripper_frame.grid(row=2, column=0, pady=5, sticky="w")
        
        self.gripper_pin_label = ctk.CTkLabel(gripper_frame, text=Config.current_lang["gripper_pin"], width=max_label_width*10)
        self.gripper_pin_label.grid(row=0, column=0, padx=(0, 32), pady=2, sticky="w")
        self.gripper_pin_entry = ctk.CTkEntry(gripper_frame, width=70)
        self.gripper_pin_entry.grid(row=0, column=1, pady=2, sticky="w")
        
        # PWM config frame
        pwm_config_frame = ctk.CTkFrame(self.dynamic_content_frame, fg_color="transparent")
        pwm_config_frame.grid(row=3, column=0, pady=10, sticky="w")
        
        min_pulse_label = ctk.CTkLabel(pwm_config_frame, text=Config.current_lang["min_pulse"])
        min_pulse_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.min_pulse_entry = ctk.CTkEntry(pwm_config_frame, width=70)
        self.min_pulse_entry.grid(row=0, column=1, padx=(10,0), pady=5, sticky="w")
        self.min_pulse_entry.insert(0, "500")
        
        max_pulse_label = ctk.CTkLabel(pwm_config_frame, text=Config.current_lang["max_pulse"])
        max_pulse_label.grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.max_pulse_entry = ctk.CTkEntry(pwm_config_frame, width=70)
        self.max_pulse_entry.grid(row=1, column=1, padx=(10,0), pady=5, sticky="w")
        self.max_pulse_entry.insert(0, "2500")
        
        freq_label = ctk.CTkLabel(pwm_config_frame, text=Config.current_lang["frequency"])
        freq_label.grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.freq_entry = ctk.CTkEntry(pwm_config_frame, width=70)
        self.freq_entry.grid(row=2, column=1, padx=(10,0), pady=5, sticky="w")
        self.freq_entry.insert(0, "50")
        
        # Save PWM config label references
        self.min_pulse_label = min_pulse_label
        self.max_pulse_label = max_pulse_label
        self.freq_label = freq_label
        
        # 创建按钮框架
        button_frame = ctk.CTkFrame(self.dynamic_content_frame, fg_color="transparent")
        button_frame.grid(row=4, column=0, pady=10, sticky="w")

        self.default_generate_button = ctk.CTkButton(
            button_frame, 
            text=Config.current_lang["generate"], 
            command=self.default_generate_script,
            width=110,
            hover_color="#41d054"
        )
        self.default_generate_button.grid(row=0, column=0, padx=10)

        # 添加保存按钮到按钮框架中
        self.save_code_button = ctk.CTkButton(
            button_frame,
            text=Config.current_lang["save"],
            command=self.save_generated_code,
            width=110,
            hover_color="#41d054"
        )
        self.save_code_button.grid(row=0, column=1, padx=10)

    def show_servo_content(self):
        for widget in self.dynamic_content_frame.winfo_children():
            widget.destroy()
            
        # Configure grid weights
        self.dynamic_content_frame.grid_columnconfigure(0, weight=1)
        
        # Joint pins label
        self.joint_pins_label = ctk.CTkLabel(self.dynamic_content_frame, text=Config.current_lang["joint_pins"], font=("Arial", 12, "bold"))
        self.joint_pins_label.grid(row=0, column=0, pady=5, sticky="w")
        
        # Joint frame
        joint_frame = ctk.CTkFrame(self.dynamic_content_frame, fg_color="transparent")
        joint_frame.grid(row=1, column=0, pady=5, sticky="w")
        
        max_label_width = max(len(f"{Config.current_lang['joint']} {i+1}") for i in range(self.servo_count))
        max_label_width = max(max_label_width, len(Config.current_lang["gripper_pin"]))
        
        # Joint entries
        self.joint_pin_entries = []
        for i in range(self.servo_count):
            joint_label = ctk.CTkLabel(joint_frame, text=f"{Config.current_lang['joint']} {i+1}", width=max_label_width*10)
            joint_label.grid(row=i, column=0, padx=(0, 32), pady=2, sticky="w")
            joint_entry = ctk.CTkEntry(joint_frame, width=70)
            joint_entry.grid(row=i, column=1, pady=2, sticky="w")
            self.joint_pin_entries.append(joint_entry)
        
        # Gripper frame
        gripper_frame = ctk.CTkFrame(self.dynamic_content_frame, fg_color="transparent")
        gripper_frame.grid(row=2, column=0, pady=5, sticky="w")
        
        self.gripper_pin_label = ctk.CTkLabel(gripper_frame, text=Config.current_lang["gripper_pin"], width=max_label_width*10)
        self.gripper_pin_label.grid(row=0, column=0, padx=(0, 32), pady=2, sticky="w")
        self.gripper_pin_entry = ctk.CTkEntry(gripper_frame, width=70)
        self.gripper_pin_entry.grid(row=0, column=1, pady=2, sticky="w")
        
        # 创建按钮框架
        button_frame = ctk.CTkFrame(self.dynamic_content_frame, fg_color="transparent")
        button_frame.grid(row=4, column=0, pady=10, sticky="w")

        self.default_generate_button = ctk.CTkButton(
            button_frame, 
            text=Config.current_lang["generate"], 
            command=self.default_generate_script,
            width=110,
            hover_color="#41d054"
        )
        self.default_generate_button.grid(row=0, column=0, padx=10)

        # 添加保存按钮到按钮框架中
        self.save_code_button = ctk.CTkButton(
            button_frame,
            text=Config.current_lang["save"],
            command=self.save_generated_code,
            width=110,
            hover_color="#41d054"
        )
        self.save_code_button.grid(row=0, column=1, padx=10)

    def on_board_selection_change(self, choice):
        if choice == "Adafruit_PWMServoDriver":
            self.show_pwm_content()
        else:
            self.show_servo_content()

    def default_generate_script(self):
        joint_pins = [entry.get() for entry in self.joint_pin_entries]
        gripper_pin = self.gripper_pin_entry.get()
        board_type = "PWM" if self.lib_var.get() == "Adafruit_PWMServoDriver" else "Servo"
        
        num_servos = len(joint_pins)
        
        joint_home_positions = []
        joint_limits_array_lines = []
        
        # get joint limits and home positions for each joint (not including gripper)
        for i in range(num_servos):
            lower = float(self.joint_limits[i][0])  # use previous joint_limits
            upper = float(self.joint_limits[i][1])
            home = int(self.home_angles[i])  # use previous home_angles
            joint_home_positions.append(str(home))
            joint_limits_array_lines.append(f"  {{{lower:.1f}f, {upper:.1f}f}},   // joint {i+1}")
        
        # remove the last comma from the last element for proper C array syntax
        if joint_limits_array_lines:
            # Only remove the trailing comma after the closing brace, not all commas
            last_line = joint_limits_array_lines[-1]
            if last_line.endswith(',   // joint ' + str(len(joint_limits_array_lines))):
                joint_limits_array_lines[-1] = last_line.replace('},   // joint', '}   // joint')
        
        # format the joint limits array
        joint_limits_array = "\n".join(joint_limits_array_lines)
        
        if board_type == "PWM":
            template_file = ResourceLoader.get_code_path(
                os.path.join('universal_pwm', 'universal_pwm.ino')
            )
        else:
            template_file = ResourceLoader.get_code_path(
                os.path.join('universal_servo', 'universal_servo.ino')
            )
            
        try:
            with open(template_file, 'r', encoding='utf-8') as file:
                template = file.read()
        except Exception as e:
            self.log_message(f"error: cannot read template file: {str(e)}")
            messagebox.showerror("error", f"cannot read template file: {str(e)}")
            return
        
        script = template.replace('{{NUM_SERVOS}}', str(num_servos))
        script = script.replace('{{JOINT_PINS}}', ', '.join(joint_pins))
        script = script.replace('{{GRIPPER_PIN}}', gripper_pin)
        script = script.replace('{{BOARD_TYPE}}', board_type)
        script = script.replace('{{JOINT_LIMITS_ARRAY}}', joint_limits_array)
        script = script.replace('{{JOINT_HOME_POSITIONS}}', ', '.join(joint_home_positions))
        
        if board_type == "PWM":
            script = script.replace('{{MIN_PULSE_WIDTH}}', self.min_pulse_entry.get())
            script = script.replace('{{MAX_PULSE_WIDTH}}', self.max_pulse_entry.get())
            script = script.replace('{{FREQUENCY}}', self.freq_entry.get())

        # 更新代码显示区域
        self.code_text.delete(1.0, tk.END)
        self.code_text.insert(tk.END, script)

    def save_generated_code(self):
        """保存生成的代码到文件"""
        filename = filedialog.asksaveasfilename(defaultextension=".ino", filetypes=[("Arduino files", "*.ino")])
        if filename:
            try:
                code = self.code_text.get(1.0, tk.END)
                with open(filename, 'w', encoding='utf-8') as script_file:
                    script_file.write(code)
                self.log_message(f"script saved to {filename}")
            except IOError as e:
                self.log_message(f"error: cannot save generated script: {str(e)}")
                messagebox.showerror("error", f"cannot save generated script: {str(e)}")

    def log_message(self, message):
        """将日志消息转发到父框架"""
        self.parent_frame.log_message(message)

    def update_texts(self):
        """更新界面文本"""
        if self.script_dialog and self.script_dialog.winfo_exists():
            # 更新对话框标题
            self.script_dialog.title(Config.current_lang["generate_script"])
            
            # 更新基本标签
            self.board_label.configure(text=Config.current_lang["board_type"])
            self.lib_label.configure(text=Config.current_lang["library_type"])
            self.caution_label.configure(text=Config.current_lang["board_caution"])
            if hasattr(self, 'joint_pins_label') and self.joint_pins_label.winfo_exists():
                self.joint_pins_label.configure(text=Config.current_lang["joint_pins"])
            if hasattr(self, 'gripper_pin_label') and self.gripper_pin_label.winfo_exists():
                self.gripper_pin_label.configure(text=Config.current_lang["gripper_pin"])
            
            # 更新PWM配置标签
            if hasattr(self, 'min_pulse_label') and self.min_pulse_label.winfo_exists():
                self.min_pulse_label.configure(text=Config.current_lang["min_pulse"])
            if hasattr(self, 'max_pulse_label') and self.max_pulse_label.winfo_exists():
                self.max_pulse_label.configure(text=Config.current_lang["max_pulse"])
            if hasattr(self, 'freq_label') and self.freq_label.winfo_exists():
                self.freq_label.configure(text=Config.current_lang["frequency"])
            
            # 更新按钮
            if hasattr(self, 'default_generate_button') and self.default_generate_button.winfo_exists():
                self.default_generate_button.configure(text=Config.current_lang["generate"])
            if hasattr(self, 'save_code_button') and self.save_code_button.winfo_exists():
                self.save_code_button.configure(text=Config.current_lang["save"])
            
            # 更新关节引脚标签
            if hasattr(self, 'joint_pin_entries'):
                for i, entry in enumerate(self.joint_pin_entries):
                    if entry.winfo_exists():
                        # 查找对应的标签
                        parent_frame = entry.master
                        if parent_frame:
                            for widget in parent_frame.winfo_children():
                                if (isinstance(widget, ctk.CTkLabel) and 
                                    widget.grid_info() and 
                                    widget.grid_info().get('row') == i and 
                                    widget.grid_info().get('column') == 0):
                                    widget.configure(text=f"{Config.current_lang['joint']} {i+1}")
                                    break
            
 
