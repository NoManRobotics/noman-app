import numpy as np
from mpl_toolkits.mplot3d import art3d
from utils.math import euler_to_rotation_matrix


class Camera3DVisualizer:
    """3D相机可视化器类，用于在3D视图中显示相机位置和视场"""
    
    def __init__(self, ax_3d, canvas):
        """
        初始化3D相机可视化器
        
        Args:
            ax_3d: matplotlib 3D轴对象
            canvas: matplotlib画布对象
        """
        self.ax_3d = ax_3d
        self.canvas = canvas
    
    def visualize_camera_in_3d(self, camera_pos, camera_rot, target_position, base_pos, base_orn, 
                               workspace_bounds=None, show_error_callback=None):
        """在3D视图中可视化相机位置和视场
        
        Args:
            camera_pos_mm: 相机位置 (毫米)
            camera_rot: 相机旋转矩阵 (3x3)
            target_position: 机器人末端位置 (米)
            base_pos: 机器人基座位置 (米)
            base_orn: 机器人基座姿态 (欧拉角)
            workspace_bounds: 工作空间边界字典，可选
            show_error_callback: 错误显示回调函数，可选
        """
        if camera_pos is None or camera_rot is None:
            if show_error_callback:
                show_error_callback("无法计算相机位姿")
            return
            
        try:
            # 清除当前3D视图
            self.ax_3d.clear()
            
            # 设置坐标轴范围
            self._set_axis_limits(workspace_bounds)
            
            # 绘制机器人基座
            self._draw_robot_base(base_pos, base_orn)
            
            # 绘制机器人末端
            self._draw_robot_end_effector(target_position)
            
            # 绘制相机位置和坐标系
            self._draw_camera(camera_pos, camera_rot)
            
            # 绘制视场范围 (FOV, Field of View)
            self._draw_camera_fov(camera_pos, camera_rot)
            
            # 设置图例和标签
            self._setup_plot_labels()
            
            # 绘制画布
            self.canvas.draw()
            
        except Exception as e:
            if show_error_callback:
                show_error_callback(f"可视化相机失败: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def _set_axis_limits(self, workspace_bounds=None):
        """设置3D坐标轴范围
        
        Args:
            workspace_bounds: 工作空间边界字典，格式为 {'x': {'min': ..., 'max': ...}, ...}
        """
        if workspace_bounds:
            self.ax_3d.set_xlim(workspace_bounds['x']['min'], workspace_bounds['x']['max'])
            self.ax_3d.set_ylim(workspace_bounds['y']['min'], workspace_bounds['y']['max'])
            self.ax_3d.set_zlim(workspace_bounds['z']['min'], workspace_bounds['z']['max'])
        else:
            # 如果工作空间边界未分析，设置默认范围
            self.ax_3d.set_xlim(-0.3, 0.3)
            self.ax_3d.set_ylim(-0.3, 0.3)
            self.ax_3d.set_zlim(0, 0.3)
    
    def _draw_robot_base(self, base_pos, base_orn):
        """绘制机器人基座"""
        # 绘制机器人基座位置
        self.ax_3d.scatter(
            base_pos[0], 
            base_pos[1],
            base_pos[2], 
            c='g', marker='s', s=50, label='Base'
        )
        
        # 将欧拉角转换为旋转矩阵
        rot_matrix = euler_to_rotation_matrix(base_orn[0], base_orn[1], base_orn[2])
        
        # 设置箭头长度
        arrow_length = 0.05
        
        # 绘制基座坐标系
        self.ax_3d.quiver(
            base_pos[0], base_pos[1], base_pos[2],
            rot_matrix[0, 0], rot_matrix[1, 0], rot_matrix[2, 0],
            color='r', length=arrow_length, normalize=True
        )
        
        self.ax_3d.quiver(
            base_pos[0], base_pos[1], base_pos[2],
            rot_matrix[0, 1], rot_matrix[1, 1], rot_matrix[2, 1],
            color='g', length=arrow_length, normalize=True
        )
        
        self.ax_3d.quiver(
            base_pos[0], base_pos[1], base_pos[2],
            rot_matrix[0, 2], rot_matrix[1, 2], rot_matrix[2, 2],
            color='b', length=arrow_length, normalize=True
        )
    
    def _draw_robot_end_effector(self, target_position):
        """绘制机器人末端执行器"""
        self.ax_3d.scatter(
            target_position[0], 
            target_position[1],
            target_position[2], 
            c='b', marker='o', s=50, label='End Effector'
        )
    
    def _draw_camera(self, camera_pos, camera_rot):
        """绘制相机位置和坐标系"""
        # 绘制相机位置
        self.ax_3d.scatter(
            camera_pos[0], 
            camera_pos[1],
            camera_pos[2], 
            c='r', marker='^', s=100, label='Camera'
        )
        
        # 设置箭头长度
        arrow_length = 0.05
        
        # 绘制相机坐标系（Z轴为光轴方向）
        self.ax_3d.quiver(
            camera_pos[0], camera_pos[1], camera_pos[2],
            camera_rot[0, 0], camera_rot[1, 0], camera_rot[2, 0],
            color='r', length=arrow_length, normalize=True
        )
        
        self.ax_3d.quiver(
            camera_pos[0], camera_pos[1], camera_pos[2],
            camera_rot[0, 1], camera_rot[1, 1], camera_rot[2, 1],
            color='g', length=arrow_length, normalize=True
        )
        
        self.ax_3d.quiver(
            camera_pos[0], camera_pos[1], camera_pos[2],
            camera_rot[0, 2], camera_rot[1, 2], camera_rot[2, 2],
            color='b', length=arrow_length, normalize=True
        )
    
    def _draw_camera_fov(self, camera_pos, camera_rot, fov_h=60, fov_v=45):
        """绘制相机视场范围 - 四条射线指向地面
        
        Args:
            camera_pos: 相机在世界坐标系中的位置 [x, y, z]
            camera_rot: 相机旋转矩阵 (3x3)
            fov_h: 水平视场角度 (度)
            fov_v: 垂直视场角度 (度)
        """
        # 将角度转换为弧度
        fov_h_rad = np.radians(fov_h)
        fov_v_rad = np.radians(fov_v)
        
        # 计算视场的四个角方向在相机坐标系中的单位向量
        half_w = np.tan(fov_h_rad / 2)
        half_h = np.tan(fov_v_rad / 2)
        
        # 四个角的方向向量（在相机坐标系中，Z轴指向前方）
        camera_directions = np.array([
            [half_w, half_h, 1],   # 右上
            [-half_w, half_h, 1],  # 左上
            [-half_w, -half_h, 1], # 左下
            [half_w, -half_h, 1],  # 右下
        ])
        
        # 归一化方向向量
        for i in range(len(camera_directions)):
            camera_directions[i] = camera_directions[i] / np.linalg.norm(camera_directions[i])
        
        # 将方向向量从相机坐标系变换到世界坐标系
        world_directions = []
        for direction in camera_directions:
            world_direction = camera_rot @ direction
            world_directions.append(world_direction)
        
        # 计算射线与地面（z=0）的交点
        ground_points = []
        for direction in world_directions:
            # 射线方程: point = camera_pos + t * direction
            # 与地面z=0的交点: camera_pos[2] + t * direction[2] = 0
            if abs(direction[2]) > 1e-6:  # 避免除零
                t = -camera_pos[2] / direction[2]
                if t > 0:  # 只考虑向前的射线
                    intersection = camera_pos + t * direction
                    ground_points.append(intersection)
                else:
                    # 如果射线不向下，就延伸一个较远的距离
                    intersection = camera_pos + 2.0 * direction
                    ground_points.append(intersection)
            else:
                # 如果射线平行于地面，就延伸一个较远的距离
                intersection = camera_pos + 2.0 * direction
                ground_points.append(intersection)
        
        # 绘制四条射线
        for ground_point in ground_points:
            self.ax_3d.plot3D(
                [camera_pos[0], ground_point[0]],
                [camera_pos[1], ground_point[1]],
                [camera_pos[2], ground_point[2]],
                'y--', alpha=0.7, linewidth=1.5
            )
    
    def _setup_plot_labels(self):
        """设置图例和标签"""
        self.ax_3d.set_xlabel('X (m)')
        self.ax_3d.set_ylabel('Y (m)')
        self.ax_3d.set_zlabel('Z (m)')
        self.ax_3d.legend()
    
    def init_3d_viewer(self, base_pos, base_orn, workspace_bounds=None):
        """初始化3D视图显示
        
        Args:
            base_pos: 机器人基座位置 (米)
            base_orn: 机器人基座姿态 (欧拉角)
            workspace_bounds: 工作空间边界字典，可选
        """
        # 设置3D图的初始视图
        self.ax_3d.view_init(30, -60)  # 默认等轴测视图
        
        # 设置坐标轴标签
        self.ax_3d.set_xlabel('X (m)')
        self.ax_3d.set_ylabel('Y (m)')
        self.ax_3d.set_zlabel('Z (m)')

        # 设置坐标轴范围
        self._set_axis_limits(workspace_bounds)
        
        # 绘制机器人基座
        self._draw_robot_base(base_pos, base_orn)
        
        # 绘制画布
        self.canvas.draw() 
