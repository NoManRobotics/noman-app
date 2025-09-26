import tkinter as tk
import customtkinter as ctk
from utils.config import Config


class CommandInfoDialog:
    """命令信息显示对话框类"""
    
    def __init__(self, parent, command_button_map=None, command_filter=None):
        """
        初始化命令信息对话框
        
        Args:
            parent: 父窗口
            command_button_map: 命令到按钮的映射字典，用于高亮显示
            command_filter: 要显示的命令列表，如果为None则显示所有命令
        """
        self.parent = parent
        self.command_button_map = command_button_map or {}
        self.command_filter = command_filter
        self.original_colors = {}
        self.window = None
        
    def show(self):
        """显示命令信息窗口"""
        if self.window and self.window.winfo_exists():
            self.window.lift()
            return
            
        # 创建新窗口
        self.window = ctk.CTkToplevel(self.parent)
        self.window.title(Config.current_lang["command_info_title"])
        self.window.withdraw()

        # 设置窗口位置
        main_window_x = self.parent.winfo_rootx()
        main_window_y = self.parent.winfo_rooty()
        main_window_width = self.parent.winfo_width()
        window_x = main_window_x + main_window_width + 10
        window_y = main_window_y - 38
        
        self.window.geometry(f"790x870+{window_x}+{window_y}")
        self.window.resizable(False, False)

        # 设置窗口内容
        self._setup_content()
        
        # 确保所有待处理的事件都被处理完毕
        self.window.update_idletasks()
        
        # 显示窗口
        self.window.deiconify()
        
        # 将窗口提到最前面
        self.window.lift()
        self.window.focus_force()
        
        # 绑定窗口关闭事件
        self.window.protocol("WM_DELETE_WINDOW", self._on_closing)
        
    def _setup_content(self):
        """设置窗口内容"""
        # 配置窗口网格
        self.window.grid_columnconfigure(0, weight=1)
        self.window.grid_rowconfigure(0, weight=1)

        # 创建可滚动框架
        scroll_frame = ctk.CTkScrollableFrame(
            self.window,
            height=900,
            fg_color="transparent"
        )
        scroll_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=(0,15))
        scroll_frame.grid_columnconfigure(0, weight=1)

        # 获取命令分类
        categories = self._get_command_categories()
        
        # 保存原始颜色
        self._save_original_colors()

        current_row = 0
        for category in categories:
            category_frame = ctk.CTkFrame(
                scroll_frame,
                fg_color="#B3B3B3"
            )
            category_frame.grid(row=current_row, column=0, sticky="nsew", pady=5, padx=5)
            category_frame.grid_columnconfigure(0, weight=1)
            current_row += 1

            # 创建列标题行
            header_frame = ctk.CTkFrame(
                category_frame,
                fg_color="transparent"
            )
            header_frame.grid(row=0, column=0, sticky="nsew", pady=5, padx=10)
            header_frame.grid_columnconfigure(2, weight=1)

            # 添加列标题
            for col_idx, column_title in enumerate(category["columns"]):
                header_label = ctk.CTkLabel(
                    header_frame,
                    text=column_title,
                    font=("Arial", 14, "bold"),
                    text_color="black",
                    width=180 if col_idx < 2 else 0,
                    anchor="w"
                )
                header_label.grid(row=0, column=col_idx, padx=10, pady=5)

            # 创建命令列表框架
            commands_frame = ctk.CTkFrame(
                category_frame,
                fg_color="transparent"
            )
            commands_frame.grid(row=1, column=0, sticky="nsew", pady=(0,10), padx=10)
            commands_frame.grid_columnconfigure(2, weight=1)

            # 添加命令行
            for cmd_idx, (cmd, data, desc) in enumerate(category["commands"]):
                self._create_command_row(commands_frame, cmd_idx, cmd, data, desc)

    def _get_command_categories(self):
        """获取命令分类数据"""
        all_commands = [
            ("EXEC", "J1,J2,J3,J4,...", "执行关节角度和工具状态"),
            ("REP", "J1,J2,J3,J4,...", "直接设置PWM(不进行轨迹插值)"),
            ("M280", "state", "设置工具状态"),
            ("RECONCET", "", "记录一次工具状态"),
            ("RECONCEJ", "", "记录一次关节角度"),
            ("SPD", "speed_factor", "设置速度"),
            ("RECSTART", "", "开始记录机械臂轨迹"),
            ("RECSTOP", "", "停止记录并保存轨迹数据"),
            ("POTON", "", "启用电位器控制模式"),
            ("POTOFF", "", "禁用电位器控制模式"),
            ("VERC", "", "获取固件版本和硬件信息"),
            ("CALIBRATE", "joint,offset", "关节校准偏移量"),
            ("TOROS", "", "切换到ROS控制模式"),
            ("TOCTR", "", "切换到控制器模式"),
            ("TOOL[GRIPPER]", ",IO11..", "配置夹爪工具(MINIMA)"),
            ("TOOL[PEN]", "", "配置笔架工具(MINIMA)"),
            ("TOOL[PUMP]", ",IO0,IO1..", "配置真空泵工具(MINIMA)"),
            ("DELAY", "S/MS", "延迟,秒/毫秒")
        ]
        
        # 如果有命令过滤器，只显示过滤后的命令
        if self.command_filter:
            filtered_commands = [cmd for cmd in all_commands if cmd[0] in self.command_filter]
        else:
            filtered_commands = all_commands
            
        return [
            {
                "columns": ["Commands", "Data", "Description"],
                "commands": filtered_commands
            }
        ]

    def _create_command_row(self, parent_frame, row_idx, cmd, data, desc):
        """创建命令行"""
        cmd_frame = ctk.CTkFrame(
            parent_frame,
            fg_color="transparent"
        )
        cmd_frame.grid(row=row_idx, column=0, sticky="nsew", pady=2)
        cmd_frame.grid_columnconfigure(2, weight=1)

        # 创建事件框架来捕获鼠标事件
        event_frame = ctk.CTkFrame(
            cmd_frame,
            fg_color="transparent"
        )
        event_frame.grid(row=0, column=0, columnspan=3, sticky="nsew")
        
        # 命令文本
        cmd_label = ctk.CTkLabel(
            event_frame,
            text=cmd,
            font=("Arial", 12),
            text_color="black",
            width=180,
            anchor="w"
        )
        cmd_label.grid(row=0, column=0, padx=10, pady=4)

        # 数据格式文本
        if data:
            data_label = ctk.CTkLabel(
                event_frame,
                text=data,
                font=("Arial", 12),
                text_color="black",
                width=200,
                anchor="w"
            )
            data_label.grid(row=0, column=1, padx=10, pady=4)

        # 描述文本
        desc_label = ctk.CTkLabel(
            event_frame,
            text=desc,
            font=("Arial", 12),
            text_color="black",
            justify="left",
            anchor="w"
        )
        desc_label.grid(row=0, column=2, padx=10, pady=4, sticky="nsew")

        # 为整行添加鼠标悬停效果
        if cmd in self.command_button_map:
            self._bind_hover_events(event_frame, cmd)

    def _save_original_colors(self):
        """保存按钮的原始颜色"""
        self.original_colors = {}
        for button in self.command_button_map.values():
            if isinstance(button, (ctk.CTkButton, ctk.CTkSwitch)):
                self.original_colors[button] = button.cget("fg_color")
            elif isinstance(button, ctk.CTkOptionMenu):
                self.original_colors[button] = button.cget("button_color")
            elif isinstance(button, ctk.CTkLabel):
                self.original_colors[button] = button.cget("text_color")

    def _bind_hover_events(self, frame, cmd):
        """绑定鼠标悬停事件"""
        def on_enter(e):
            frame.configure(fg_color="#DDDDDD")
            button = self.command_button_map[cmd]
            if isinstance(button, ctk.CTkButton):
                button.configure(fg_color="#41d054")
            elif isinstance(button, ctk.CTkSwitch):
                button.configure(progress_color="#41d054")
            elif isinstance(button, ctk.CTkOptionMenu):
                button.configure(fg_color="#41d054")
            elif isinstance(button, ctk.CTkLabel) and cmd.startswith("SPD"):
                button.configure(text_color="#41d054")

        def on_leave(e):
            frame.configure(fg_color="transparent")
            button = self.command_button_map[cmd]
            if isinstance(button, ctk.CTkButton):
                button.configure(fg_color=self.original_colors[button])
            elif isinstance(button, ctk.CTkSwitch):
                button.configure(progress_color=self.original_colors[button])
            elif isinstance(button, ctk.CTkOptionMenu):
                button.configure(fg_color=self.original_colors[button])
            elif isinstance(button, ctk.CTkLabel) and cmd.startswith("SPD"):
                button.configure(text_color="black")

        frame.bind("<Enter>", on_enter)
        frame.bind("<Leave>", on_leave)

        # 确保标签也能触发事件
        for widget in frame.winfo_children():
            widget.bind("<Enter>", on_enter)
            widget.bind("<Leave>", on_leave)

    def update_command_button_map(self, command_button_map, command_filter=None):
        """更新命令按钮映射"""
        self.command_button_map = command_button_map
        if command_filter is not None:
            self.command_filter = command_filter
        self._save_original_colors()
        
        # 如果窗口已经打开，清除内容并重新创建
        if self.window and self.window.winfo_exists():
            # 清除窗口中的所有内容
            for widget in self.window.winfo_children():
                widget.destroy()
            # 重新设置内容
            self._setup_content()

    def _on_closing(self):
        """窗口关闭时的清理工作"""
        if self.window:
            self.window.destroy()
            self.window = None 
