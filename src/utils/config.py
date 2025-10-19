import os
import json
import platform

from .resource_loader import ResourceLoader

# 全局配置类
class Config:
    ''' Application Version '''
    version = "1.1.1"
    release_date = "2025-10-19"
    
    ''' Language Config '''
    current_lang = None
    current_lang_name = "English"  # 记录当前语言名称

    ''' UI Config '''
    # Operating System
    operating_system = platform.system()

    if operating_system == "Windows":
        geometry = "890x950"
    elif operating_system == "Darwin":  # macOS
        geometry = "890x920"
    elif operating_system == "Linux":
        geometry = "890x980"
    else:
        geometry = "890x980"

    position_steps = 0.001
    orientation_steps = 1
    rcl_preview_point_radius = 0.0006
    rcl_preview_axis_length = 0.02

    ''' Application Config '''
    # system path for the application
    base_dir = None
    
    ''' Audio Config '''
    last_audio_device = None  # 最后选择的音频设备
    
    ''' Kinematics Config '''
    # Levenberg-Marquardt参数
    lm_lambda = 0.05
    lm_epsilon = 1e-6
    lm_max_iterations = 100
    
    # DLS参数
    dls_damping = 0.07
    dls_epsilon = 1e-6
    dls_max_iterations = 100
    
    # TRAC-IK参数
    trac_ik_epsilon = 1e-6
    trac_ik_max_iterations = 100

    ''' Trajectory Optimiser Config '''
    dt = 0.5
    trajectory_method = "scurve"  # 默认使用梯形速度曲线
    
    joint_speeds = []  # 每个关节的速度倍数
    joint_accelerations = []  # 每个关节的加速度百分比
    joint_jerks = []  # 每个关节的急动度百分比

    ''' Interpolation Config '''
    interpolation_method = "linear"  # 默认使用线性插值

    ''' Protocol Config '''
    serial_baudrate = 115200
    can_bitrate = 500000

    @classmethod
    def initialize_path(cls):
        """
        初始化应用程序基础目录
        根据操作系统设置合适的基础目录路径
        """
        if cls.operating_system == "Windows":
            cls.base_dir = os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'nomanrobotics', 'minima')
        elif cls.operating_system == "Darwin":  # macOS
            cls.base_dir = os.path.join(os.path.expanduser('~'), '.nomanrobotics', 'minima')
        elif cls.operating_system == "Linux":
            cls.base_dir = os.path.join(os.path.expanduser('~'), '.nomanrobotics', 'minima')
        else:
            # 对于其他操作系统，也使用用户目录
            cls.base_dir = os.path.join(os.path.expanduser('~'), '.nomanrobotics', 'minima')
        
        # 初始化目录结构
        cls._init_directories()
        
    @classmethod
    def _init_directories(cls):
        """
        初始化必要的目录结构
        """
        if not cls.base_dir:
            cls.initialize_path()
            
        # 创建配置目录
        config_dir = os.path.join(cls.base_dir, 'config')
        if not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)

    @classmethod
    def get_path(cls):
        """
        获取应用程序基础目录
        如果尚未初始化，则先进行初始化
        
        返回:
            str: 基础目录路径
        """
        return cls.base_dir
        
    @classmethod
    def load_language(cls, lang="English"):
        """加载语言配置"""
        language_file = ResourceLoader.get_asset_path(os.path.join("config", "language.json"))
        with open(language_file, 'r', encoding='utf-8') as f:
            languages = json.load(f)
        cls.current_lang = languages.get(lang, languages["English"])
        cls.current_lang_name = lang  # 记录当前语言名称
        return cls.current_lang

    @classmethod
    def get_current_lang(cls):
        """获取当前语言配置"""
        if cls.current_lang is None:
            cls.load_language()
        return cls.current_lang

    @classmethod
    def init_global_config(cls):
        """初始化全局配置，从文件加载已保存的设置"""
        if not cls.base_dir:
            cls.initialize_path()
        
        config_file = os.path.join(cls.base_dir, 'config', 'global_config.json')
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    saved_config = json.load(f)
                
                # 加载UI配置
                ui_config = saved_config.get('ui', {})
                for param_name, value in ui_config.items():
                    if hasattr(cls, param_name):
                        setattr(cls, param_name, value)
                
                # 如果保存了语言设置，重新加载该语言
                if 'language' in ui_config:
                    cls.load_language(ui_config['language'])
                
                # 加载音频配置
                audio_config = saved_config.get('audio', {})
                for param_name, value in audio_config.items():
                    if hasattr(cls, param_name):
                        setattr(cls, param_name, value)
                
                # 加载轨迹优化器配置
                trajectory_config = saved_config.get('trajectory', {})
                for param_name, value in trajectory_config.items():
                    if hasattr(cls, param_name):
                        setattr(cls, param_name, value)
                        
                # 加载插值配置
                interpolation_config = saved_config.get('interpolation', {})
                for param_name, value in interpolation_config.items():
                    if hasattr(cls, param_name):
                        setattr(cls, param_name, value)
                        
                # 加载协议配置
                protocol_config = saved_config.get('protocol', {})
                for param_name, value in protocol_config.items():
                    if hasattr(cls, param_name):
                        setattr(cls, param_name, value)
                        
                # 同步协议类配置
                cls._sync_protocol_classes()
                        
            except Exception as e:
                print(f"Error loading global config: {e}")

    @classmethod
    def _sync_protocol_classes(cls):
        """同步协议类的配置值"""
        try:
            # 导入协议类并同步配置值
            from protocol.serial_protocol import SerialProtocol
            from protocol.can_protocol import CanProtocol
            
            SerialProtocol.SERIAL_BAUDRATE = cls.serial_baudrate
            CanProtocol.bitrate = cls.can_bitrate
        except ImportError:
            # 如果协议类尚未加载，忽略错误
            pass

    @classmethod
    def save_global_config(cls):
        """保存全局配置到文件"""
        if not cls.base_dir:
            cls.initialize_path()
        
        config_dir = os.path.join(cls.base_dir, 'config')
        if not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)
        
        config_file = os.path.join(config_dir, 'global_config.json')
        
        # 构建配置数据
        config_data = {
            'ui': {
                'position_steps': cls.position_steps,
                'orientation_steps': cls.orientation_steps,
                'rcl_preview_point_radius': cls.rcl_preview_point_radius,
                'rcl_preview_axis_length': cls.rcl_preview_axis_length,
                'language': cls.current_lang_name
            },
            'audio': {
                'last_audio_device': cls.last_audio_device
            },
            'trajectory': {
                'dt': cls.dt,
                'trajectory_method': cls.trajectory_method,
                'joint_speeds': cls.joint_speeds,
                'joint_accelerations': cls.joint_accelerations,
                'joint_jerks': cls.joint_jerks
            },
            'interpolation': {
                'interpolation_method': cls.interpolation_method
            },
            'protocol': {
                'serial_baudrate': cls.serial_baudrate,
                'can_bitrate': cls.can_bitrate
            }
        }
        
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving global config: {e}")
            return False

    @classmethod
    def set_audio_device(cls, device_name):
        """设置音频设备并保存配置"""
        cls.last_audio_device = device_name
        cls.save_global_config()

    @classmethod
    def get_audio_device(cls):
        """获取当前音频设备设置"""
        return cls.last_audio_device
    
    @classmethod
    def init_joint_params(cls, num_joints):
        """初始化关节级别的参数"""
        if len(cls.joint_speeds) != num_joints:
            cls.joint_speeds = [100] * num_joints  # 默认100%
        if len(cls.joint_accelerations) != num_joints:
            cls.joint_accelerations = [100] * num_joints  # 默认100%
        if len(cls.joint_jerks) != num_joints:
            cls.joint_jerks = [100] * num_joints  # 默认100%
    
    @classmethod
    def set_joint_speed(cls, joint_index, speed_value):
        """设置指定关节的速度"""
        if joint_index < len(cls.joint_speeds):
            cls.joint_speeds[joint_index] = speed_value
    
    @classmethod
    def set_joint_acceleration(cls, joint_index, acc_value):
        """设置指定关节的加速度"""
        if joint_index < len(cls.joint_accelerations):
            cls.joint_accelerations[joint_index] = acc_value
    
    @classmethod
    def set_joint_jerk(cls, joint_index, jerk_value):
        """设置指定关节的急动度"""
        if joint_index < len(cls.joint_jerks):
            cls.joint_jerks[joint_index] = jerk_value

# init language and system path
Config.load_language()
Config.initialize_path()
Config.init_global_config()
