import cv2
import tkinter as tk
import customtkinter as ctk

class CameraSetup:
    def __init__(self, parent, controller):
        self.parent = parent
        self.controller = controller
        self.setup_window = None
        self.scan_status_label = None
        self.available_cameras = []
        self.is_scanning = False
        self.camera_resolution_vars = {}  # 存储每个摄像头的分辨率选择
        
    def open_camera_setup(self):
        """打开相机设置窗口"""
        # 检查是否已达到最大相机数量
        if self.controller.get_camera_count() >= self.controller.get_max_cameras():
            self.show_error(f"已达到最大相机数量限制 ({self.controller.get_max_cameras()})。请先移除一个相机。")
            return
            
        self.setup_window = ctk.CTkToplevel(self.parent)
        self.setup_window.title("相机设置")
        self.setup_window.geometry("480x420")  # 减小高度以避免窗口过长
        self.setup_window.transient(self.parent)  # 设置为主窗口的子窗口
        self.setup_window.update_idletasks()
        self.setup_window.grab_set()  # 模态窗口
        
        # 窗口关闭时清理引用
        self.setup_window.protocol("WM_DELETE_WINDOW", self.cleanup_setup_window)
        
        # 配置setup_window的grid权重
        self.setup_window.grid_rowconfigure(0, weight=0)  # 相机类型选择行
        self.setup_window.grid_rowconfigure(1, weight=1)  # 参数框架行 - 分配更多空间
        self.setup_window.grid_rowconfigure(2, weight=0)  # 按钮行
        self.setup_window.grid_columnconfigure(0, weight=1)  # 所有列都可以扩展
        
        # 相机类型选择
        camera_type_frame = ctk.CTkFrame(self.setup_window)
        camera_type_frame.grid(row=0, column=0, padx=10, pady=5, sticky="ew")
        
        camera_type_frame.grid_columnconfigure(0, weight=0)
        for i in range(1, 4):  # 为三个单选按钮分配权重
            camera_type_frame.grid_columnconfigure(i, weight=1)
            
        ctk.CTkLabel(camera_type_frame, text="相机类型:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        
        self.camera_type_var = tk.StringVar(value="webcam")
        camera_types = [("网络摄像头", "webcam"), ("IP摄像头", "ip_camera"), ("ZED相机", "zed_camera")]
        
        for i, (text, value) in enumerate(camera_types):
            ctk.CTkRadioButton(
                camera_type_frame, 
                text=text,
                variable=self.camera_type_var, 
                value=value,
                command=self.update_setup_form
            ).grid(row=0, column=i+1, padx=5, pady=5)
        
        # 参数设置框架
        self.param_frame = ctk.CTkFrame(self.setup_window)
        self.param_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        
        # 按钮框架
        button_frame = ctk.CTkFrame(self.setup_window, fg_color="transparent")
        button_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        
        button_frame.grid_columnconfigure(0, weight=1)  # 中间空白区域
        button_frame.grid_columnconfigure(1, weight=0)  # 取消按钮
        button_frame.grid_columnconfigure(2, weight=0)  # 确定按钮
        
        ctk.CTkButton(
            button_frame, 
            text="确定", 
            command=self.add_camera
        ).grid(row=0, column=2, padx=5, pady=5, sticky="e")
        
        ctk.CTkButton(
            button_frame, 
            text="取消", 
            command=self.cleanup_setup_window
        ).grid(row=0, column=1, padx=5, pady=5, sticky="e")
        
        # 初始化表单
        self.update_setup_form()
    
    def cleanup_setup_window(self):
        """关闭设置窗口并清理引用"""
        if self.setup_window and self.setup_window.winfo_exists():
            self.setup_window.destroy()
        self.setup_window = None
        self.scan_status_label = None
        
    def update_setup_form(self):
        """根据相机类型更新设置表单"""
        # 清空参数框架
        for widget in self.param_frame.winfo_children():
            widget.destroy()
            
        camera_type = self.camera_type_var.get()
        
        if camera_type == "webcam":
            # 网络摄像头设置
            self.setup_webcam_form()
            
        elif camera_type == "ip_camera":
            self.setup_ip_camera_form()
            
        elif camera_type == "zed_camera":
            # ZED相机设置 - 确保信息标签居中
            self.param_frame.grid_rowconfigure(0, weight=1)
            self.param_frame.grid_columnconfigure(0, weight=1)
            
            # 创建一个框架让内容填充可用空间并居中
            zed_frame = ctk.CTkFrame(self.param_frame)
            zed_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
            
            # 让内容垂直居中
            zed_frame.grid_rowconfigure(0, weight=1)
            zed_frame.grid_rowconfigure(1, weight=0)  # 文本标签
            zed_frame.grid_rowconfigure(2, weight=1)
            zed_frame.grid_columnconfigure(0, weight=1)
            
            info_label = ctk.CTkLabel(
                zed_frame, 
                text="ZED not supported yet\nUse IP/WEB camera", 
                justify="center"
            )
            info_label.grid(row=1, column=0, padx=20, pady=20)
    
    def setup_webcam_form(self):
        """设置网络摄像头表单"""
        # 配置网格布局
        self.param_frame.grid_rowconfigure(0, weight=0)  # 扫描按钮行
        self.param_frame.grid_rowconfigure(1, weight=0)  # 标题行
        self.param_frame.grid_rowconfigure(2, weight=1)  # 列表区域
        self.param_frame.grid_columnconfigure(0, weight=1)
        
        # 初始化默认ID
        self.webcam_id_var = tk.StringVar(value="0")
        
        # 创建扫描按钮框架
        input_frame = ctk.CTkFrame(self.param_frame, fg_color="transparent")
        input_frame.grid(row=0, column=0, padx=10, pady=5, sticky="ew")
        
        input_frame.grid_columnconfigure(0, weight=1)
        
        # 扫描按钮
        scan_button = ctk.CTkButton(
            input_frame,
            text="扫描可用摄像头",
            width=150,
            height=32,
            command=self.start_camera_scan
        )
        scan_button.grid(row=0, column=0, padx=5, pady=10)
        
        # 创建列标题框架
        title_frame = ctk.CTkFrame(self.param_frame, fg_color="transparent")
        title_frame.grid(row=1, column=0, padx=10, pady=(5,0), sticky="ew")
        
        # 选择标签
        ctk.CTkLabel(
            title_frame,
            text="选择",
            font=("Arial", 12, "bold"),
            text_color="#333333"
        ).grid(row=0, column=0, padx=15, pady=5)
        
        # 设备名称标签
        ctk.CTkLabel(
            title_frame,
            text="设备名称", 
            font=("Arial", 12, "bold"),
            text_color="#333333"
        ).grid(row=0, column=1, padx=(50,15), pady=5, sticky="w")
        
        # 分辨率标签
        ctk.CTkLabel(
            title_frame,
            text="分辨率",
            font=("Arial", 12, "bold"),
            text_color="#333333"
        ).grid(row=0, column=2, padx=(50,0), pady=5)
        
        # 添加分隔线
        separator_frame = ctk.CTkFrame(title_frame, height=1, fg_color="#CCCCCC")
        separator_frame.grid(row=1, column=0, columnspan=3, sticky="ew", padx=5, pady=(0,5))
        
        # 创建状态和列表区域
        self.camera_list_frame = ctk.CTkFrame(self.param_frame, fg_color="transparent")
        self.camera_list_frame.grid(row=2, column=0, padx=10, pady=(0,5), sticky="nsew")
        
        # 提示文本
        self.hint_label = ctk.CTkLabel(
            self.camera_list_frame,
            text="系统将自动检测和列出可用的摄像头设备\n选择一个设备后点击确定添加",
            text_color="gray",
            justify="center"
        )
        self.hint_label.pack(expand=True)
    
    def setup_ip_camera_form(self):
        """设置IP摄像头表单"""
        self.param_frame.grid_rowconfigure(0, weight=1)
        self.param_frame.grid_columnconfigure(0, weight=1)
        
        # 创建表单框架并使其填充整个可用空间
        form_frame = ctk.CTkFrame(self.param_frame, fg_color="transparent")
        form_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        # 表单内部结构 - 增加行数以容纳新字段
        for i in range(8):  # 8行参数（增加分辨率行）
            form_frame.grid_rowconfigure(i, weight=0)
        # 添加额外的空行来推动表单向上对齐
        form_frame.grid_rowconfigure(8, weight=1)
        
        form_frame.grid_columnconfigure(0, weight=0)  # 标签列
        form_frame.grid_columnconfigure(1, weight=1)  # 输入框列
        
        # 协议选择
        ctk.CTkLabel(form_frame, text="协议:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.protocol_var = tk.StringVar(value="http")
        protocol_menu = ctk.CTkOptionMenu(
            form_frame,
            variable=self.protocol_var,
            values=["http", "rtsp", "mjpeg"],
            command=self.on_protocol_changed
        )
        protocol_menu.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        # IP地址
        ctk.CTkLabel(form_frame, text="IP地址:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.ip_address_var = tk.StringVar(value="192.168.1.100")
        ctk.CTkEntry(form_frame, textvariable=self.ip_address_var).grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        
        # 端口
        ctk.CTkLabel(form_frame, text="端口:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.port_var = tk.StringVar(value="8081")
        ctk.CTkEntry(form_frame, textvariable=self.port_var).grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        
        # 路径
        ctk.CTkLabel(form_frame, text="路径:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.path_var = tk.StringVar(value="")
        path_entry = ctk.CTkEntry(form_frame, textvariable=self.path_var, placeholder_text="例如: /video 或 /stream")
        path_entry.grid(row=3, column=1, padx=5, pady=5, sticky="ew")
        
        # 常用路径下拉菜单
        ctk.CTkLabel(form_frame, text="常用路径:").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        self.common_path_var = tk.StringVar(value="选择常用路径")
        self.common_path_menu = ctk.CTkOptionMenu(
            form_frame,
            variable=self.common_path_var,
            values=["选择常用路径"],
            command=self.on_common_path_selected
        )
        self.common_path_menu.grid(row=4, column=1, padx=5, pady=5, sticky="ew")
        
        # 用户名
        ctk.CTkLabel(form_frame, text="用户名:").grid(row=5, column=0, padx=5, pady=5, sticky="w")
        self.username_var = tk.StringVar(value="")
        ctk.CTkEntry(form_frame, textvariable=self.username_var, placeholder_text="留空表示不需要认证").grid(row=5, column=1, padx=5, pady=5, sticky="ew")
        
        # 密码
        ctk.CTkLabel(form_frame, text="密码:").grid(row=6, column=0, padx=5, pady=5, sticky="w")
        self.password_var = tk.StringVar(value="")
        ctk.CTkEntry(form_frame, textvariable=self.password_var, show="*", placeholder_text="留空表示不需要认证").grid(row=6, column=1, padx=5, pady=5, sticky="ew")
        
        # 分辨率选择
        ctk.CTkLabel(form_frame, text="分辨率:").grid(row=7, column=0, padx=5, pady=5, sticky="w")
        self.ip_resolution_var = tk.StringVar(value="640x480")
        ip_resolution_options = ["320x240", "640x480", "800x600", "1024x768", "1280x720", "1280x960", "1600x1200", "1920x1080"]
        ctk.CTkOptionMenu(
            form_frame,
            variable=self.ip_resolution_var,
            values=ip_resolution_options,
            width=120
        ).grid(row=7, column=1, padx=5, pady=5, sticky="w")
        
        # 初始化协议相关设置
        self.on_protocol_changed("http")
    
    def on_protocol_changed(self, selected_protocol):
        """当协议改变时更新端口和常用路径"""
        from noman.camera_controller.cameras.ip_camera import IpCamera
        
        # 创建临时对象获取协议信息
        temp_camera = IpCamera("", 0, "", "", selected_protocol)
        protocol_info = temp_camera.get_protocol_info()
        
        if selected_protocol in protocol_info:
            info = protocol_info[selected_protocol]
            
            # 更新默认端口
            self.port_var.set(str(info["default_port"]))
            
            # 更新常用路径选项
            paths = ["选择常用路径"] + info["common_paths"]
            self.common_path_menu.configure(values=paths)
            self.common_path_var.set("选择常用路径")
    
    def on_common_path_selected(self, selected_path):
        """当选择常用路径时更新路径字段"""
        if selected_path != "选择常用路径":
            self.path_var.set(selected_path)
    
    def get_camera_resolutions(self, camera_id):
        """获取摄像头支持的分辨率列表"""
        # 常见的分辨率列表
        common_resolutions = [
            (640, 480),   # VGA
            (1280, 720),  # HD 720p
            (1280, 960),  # 4:3 HD
            (1920, 1080), # Full HD 1080p
        ]
        
        supported_resolutions = []
        
        try:
            # 临时打开摄像头来测试分辨率
            cap = cv2.VideoCapture(camera_id)
            if not cap.isOpened():
                return [("640x480", 640, 480)]  # 返回默认分辨率
            
            for width, height in common_resolutions:
                # 尝试设置分辨率
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                
                # 检查实际设置的分辨率
                actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                
                # 如果实际分辨率匹配请求的分辨率，则认为支持
                if actual_width == width and actual_height == height:
                    resolution_text = f"{width}x{height}"
                    supported_resolutions.append((resolution_text, width, height))
            
            cap.release()
            
            # 如果没有找到支持的分辨率，返回默认值
            if not supported_resolutions:
                supported_resolutions = [("640x480", 640, 480)]
                
        except Exception as e:
            print(f"检测摄像头 {camera_id} 分辨率时出错: {str(e)}")
            supported_resolutions = [("640x480", 640, 480)]
        
        return supported_resolutions
    
    def start_camera_scan(self):
        """开始扫描摄像头"""
        self.hint_label.configure(text="Scanning available cameras...")  
        self.refresh_camera_list(callback=self.update_camera_list_ui)
    
    def refresh_camera_list(self, callback=None):
        """刷新可用摄像头列表（异步）"""
        # 如果已经在扫描中，则不再启动新的扫描
        if self.is_scanning:
            return
            
        self.is_scanning = True
        
        # 创建并启动线程
        import threading
        threading.Thread(
            target=self._scan_cameras_thread,
            args=(callback,),
            daemon=True
        ).start()
    
    def _scan_cameras_thread(self, callback):
        """摄像头扫描线程"""
        try:
            self.available_cameras = self.controller.list_available_cameras()
            
            if callback:
                self.setup_window.after(0, callback)
        finally:
            self.is_scanning = False
    
    def update_camera_list_ui(self):
        """更新摄像头列表UI"""
        # 清除相机列表区域内容
        for widget in self.camera_list_frame.winfo_children():
            widget.destroy()
        
        # 检查是否找到摄像头
        if not self.available_cameras:
            # 显示未找到相机的提示
            no_camera_frame = ctk.CTkFrame(self.camera_list_frame, fg_color="transparent")
            no_camera_frame.pack(fill="both", expand=True)
            
            self.hint_label = ctk.CTkLabel(
                no_camera_frame,
                text="No camera detected",
                text_color="#FF6B6B",
                font=("Arial", 13),
                justify="center"
            )
            self.hint_label.pack(expand=True)
            return
        
        # 创建滚动区域
        scroll_frame = ctk.CTkScrollableFrame(self.camera_list_frame)
        scroll_frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        # 设置默认选择第一个相机
        if self.available_cameras:
            self.webcam_id_var.set(str(self.available_cameras[0]["id"]))
        
        # 清空之前的分辨率变量
        self.camera_resolution_vars.clear()
        
        # 添加相机选项
        for i, camera in enumerate(self.available_cameras):
            camera_id = camera["id"]
            
            camera_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
            camera_frame.pack(fill="x", padx=2, pady=1)
            
            # 单选按钮
            radio_button = ctk.CTkRadioButton(
                camera_frame,
                text="",
                variable=self.webcam_id_var,
                value=str(camera_id),
                fg_color="#007BFF",
                border_color="#007BFF"
            )
            radio_button.grid(row=0, column=0, padx=0, pady=8)
            
            # 设备名称标签
            name_label = ctk.CTkLabel(
                camera_frame,
                text=camera["name"],
                anchor="w"
            )
            name_label.grid(row=0, column=1, padx=(5,10), pady=8, sticky="w")
            
            # 获取支持的分辨率
            supported_resolutions = self.get_camera_resolutions(camera_id)
            resolution_options = [res[0] for res in supported_resolutions]  # 只要显示文本
            
            # 创建分辨率选择变量
            resolution_var = tk.StringVar(value=resolution_options[0] if resolution_options else "640x480")
            self.camera_resolution_vars[camera_id] = {
                'var': resolution_var,
                'resolutions': supported_resolutions
            }
            
            # 分辨率选择菜单
            resolution_menu = ctk.CTkOptionMenu(
                camera_frame,
                variable=resolution_var,
                values=resolution_options,
                width=120
            )
            resolution_menu.grid(row=0, column=2, padx=10, pady=8)
    
    def add_camera(self):
        """根据设置添加相机"""
        camera_type = self.camera_type_var.get()
        
        try:
            success = False
            result = None
            
            if camera_type == "webcam":
                # 检查是否已选择相机
                if not self.webcam_id_var.get():
                    self.show_error("Scan first and then select a camera")
                    return
                    
                camera_id = int(self.webcam_id_var.get())
                
                # 获取选择的分辨率
                width, height = 640, 480  # 默认分辨率
                if camera_id in self.camera_resolution_vars:
                    selected_resolution = self.camera_resolution_vars[camera_id]['var'].get()
                    # 从分辨率列表中找到对应的宽高值
                    for res_text, res_width, res_height in self.camera_resolution_vars[camera_id]['resolutions']:
                        if res_text == selected_resolution:
                            width, height = res_width, res_height
                            break
                
                success, result = self.controller.create_webcam(camera_id, width, height)
                
            elif camera_type == "ip_camera":
                ip_address = self.ip_address_var.get()
                port = int(self.port_var.get())
                username = self.username_var.get()
                password = self.password_var.get()
                protocol = self.protocol_var.get()
                path = self.path_var.get()
                
                # 获取选择的分辨率
                resolution_text = self.ip_resolution_var.get()
                width, height = 640, 480  # 默认分辨率
                if 'x' in resolution_text:
                    try:
                        width, height = map(int, resolution_text.split('x'))
                    except ValueError:
                        pass  # 使用默认分辨率
                
                success, result = self.controller.create_ip_camera(ip_address, port, username, password, protocol, path, width, height)
                
            elif camera_type == "zed_camera":
                success, result = self.controller.create_zed_camera()
                
            if success:
                # 成功添加相机后直接关闭设置窗口，不再询问是否激活
                self.cleanup_setup_window()
            else:
                self.show_error(f"添加相机失败: {result}")
                
        except Exception as e:
            self.show_error(f"添加相机时出错: {str(e)}")
    
    def show_error(self, message):
        """显示错误对话框"""
        error_window = ctk.CTkToplevel(self.parent)
        error_window.title("错误")
        error_window.geometry("300x150")
        error_window.transient(self.parent)
        error_window.grab_set()
        
        ctk.CTkLabel(
            error_window, 
            text=message,
            wraplength=280
        ).pack(padx=20, pady=20)
        
        ctk.CTkButton(
            error_window, 
            text="确定", 
            command=error_window.destroy
        ).pack(pady=10) 
