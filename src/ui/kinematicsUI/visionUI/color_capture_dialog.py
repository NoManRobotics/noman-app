import cv2
import numpy as np
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk
from tkinter import messagebox

class ColorCaptureDialog:
    """颜色捕获对话框
    
    用于从图像中选择颜色的独立对话框窗口
    """
    
    def __init__(self, parent, frame, on_color_selected=None):
        """初始化颜色捕获对话框
        
        Args:
            parent: 父窗口
            frame: OpenCV格式的图像帧 (BGR)
            on_color_selected: 颜色选择回调函数，接收HSV颜色值作为参数
        """
        self.parent = parent
        self.frame = frame.copy()
        self.on_color_selected = on_color_selected
        
        # 窗口和画布相关变量
        self.window = None
        self.canvas = None
        self.scale = 1.0
        self.display_width = 0
        self.display_height = 0
        
        # 颜色信息
        self.color_info = {'selected': False, 'hsv': None}
        
        # 十字光标
        self.crosshair_h = None
        self.crosshair_v = None
        
        # UI组件
        self.color_info_label = None
        self.capture_button = None
        
    def show(self):
        """显示对话框"""
        self._create_window()
        self._setup_ui()
        self._bind_events()
        
    def _create_window(self):
        """创建窗口"""
        self.window = ctk.CTkToplevel(self.parent)
        self.window.title("从帧捕获颜色")
        self.window.attributes('-topmost', True)
        
        # 计算窗口大小
        frame_height, frame_width = self.frame.shape[:2]
        max_display_width = 800
        max_display_height = 500
        
        self.scale = min(max_display_width / frame_width, max_display_height / frame_height)
        self.display_width = int(frame_width * self.scale)
        self.display_height = int(frame_height * self.scale)
        
        # 设置窗口大小
        window_width = self.display_width + 20
        window_height = self.display_height + 150
        self.window.geometry(f"{window_width}x{window_height}")
        
        # 窗口居中
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() - window_width) // 2
        y = (self.window.winfo_screenheight() - window_height) // 2
        self.window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # 设置为模态对话框
        self.window.transient(self.parent)
        self.window.grab_set()
        
    def _setup_ui(self):
        """设置UI组件"""
        # 转换图像为RGB并调整大小
        frame_rgb = cv2.cvtColor(self.frame, cv2.COLOR_BGR2RGB)
        frame_pil = Image.fromarray(frame_rgb)
        frame_pil = frame_pil.resize((self.display_width, self.display_height), Image.LANCZOS)
        
        # 创建画布
        self.canvas = tk.Canvas(
            self.window, 
            width=self.display_width, 
            height=self.display_height, 
            bg='black'
        )
        self.canvas.pack(pady=10)
        
        # 显示图像
        self.frame_tk = ImageTk.PhotoImage(frame_pil)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.frame_tk)
        
        # 说明标签
        instruction_label = ctk.CTkLabel(
            self.window, 
            text="点击图像上的任意位置选择颜色"
        )
        instruction_label.pack(pady=5)
        
        # 颜色信息标签
        self.color_info_label = ctk.CTkLabel(self.window, text="")
        self.color_info_label.pack(pady=5)
        
        # 按钮区域
        button_frame = ctk.CTkFrame(self.window, fg_color="transparent")
        button_frame.pack(fill="x", pady=10)
        
        # 捕获按钮
        self.capture_button = ctk.CTkButton(
            button_frame, 
            text="捕获颜色", 
            command=self._apply_capture, 
            state="disabled"
        )
        self.capture_button.pack(side="left", padx=10, expand=True)
        
        # 取消按钮
        cancel_button = ctk.CTkButton(
            button_frame, 
            text="取消", 
            command=self._cancel
        )
        cancel_button.pack(side="right", padx=10, expand=True)
        
    def _bind_events(self):
        """绑定事件"""
        self.canvas.bind("<Motion>", self._on_mouse_move)
        self.canvas.bind("<Button-1>", self._on_mouse_click)
        
    def _on_mouse_move(self, event):
        """鼠标移动事件处理"""
        # 删除之前的十字光标
        if self.crosshair_h:
            self.canvas.delete(self.crosshair_h)
        if self.crosshair_v:
            self.canvas.delete(self.crosshair_v)
        
        # 绘制新的十字光标
        self.crosshair_h = self.canvas.create_line(
            0, event.y, self.display_width, event.y, 
            fill='red', width=1
        )
        self.crosshair_v = self.canvas.create_line(
            event.x, 0, event.x, self.display_height, 
            fill='red', width=1
        )
        
        # 获取颜色信息
        color_info = self._get_color_at_position(event.x, event.y)
        if color_info:
            rgb, hsv = color_info
            self.color_info_label.configure(
                text=f"RGB: ({rgb[0]}, {rgb[1]}, {rgb[2]}) | "
                     f"HSV: ({hsv[0]}, {hsv[1]}, {hsv[2]})"
            )
            
    def _on_mouse_click(self, event):
        """鼠标点击事件处理"""
        color_info = self._get_color_at_position(event.x, event.y)
        if color_info:
            rgb, hsv = color_info
            
            # 存储选择的颜色
            self.color_info['selected'] = True
            self.color_info['hsv'] = [int(hsv[0]), int(hsv[1]), int(hsv[2])]
            
            # 在点击位置绘制标记
            self.canvas.create_oval(
                event.x-5, event.y-5, event.x+5, event.y+5,
                outline='yellow', width=2
            )
            
            # 启用捕获按钮
            self.capture_button.configure(state="normal")
            
    def _get_color_at_position(self, x, y):
        """获取指定位置的颜色
        
        Args:
            x, y: 画布上的坐标
            
        Returns:
            tuple: (RGB颜色, HSV颜色) 或 None
        """
        # 转换为原始图像坐标
        original_x = int(x / self.scale)
        original_y = int(y / self.scale)
        
        # 获取图像尺寸
        frame_height, frame_width = self.frame.shape[:2]
        
        # 确保坐标在范围内
        if 0 <= original_x < frame_width and 0 <= original_y < frame_height:
            # 获取BGR颜色
            bgr_color = self.frame[original_y, original_x]
            
            # 转换为RGB
            rgb_color = [bgr_color[2], bgr_color[1], bgr_color[0]]
            
            # 转换为HSV
            bgr_array = np.uint8([[[bgr_color[0], bgr_color[1], bgr_color[2]]]])
            hsv_array = cv2.cvtColor(bgr_array, cv2.COLOR_BGR2HSV)
            hsv_color = hsv_array[0][0]
            
            return (rgb_color, hsv_color)
        
        return None
        
    def _apply_capture(self):
        """应用颜色捕获"""
        if self.color_info['selected']:
            # 调用回调函数
            if self.on_color_selected:
                self.on_color_selected(self.color_info['hsv'])
            
            # 关闭窗口
            self.window.destroy()
        else:
            messagebox.showwarning("警告", "请先点击图像选择一个颜色")
            
    def _cancel(self):
        """取消操作"""
        self.window.destroy() 
