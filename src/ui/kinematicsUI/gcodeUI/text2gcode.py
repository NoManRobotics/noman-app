import os
from freetype import Face
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox
from PIL import Image, ImageDraw, ImageFont, ImageTk

from utils.tooltip import ToolTip
from utils.resource_loader import ResourceLoader

class Text2GCode:
    def __init__(self, gcode_ui, gcode_controller):
        """Initialize Text2GCode converter
        
        Args:
            parent: Parent window
            gcode_ui: Reference to GCodeController instance
        """
        self.parent = gcode_ui
        self.gcode_controller = gcode_controller
        self.available_fonts = self._load_available_fonts()
        
        self.text_dialog = None
        self.preview_canvas = None
        self.status_label = None
        self.text_input = None
        self.size_var = None
        self.spacing_var = None
        self.line_spacing_var = None
        self.font_var = None
        self.z_height_var = None
        self.safe_z_var = None
        self.ready_pos_var = None
        
        # 姿态约束变量
        self.r_enabled_var = None
        self.p_enabled_var = None
        self.y_enabled_var = None
        self.r_value_var = None
        self.p_value_var = None
        self.y_value_var = None
        
        # Load icons
        self.load_icons()
    
    def load_icons(self):
        """Load question icon"""
        path = ResourceLoader.get_asset_path(os.path.join("icons", "question_white.png"))
        self.question_icon_white = ctk.CTkImage(Image.open(path).convert("RGBA"), size=(15, 15))

    def show_dialog(self):
        """Show text to GCode conversion dialog"""
        try:
            # 创建文本输入对话框
            self.text_dialog = ctk.CTkToplevel(self.parent.dialog)
            self.text_dialog.title("Text to GCode")
            
            # 计算位置以使对话框居中显示在父窗口上
            parent_x = self.parent.dialog.winfo_rootx()
            parent_y = self.parent.dialog.winfo_rooty()
            parent_width = self.parent.dialog.winfo_width()
            parent_height = self.parent.dialog.winfo_height()
            
            dialog_width = 850
            dialog_height = 620
            
            x = parent_x + (parent_width - dialog_width) // 2
            y = parent_y + (parent_height - dialog_height) // 2
            
            # 定位对话框并确保它在屏幕上可见
            self.text_dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
            
            # 等待窗口可见再grab_set
            self.text_dialog.wait_visibility()
            self.text_dialog.grab_set()
            
            # 确保窗口始终在父窗口之上
            self.text_dialog.transient(self.parent.dialog)
            self.text_dialog.focus_set()
            
            # 初始化ready_pos变量，可以通过点击修改
            self.ready_pos_var = {
                'x': 0.087768,
                'y': 0.045273,
                'z': 0.104557
            }
            
            # 创建左右框架
            left_frame = ctk.CTkFrame(self.text_dialog)
            left_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)
            
            right_frame = ctk.CTkFrame(self.text_dialog)
            right_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)
            
            # 左侧输入区域
            text_label = ctk.CTkLabel(left_frame, text="Input text:")
            text_label.pack(pady=5)
            
            self.text_input = ctk.CTkTextbox(left_frame, height=120)
            self.text_input.pack(fill="x", padx=10, pady=5)
            
            # 参数设置区域
            font_settings_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
            font_settings_frame.pack(fill="x", padx=10, pady=(20,0))
            
            # 字体选择
            font_frame = ctk.CTkFrame(font_settings_frame, fg_color="transparent")
            font_frame.pack(fill="x", pady=2)
            ctk.CTkLabel(font_frame, text="Font:").pack(side="left")
            
            font_names = [font['name'] for font in self.available_fonts]
            self.font_var = tk.StringVar(value=font_names[0] if font_names else "")
            font_menu = ctk.CTkOptionMenu(font_frame, 
                                        values=font_names,
                                        variable=self.font_var,
                                        command=lambda _: self.view_result())
            font_menu.pack(side="left", padx=5)
            
            size_frame = ctk.CTkFrame(font_settings_frame, fg_color="transparent")
            size_frame.pack(fill="x", pady=(8,2))
            ctk.CTkLabel(size_frame, text="Font size(mm):").pack(side="left")
            self.size_var = tk.StringVar(value="10")
            size_entry = ctk.CTkEntry(size_frame, width=73, textvariable=self.size_var)
            size_entry.pack(side="left", padx=(28,5))
            
            spacing_frame = ctk.CTkFrame(font_settings_frame, fg_color="transparent")
            spacing_frame.pack(fill="x", pady=2)
            ctk.CTkLabel(spacing_frame, text="Char spacing(mm):").pack(side="left")
            self.spacing_var = tk.StringVar(value="2")
            spacing_entry = ctk.CTkEntry(spacing_frame, width=73, textvariable=self.spacing_var)
            spacing_entry.pack(side="left", padx=5)
            
            line_spacing_frame = ctk.CTkFrame(font_settings_frame, fg_color="transparent")
            line_spacing_frame.pack(fill="x", pady=2)
            ctk.CTkLabel(line_spacing_frame, text="Line spacing(mm):").pack(side="left")
            self.line_spacing_var = tk.StringVar(value="15")
            line_spacing_entry = ctk.CTkEntry(line_spacing_frame, width=73, textvariable=self.line_spacing_var)
            line_spacing_entry.pack(side="left", padx=(7,5))
            
            # Ready Position Z height setting
            ready_pos_frame = ctk.CTkFrame(font_settings_frame, fg_color="transparent")
            ready_pos_frame.pack(fill="x", pady=2)
            ctk.CTkLabel(ready_pos_frame, text="Work Z-height(m):").pack(side="left")
            self.z_height_var = tk.StringVar(value=f"{self.ready_pos_var['z']:.6f}")
            z_height_entry = ctk.CTkEntry(ready_pos_frame, width=73, textvariable=self.z_height_var)
            z_height_entry.pack(side="left", padx=(10,5))
            
            # Add question button with tooltip for Z height
            question_button = ctk.CTkButton(
                ready_pos_frame,
                text="",
                image=self.question_icon_white,
                width=20,
                height=20,
                fg_color="transparent",
                hover_color="#B3B3B3"
            )
            question_button.pack(side="left")
            ToolTip(question_button, "Z height is the distance from pen tip to the pen holder.\nYou should adjust the value in Kinematics until the pen tip touches surface.")
            
            # Safe Z height setting
            safe_z_frame = ctk.CTkFrame(font_settings_frame, fg_color="transparent")
            safe_z_frame.pack(fill="x", pady=2)
            ctk.CTkLabel(safe_z_frame, text="Safe Z-height(m):").pack(side="left")
            self.safe_z_var = tk.StringVar(value=f"{self.ready_pos_var['z'] + 0.015:.6f}")
            safe_z_entry = ctk.CTkEntry(safe_z_frame, width=73, textvariable=self.safe_z_var)
            safe_z_entry.pack(side="left", padx=(13,5))
            
            # Add question button with tooltip for Safe Z height
            safe_z_question_button = ctk.CTkButton(
                safe_z_frame,
                text="",
                image=self.question_icon_white,
                width=20,
                height=20,
                fg_color="transparent",
                hover_color="#B3B3B3"
            )
            safe_z_question_button.pack(side="left")
            ToolTip(safe_z_question_button, "Safe Z height is the height for pen lifting during movement.\nShould be higher than work Z-height to avoid collision.")
            
            # 添加姿态约束控件
            orientation_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
            orientation_frame.pack(fill="x", padx=10, pady=(15,0))
            
            # 添加标题
            orientation_title = ctk.CTkLabel(orientation_frame, text="Orientation Constraints:", font=("Helvetica", 12, "bold"))
            orientation_title.pack(anchor="w", pady=(0,5))
            
            # R (Roll, A) 控制
            r_frame = ctk.CTkFrame(orientation_frame, fg_color="transparent")
            r_frame.pack(fill="x", pady=2)
            
            self.r_enabled_var = tk.BooleanVar(value=False)
            r_checkbox = ctk.CTkCheckBox(r_frame, text="R (Roll):", variable=self.r_enabled_var, 
                                         command=lambda: self.view_result())
            r_checkbox.pack(side="left")
            
            self.r_value_var = tk.StringVar(value="0.0")
            r_entry = ctk.CTkEntry(r_frame, width=60, textvariable=self.r_value_var)
            r_entry.pack(side="left", padx=5)
            
            # P (Pitch, B) 控制
            p_frame = ctk.CTkFrame(orientation_frame, fg_color="transparent")
            p_frame.pack(fill="x", pady=2)
            
            self.p_enabled_var = tk.BooleanVar(value=False)
            p_checkbox = ctk.CTkCheckBox(p_frame, text="P (Pitch):", variable=self.p_enabled_var,
                                         command=lambda: self.view_result())
            p_checkbox.pack(side="left")
            
            self.p_value_var = tk.StringVar(value="0.0")
            p_entry = ctk.CTkEntry(p_frame, width=60, textvariable=self.p_value_var)
            p_entry.pack(side="left", padx=5)
            
            # Y (Yaw, C) 控制
            y_frame = ctk.CTkFrame(orientation_frame, fg_color="transparent")
            y_frame.pack(fill="x", pady=2)
            
            self.y_enabled_var = tk.BooleanVar(value=False)
            y_checkbox = ctk.CTkCheckBox(y_frame, text="Y (Yaw):", variable=self.y_enabled_var,
                                         command=lambda: self.view_result())
            y_checkbox.pack(side="left")
            
            self.y_value_var = tk.StringVar(value="0.0")
            y_entry = ctk.CTkEntry(y_frame, width=60, textvariable=self.y_value_var)
            y_entry.pack(side="left", padx=5)
            
            self.preview_canvas = tk.Canvas(right_frame, bg='white', width=700, height=800)
            self.preview_canvas.pack(fill="both", expand=True)
            
            # 添加状态提示标签
            self.status_label = ctk.CTkLabel(right_frame, text="Click the preview area to set Ready Position")
            self.status_label.pack(pady=5)
            
            # 绑定Canvas点击事件
            self.preview_canvas.bind("<Button-1>", self.on_canvas_click)
            
            # 按钮框架
            button_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
            button_frame.pack(fill="x", pady=(20,5))
            
            # 生成按钮
            generate_button = ctk.CTkButton(button_frame, text="Generate", command=self.generate, width=70)
            generate_button.pack(side="right", padx=(5,20))
            
            # 预览按钮
            preview_button = ctk.CTkButton(button_frame, text="Preview", command=self.view_result, width=70)
            preview_button.pack(side="right", padx=5)

        except Exception as e:
            messagebox.showerror("错误", f"打开文本转换对话框失败: {str(e)}")

    def on_canvas_click(self, event):
        """处理画布点击事件"""
        if not hasattr(self.preview_canvas, 'image'):
            return

        if self.parent.kinematics_frame.workspace['analyzed']:
            bounds = self.parent.kinematics_frame.workspace['bounds']
        else:
            self.parent.update_gcode_terminal("警告: 工作空间未分析，使用默认边界")
            bounds = {
                'x': {'min': 0.0, 'max': 0.2},
                'y': {'min': 0.0, 'max': 0.2},
                'z': {'min': 0.0, 'max': 0.2}
            }

        canvas_width = self.preview_canvas.winfo_width()
        canvas_height = self.preview_canvas.winfo_height()
        margin = 60

        workspace_width_mm = (bounds['y']['max'] - bounds['y']['min']) * 1000
        workspace_height_mm = (bounds['x']['max'] - bounds['x']['min']) * 1000

        available_width = canvas_width - 2 * margin
        available_height = canvas_height - 2 * margin

        pixels_per_mm = min(
            available_width / workspace_width_mm,
            available_height / workspace_height_mm
        )

        workspace_left = margin
        workspace_top = margin
        workspace_right = workspace_left + workspace_width_mm * pixels_per_mm
        workspace_bottom = workspace_top + workspace_height_mm * pixels_per_mm

        # 检查点击是否在工作空间范围内
        if not (workspace_left <= event.x <= workspace_right and 
                workspace_top <= event.y <= workspace_bottom):
            self.status_label.configure(text="点击位置超出工作空间范围！")
            return

        # 计算归一化比例（反向）
        rel_y = 1 - (event.x - workspace_left) / (workspace_right - workspace_left)
        rel_x = 1 - (event.y - workspace_top) / (workspace_bottom - workspace_top)

        # 物理坐标（米）
        y_m = bounds['y']['min'] + rel_y * (bounds['y']['max'] - bounds['y']['min'])
        x_m = bounds['x']['min'] + rel_x * (bounds['x']['max'] - bounds['x']['min'])

        self.ready_pos_var['x'] = x_m
        self.ready_pos_var['y'] = y_m

        self.status_label.configure(text=f"Ready Pos已设置为: X{x_m:.6f}m, Y{y_m:.6f}m, Z{self.ready_pos_var['z']:.6f}m")
        self.view_result()
    
    def view_result(self):
        """更新预览画布显示"""
        text = self.text_input.get("1.0", tk.END).strip()
        if not text:
            return
        
        # 获取参数
        size = float(self.size_var.get())
        spacing = float(self.spacing_var.get())
        line_spacing = float(self.line_spacing_var.get())
        font_name = self.font_var.get()
        
        # 获取工作空间边界
        if self.parent.kinematics_frame.workspace['analyzed']:
            bounds = self.parent.kinematics_frame.workspace['bounds']
        else:
            self.parent.update_gcode_terminal("警告: 工作空间未分析，使用默认边界")
            bounds = {
                'x': {'min': 0.0, 'max': 0.2},
                'y': {'min': 0.0, 'max': 0.2},
                'z': {'min': 0.0, 'max': 0.2}
            }
        
        # 清除画布并创建临时图像
        self.preview_canvas.delete("all")
        canvas_width = self.preview_canvas.winfo_width()
        canvas_height = self.preview_canvas.winfo_height()
        img = Image.new('RGB', (canvas_width, canvas_height), 'white')
        draw = ImageDraw.Draw(img)
        
        # 工作空间物理尺寸（毫米）
        workspace_width_mm = (bounds['y']['max'] - bounds['y']['min']) * 1000
        workspace_height_mm = (bounds['x']['max'] - bounds['x']['min']) * 1000
        
        # 计算边距和可用画布尺寸
        margin = 60
        available_width = canvas_width - 2 * margin
        available_height = canvas_height - 2 * margin
        
        # 计算缩放比例（像素/毫米）
        pixels_per_mm = min(
            available_width / workspace_width_mm,
            available_height / workspace_height_mm
        )
        
        # 调整字体大小
        preview_size = int(size * pixels_per_mm)
        
        # 加载字体
        font = None
        for font_info in self.available_fonts:
            if font_info['name'] == font_name:
                try:
                    font = ImageFont.truetype(font_info['path'], preview_size)
                    break
                except Exception as e:
                    self.parent.update_gcode_terminal(f"警告: 加载字体 {font_name} 失败 - {str(e)}")
        
        if font is None:
            font = ImageFont.load_default()
            preview_size = int(size * 10)
            self.parent.update_gcode_terminal("警告: 使用默认字体")
        
        # 计算工作空间在画布上的位置
        workspace_left = margin
        workspace_top = margin
        workspace_right = workspace_left + workspace_width_mm * pixels_per_mm
        workspace_bottom = workspace_top + workspace_height_mm * pixels_per_mm
        
        # 绘制工作空间边界框
        draw.rectangle([workspace_left, workspace_top, workspace_right, workspace_bottom], 
                       outline='#0000FF', width=2)
        
        # 网格设置
        grid_mm = 20  # 网格间距（毫米）增加到20mm
        label_interval = 2  # 每隔几条网格线显示一个标签
        grid_color = '#EEEEEE'
        ruler_color = '#666666'
        
        # 计算Y轴网格起始点和终点（毫米）
        y_min_mm = bounds['y']['min'] * 1000
        y_max_mm = bounds['y']['max'] * 1000
        
        # 确定Y轴网格线位置（以20mm为间隔）
        y_grid_start = (int(y_min_mm / grid_mm)) * grid_mm
        if y_grid_start < y_min_mm:
            y_grid_start += grid_mm
        
        # 绘制Y轴网格线和标签
        label_count = 0
        for y_mm in range(int(y_grid_start), int(y_max_mm) + grid_mm, grid_mm):
            # 计算网格线在画布上的Y坐标
            y_offset_mm = y_mm - y_min_mm
            # 反转方向：从右到左
            y_pixel = workspace_right - y_offset_mm * pixels_per_mm
            
            if workspace_left <= y_pixel <= workspace_right:
                # 绘制网格线
                draw.line([(y_pixel, workspace_top), (y_pixel, workspace_bottom)], fill=grid_color)
                # 只在特定间隔绘制Y轴刻度
                label_count += 1
                if label_count % label_interval == 0:
                    draw.text((y_pixel-20, workspace_bottom+5), f"{y_mm/1000:.3f}", fill=ruler_color)
        
        # 计算X轴网格起始点和终点（毫米）
        x_min_mm = bounds['x']['min'] * 1000
        x_max_mm = bounds['x']['max'] * 1000
        
        # 确定X轴网格线位置（以20mm为间隔）
        x_grid_start = (int(x_min_mm / grid_mm)) * grid_mm
        if x_grid_start < x_min_mm:
            x_grid_start += grid_mm
        
        # 绘制X轴网格线和标签
        label_count = 0
        for x_mm in range(int(x_grid_start), int(x_max_mm) + grid_mm, grid_mm):
            # 计算网格线在画布上的X坐标
            x_offset_mm = x_mm - x_min_mm
            x_pixel = workspace_bottom - x_offset_mm * pixels_per_mm
            
            if workspace_top <= x_pixel <= workspace_bottom:
                # 绘制网格线
                draw.line([(workspace_left, x_pixel), (workspace_right, x_pixel)], fill=grid_color)
                # 只在特定间隔绘制X轴刻度
                label_count += 1
                if label_count % label_interval == 0:
                    draw.text((workspace_left-40, x_pixel-10), f"{x_mm/1000:.3f}", fill=ruler_color)
        
        # 绘制坐标轴
        draw.line([(workspace_left, workspace_top), (workspace_left, workspace_bottom)], fill='red', width=2)
        draw.line([(workspace_left, workspace_top), (workspace_right, workspace_top)], fill='blue', width=2)
        
        # 添加坐标轴标签
        axis_font = ImageFont.load_default()
        draw.text((workspace_left-30, workspace_top-20), 
                  f"X range: {bounds['x']['min']:.3f}m - {bounds['x']['max']:.3f}m", 
                  fill='red', font=axis_font)
        draw.text((workspace_right-150, workspace_top-20), 
                  f"Y range: {bounds['y']['min']:.3f}m - {bounds['y']['max']:.3f}m", 
                  fill='blue', font=axis_font)
        
        # 获取当前使用的ready_pos，包括最新的Z高度和安全Z高度
        current_z = float(self.z_height_var.get())
        safe_z = float(self.safe_z_var.get())
        ready_pos = [self.ready_pos_var['x'], self.ready_pos_var['y'], current_z]
        
        # 计算坐标原点(0,0)在画布上的像素坐标
        origin_pixels = [
            workspace_right - (0 - bounds['y']['min']) * 1000 * pixels_per_mm,
            workspace_bottom - (0 - bounds['x']['min']) * 1000 * pixels_per_mm
        ]
        
        # 计算ready_pos在画布上的像素坐标，作为从原点(0,0)的偏移
        ready_pos_pixels = [
            workspace_right - (ready_pos[1] - bounds['y']['min']) * 1000 * pixels_per_mm,
            workspace_bottom - (ready_pos[0] - bounds['x']['min']) * 1000 * pixels_per_mm
        ]
        
        # 绘制原点十字标记
        cross_size = 15
        draw.line([
            origin_pixels[0] - cross_size, origin_pixels[1],
            origin_pixels[0] + cross_size, origin_pixels[1]
        ], fill='#00AA00', width=2)
        draw.line([
            origin_pixels[0], origin_pixels[1] - cross_size,
            origin_pixels[0], origin_pixels[1] + cross_size
        ], fill='#00AA00', width=2)
        
        # 添加原点标签
        draw.text((origin_pixels[0] + 15, origin_pixels[1] + 5), 
                f"Origin: X0.00, Y0.00", 
                fill='#00AA00')
        
        # 在ready_pos位置绘制标记
        marker_size = 5
        draw.ellipse([
            ready_pos_pixels[0] - marker_size, 
            ready_pos_pixels[1] - marker_size,
            ready_pos_pixels[0] + marker_size, 
            ready_pos_pixels[1] + marker_size
        ], fill='red')
        
        # 添加ready_pos标签
        draw.text((ready_pos_pixels[0] + 10, ready_pos_pixels[1] - 15), 
                  f"Ready Pos: X{ready_pos[0]:.6f}, Y{ready_pos[1]:.6f}", 
                  fill='red')
        
        # 计算文本起始位置（从ready_pos开始）
        start_x = ready_pos_pixels[0]
        start_y = ready_pos_pixels[1]
        
        # 绘制文本
        current_x = start_x
        current_y = start_y
        scaled_spacing = spacing * pixels_per_mm
        scaled_line_spacing = line_spacing * pixels_per_mm
        
        # 初始化文本边界框
        text_bounds = {
            'min_x': float('inf'), 'min_y': float('inf'),
            'max_x': float('-inf'), 'max_y': float('-inf')
        }
        
        # 获取姿态约束信息
        rpy_constraints = []
        if self.r_enabled_var.get():
            rpy_constraints.append(f"R: {self.r_value_var.get()}°")
        if self.p_enabled_var.get():
            rpy_constraints.append(f"P: {self.p_value_var.get()}°")
        if self.y_enabled_var.get():
            rpy_constraints.append(f"Y: {self.y_value_var.get()}°")
        
        # 绘制每行文本
        for line in text.split('\n'):
            current_x = start_x  # 每行重置X位置
            
            for char in line:
                if char.isspace():
                    current_x += scaled_spacing
                    continue
                
                # 绘制字符
                draw.text((current_x, current_y), char, font=font, fill='black')
                
                # 获取字符边界框
                bbox = draw.textbbox((current_x, current_y), char, font=font)
                
                # 绘制字符边界框
                draw.rectangle([bbox[0], bbox[1], bbox[2], bbox[3]], 
                              outline='#FF0000', width=1)
                
                # 更新整体文本边界
                text_bounds['min_x'] = min(text_bounds['min_x'], bbox[0])
                text_bounds['min_y'] = min(text_bounds['min_y'], bbox[1])
                text_bounds['max_x'] = max(text_bounds['max_x'], bbox[2])
                text_bounds['max_y'] = max(text_bounds['max_y'], bbox[3])
                
                # 更新位置
                char_width = bbox[2] - bbox[0]
                current_x += char_width + scaled_spacing
            
            # 坐标系变换 - Y方向文本向下显示
            current_y += scaled_line_spacing
        
        # 如果有文本，绘制整体边界框
        if text_bounds['min_x'] != float('inf'):
            # 绘制文本整体边界框
            draw.rectangle([
                text_bounds['min_x'], text_bounds['min_y'],
                text_bounds['max_x'], text_bounds['max_y']
            ], outline='#0000FF', width=2)
            
            # 计算文本边界框对应的物理坐标（米）
            text_physical_bounds = {
                'min_x': bounds['x']['min'] + (workspace_bottom - text_bounds['max_y']) / pixels_per_mm / 1000,
                'min_y': bounds['y']['min'] + (workspace_right - text_bounds['max_x']) / pixels_per_mm / 1000,
                'max_x': bounds['x']['min'] + (workspace_bottom - text_bounds['min_y']) / pixels_per_mm / 1000,
                'max_y': bounds['y']['min'] + (workspace_right - text_bounds['min_x']) / pixels_per_mm / 1000
            }
            
            # 显示文本边界框信息
            info_text = (
                f"bounding box:\n"
                f"Top left: X{text_physical_bounds['min_x']:.4f}, Y{text_physical_bounds['min_y']:.4f}\n"
                f"Bottom right: X{text_physical_bounds['max_x']:.4f}, Y{text_physical_bounds['max_y']:.4f}\n"
                f"Width: {(text_physical_bounds['max_x'] - text_physical_bounds['min_x']):.4f}m\n"
                f"2D Height: {(text_physical_bounds['max_y'] - text_physical_bounds['min_y']):.4f}m\n"
            )
            
            # 添加姿态约束信息
            if rpy_constraints:
                info_text += f"\nOrientation: {', '.join(rpy_constraints)}"
            
            # 在文本框下方显示信息
            info_box = [
                text_bounds['min_x'], text_bounds['max_y'] + 10,
                text_bounds['max_x'], text_bounds['max_y'] + 75
            ]
            
            # 确保信息框在工作空间内
            if info_box[3] > workspace_bottom:
                # 如果超出底部，则在文本框上方显示
                info_box = [
                    text_bounds['min_x'], text_bounds['min_y'] - 75,
                    text_bounds['max_x'], text_bounds['min_y'] - 10
                ]
            
            # 绘制信息背景
            draw.rectangle(info_box, fill='#EEEEEE')
            
            # 绘制信息文本
            info_lines = info_text.split('\n')
            for i, line in enumerate(info_lines):
                draw.text(
                    (info_box[0] + 5, info_box[1] + 5 + i * 15),
                    line, fill='#000000'
                )
        
        # 显示预览
        photo = ImageTk.PhotoImage(img)
        self.preview_canvas.create_image(0, 0, image=photo, anchor="nw")
        self.preview_canvas.image = photo

    def _load_available_fonts(self):
        """Load available fonts from assets directory"""
        fonts = []
        font_dir = ResourceLoader.get_asset_path("fonts")
        if os.path.exists(font_dir):
            for file in os.listdir(font_dir):
                if file.lower().endswith(('.ttf', '.otf')):
                    font_path = os.path.join(font_dir, file)
                    try:
                        # Try to load font to verify it's valid
                        face = Face(font_path)
                        font_name = face.family_name.decode('utf-8')
                        fonts.append({
                            'name': font_name,
                            'path': font_path
                        })
                    except Exception as e:
                        print(f"Warning: Failed to load font {file}: {str(e)}")
        return fonts
    
    def generate(self):
        """生成GCode并更新编辑器"""
        try:
            text = self.text_input.get("1.0", tk.END).strip()
            if not text:
                messagebox.showwarning("警告", "请输入要转换的文本")
                return
            
            size = float(self.size_var.get())
            spacing = float(self.spacing_var.get())
            line_spacing = float(self.line_spacing_var.get())
            font_name = self.font_var.get()
            
            # 直接从输入框读取Z高度和安全Z高度
            z_height = float(self.z_height_var.get())
            safe_z_height = float(self.safe_z_var.get())

            # 加载字体
            font_path = None
            for font_info in self.available_fonts:
                if font_info['name'] == font_name:
                    font_path = font_info['path']
                    break
            
            # 获取姿态约束
            orientation_constraints = {
                'r_enabled': self.r_enabled_var.get(),
                'p_enabled': self.p_enabled_var.get(),
                'y_enabled': self.y_enabled_var.get(),
                'r_value': float(self.r_value_var.get()) if self.r_enabled_var.get() else None,
                'p_value': float(self.p_value_var.get()) if self.p_enabled_var.get() else None,
                'y_value': float(self.y_value_var.get()) if self.y_enabled_var.get() else None
            }
            
            # Generate GCode
            success, gcode, error_msg = self.gcode_controller.text2gcode(
                text, size, spacing, line_spacing, font_path,
                ready_pos=[self.ready_pos_var['x'], self.ready_pos_var['y'], z_height],
                orientation_constraints=orientation_constraints,
                z_lift=safe_z_height - z_height
            )
            
            if success:
                # Update editor content
                self.parent.gcode_text.delete("1.0", tk.END)
                self.parent.gcode_text.insert("1.0", gcode)
                # Apply syntax highlighting after inserting text
                self.parent._apply_syntax_highlighting()
                
                self.text_dialog.destroy()
                self.parent.update_gcode_terminal("文本转换GCode完成")
            else:
                self.parent.update_gcode_terminal(error_msg)
            
        except Exception as e:
            messagebox.showerror("错误", f"生成GCode失败: {str(e)}")
