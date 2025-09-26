import numpy as np

def euclidean_distance(pos1: np.ndarray, pos2: np.ndarray) -> float:
    """计算两点间的欧几里得距离"""
    return np.linalg.norm(pos1 - pos2)

def sigmoid(x, a=0.1, b=0.0005):
    return a / (1 + np.exp(-b * (x - 50)))

def rpy_to_quaternion(roll, pitch, yaw):
    """将RPY转换为四元数
        
    Args:
        roll: 绕X轴旋转角度
        pitch: 绕Y轴旋转角度
        yaw: 绕Z轴旋转角度
        
    Returns:
        numpy.ndarray: 四元数 [x, y, z, w]
    """
    
    # 计算各个角度的正弦和余弦值
    cy = np.cos(yaw * 0.5)
    sy = np.sin(yaw * 0.5)
    cp = np.cos(pitch * 0.5)
    sp = np.sin(pitch * 0.5)
    cr = np.cos(roll * 0.5)
    sr = np.sin(roll * 0.5)
    
    # 计算四元数
    w = cr * cp * cy + sr * sp * sy
    x = sr * cp * cy - cr * sp * sy
    y = cr * sp * cy + sr * cp * sy
    z = cr * cp * sy - sr * sp * cy
    
    return np.array([x, y, z, w])

def rotation_to_euler_angles(R):
    """将旋转矩阵转换为欧拉角（X-Y-Z顺序，也称为RPY）
    
    Args:
        R: 3x3旋转矩阵
        
    Returns:
        [x, y, z]: 欧拉角（弧度）
    """
    # 检查是否存在万向节锁（Gimbal Lock）
    sy = np.sqrt(R[0, 0] * R[0, 0] + R[1, 0] * R[1, 0])
    
    if sy > 1e-6:  # 非奇异情况
        x = np.arctan2(R[2, 1], R[2, 2])
        y = np.arctan2(-R[2, 0], sy)
        z = np.arctan2(R[1, 0], R[0, 0])
    else:  # 奇异情况
        x = np.arctan2(-R[1, 2], R[1, 1])
        y = np.arctan2(-R[2, 0], sy)
        z = 0
        
    return [x, y, z]
    
def euler_to_rotation_matrix(roll, pitch, yaw):
    """将欧拉角（弧度）转换为旋转矩阵
    
    Args:
        roll: 绕X轴旋转角度
        pitch: 绕Y轴旋转角度
        yaw: 绕Z轴旋转角度
        
    Returns:
        numpy.ndarray: 3x3旋转矩阵
    """
    # 计算各个角度的正弦和余弦值
    cr = np.cos(roll)
    sr = np.sin(roll)
    cp = np.cos(pitch)
    sp = np.sin(pitch)
    cy = np.cos(yaw)
    sy = np.sin(yaw)
    
    # 构建旋转矩阵 (ZYX顺序，先yaw，再pitch，最后roll)
    # R = Rz(yaw) * Ry(pitch) * Rx(roll)
    R = np.array([
        [cy*cp, cy*sp*sr - sy*cr, cy*sp*cr + sy*sr],
        [sy*cp, sy*sp*sr + cy*cr, sy*sp*cr - cy*sr],
        [-sp, cp*sr, cp*cr]
    ])
    
    return R
    
def quaternion_to_rpy(quaternion):
    """将四元数转换为欧拉角（弧度）
    
    Args:
        quaternion: 四元数 [x, y, z, w]
        
    Returns:
        numpy.ndarray: 欧拉角 [roll, pitch, yaw]（弧度）
    """
    x, y, z, w = quaternion
    
    # 计算欧拉角（弧度）
    # roll (x-axis rotation)
    sinr_cosp = 2 * (w * x + y * z)
    cosr_cosp = 1 - 2 * (x * x + y * y)
    roll = np.arctan2(sinr_cosp, cosr_cosp)
    
    # pitch (y-axis rotation)
    sinp = 2 * (w * y - z * x)
    if abs(sinp) >= 1:
        pitch = np.copysign(np.pi / 2, sinp)  # 使用90度，如果sinp超出范围
    else:
        pitch = np.arcsin(sinp)
    
    # yaw (z-axis rotation)
    siny_cosp = 2 * (w * z + x * y)
    cosy_cosp = 1 - 2 * (y * y + z * z)
    yaw = np.arctan2(siny_cosp, cosy_cosp)
    
    return np.array([roll, pitch, yaw])

def slerp(q1, q2, t):
    """四元数球面线性插值(SLERP)
    
    Args:
        q1: 起始四元数 [x,y,z,w]
        q2: 结束四元数 [x,y,z,w]
        t: 插值参数 (0.0 到 1.0)
        
    Returns:
        插值后的四元数
    """
    # 确保四元数是单位四元数
    q1 = q1 / np.linalg.norm(q1)
    q2 = q2 / np.linalg.norm(q2)
    
    # 计算四元数的点积
    dot = np.sum(q1 * q2)
    
    # 如果点积为负，取q2的反方向，以确保取最短路径
    if dot < 0.0:
        q2 = -q2
        dot = -dot
    
    # 设置阈值，当四元数接近平行时使用线性插值
    DOT_THRESHOLD = 0.9995
    if dot > DOT_THRESHOLD:
        # 线性插值
        result = q1 + t * (q2 - q1)
        return result / np.linalg.norm(result)
    
    # 计算插值角度
    theta_0 = np.arccos(dot)
    theta = theta_0 * t
    
    # 计算插值四元数
    sin_theta = np.sin(theta)
    sin_theta_0 = np.sin(theta_0)
    
    s0 = np.cos(theta) - dot * sin_theta / sin_theta_0
    s1 = sin_theta / sin_theta_0
    
    return s0 * q1 + s1 * q2
    
def slerp_scipy(q1, q2, t):
    from scipy.spatial.transform import Rotation as R
    
    """使用SciPy实现的四元数球面线性插值(SLERP)"""
    r1 = R.from_quat(q1)
    r2 = R.from_quat(q2)
    r_interp = R.slerp(r1, r2, [t])[0]
    return r_interp.as_quat()

def multiply_quaternions(q1, q2):
    """合成两个四元数（相当于两个旋转的串联）
    
    这相当于四元数的"加法"操作，实际上是两个旋转变换的组合
    q1 * q2 表示先应用q2旋转，再应用q1旋转
    
    Args:
        q1: 第一个四元数 [x, y, z, w]
        q2: 第二个四元数 [x, y, z, w]
        
    Returns:
        numpy.ndarray: 合成后的四元数 [x, y, z, w]
    """
    x1, y1, z1, w1 = q1
    x2, y2, z2, w2 = q2
    
    w = w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2
    x = w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2
    y = w1 * y2 + y1 * w2 + z1 * x2 - x1 * z2
    z = w1 * z2 + z1 * w2 + x1 * y2 - y1 * x2
    
    return np.array([x, y, z, w])

def inverse_multiply_quaternions(q1, q2):
    """从合成四元数q1中"减去"四元数q2
    
    这相当于四元数的"减法"操作，实际上是用q1四元数乘以q2的逆
    q_result = q1 * q2^(-1) 表示从q1变换中移除q2变换
    
    Args:
        q1: 合成后的四元数 [x, y, z, w]
        q2: 要"减去"的四元数 [x, y, z, w]
        
    Returns:
        numpy.ndarray: 结果四元数 [x, y, z, w]
    """
    # 计算q2的逆（共轭除以模长平方，但对单位四元数共轭即为逆）
    q2_inv = np.array([-q2[0], -q2[1], -q2[2], q2[3]])
    
    # 归一化确保是单位四元数
    q2_inv = q2_inv / np.linalg.norm(q2_inv)
    
    # 合成q1和q2的逆
    return multiply_quaternions(q1, q2_inv)

def atan2p(y, x):
    """计算正角度的atan2函数
    
    Args:
        y: y坐标
        x: x坐标
        
    Returns:
        float: 角度值，范围[0, 2π)
    """
    angle = np.arctan2(y, x)
    return angle + 2 * np.pi if angle < 0 else angle

def bezier_point(control_points, t):
    """计算贝塞尔曲线上的一个点
    
    Args:
        control_points: 控制点列表，每个点可以是任意维度的numpy数组
        t: 参数值，范围[0,1]
        
    Returns:
        numpy.ndarray: 贝塞尔曲线上对应参数t的点
    """
    n = len(control_points) - 1  # 控制点数量减1为阶数
    
    # 使用De Casteljau算法计算贝塞尔曲线点
    points = np.copy(control_points)
    for r in range(1, n + 1):
        for i in range(n - r + 1):
            points[i] = (1 - t) * points[i] + t * points[i + 1]
    
    return points[0]

def bezier_curve(control_points, num_points=100):
    """生成贝塞尔曲线
    
    Args:
        control_points: 控制点列表，每个点可以是任意维度的numpy数组
        num_points: 曲线上采样的点数量
        
    Returns:
        numpy.ndarray: 贝塞尔曲线上的点序列，形状为(num_points, dim)
    """
    if len(control_points) < 2:
        raise ValueError("至少需要两个控制点才能生成贝塞尔曲线")
    
    # 转换控制点为numpy数组
    points = np.array(control_points)
    
    # 创建参数t的均匀采样
    t_values = np.linspace(0, 1, num_points)
    
    # 计算每个t值对应的贝塞尔曲线点
    curve_points = np.array([bezier_point(points, t) for t in t_values])
    
    return curve_points

def bezier_interpolate(data_points, num_segments=1, smoothness=0.5, num_points=100):
    """使用分段贝塞尔曲线插值给定的数据点
    
    Args:
        data_points: 要插值的数据点列表
        num_segments: 分段数量(默认为1，即单个贝塞尔曲线)
        smoothness: 控制曲线平滑度的参数，范围[0,1]，0表示折线，1表示最平滑
        num_points: 每段曲线上的采样点数量
        
    Returns:
        numpy.ndarray: 插值后的曲线点
    """
    if len(data_points) < 2:
        raise ValueError("至少需要两个数据点才能进行插值")
    
    # 转换数据点为numpy数组
    points = np.array(data_points)
    
    if num_segments == 1:
        # 单段贝塞尔曲线情况
        if len(points) == 2:
            # 两个点的情况：线性插值
            return np.array([points[0] * (1-t) + points[1] * t for t in np.linspace(0, 1, num_points)])
        elif len(points) == 3:
            # 三个点的情况：二次贝塞尔曲线
            return bezier_curve(points, num_points)
        else:
            # 多于三个点：构造控制点进行单段贝塞尔插值
            n = len(points)
            control_points = [points[0]]
            
            # 根据数据点生成中间控制点
            for i in range(1, n-1):
                # 在每个数据点周围添加控制点
                prev_point = points[i-1]
                curr_point = points[i]
                next_point = points[i+1]
                
                # 根据相邻点计算切线方向
                tangent = smoothness * (next_point - prev_point) / 2
                
                # 添加当前点之前的控制点
                control_points.append(curr_point - tangent)
                # 添加当前数据点
                control_points.append(curr_point)
                # 添加当前点之后的控制点
                control_points.append(curr_point + tangent)
            
            control_points.append(points[-1])
            return bezier_curve(control_points, num_points)
    else:
        # 分段贝塞尔曲线
        n = len(points)
        segments = np.linspace(0, n-1, num_segments+1, dtype=int)
        curve_points = []
        
        for i in range(len(segments)-1):
            start_idx = segments[i]
            end_idx = segments[i+1] + 1  # 包含结束点
            segment_points = points[start_idx:end_idx]
            
            # 为每段计算贝塞尔曲线
            segment_curve = bezier_interpolate(segment_points, 1, smoothness, num_points)
            
            # 如果不是第一段，去掉重复的第一个点
            if i > 0:
                segment_curve = segment_curve[1:]
            
            curve_points.extend(segment_curve)
        
        return np.array(curve_points)

if __name__ == "__main__":
    """测试贝塞尔曲线函数的主函数"""
    import matplotlib.pyplot as plt
    
    # 测试2D贝塞尔曲线
    def test_2d_bezier():
        # 创建示例控制点 - 2D，增加更多控制点
        control_points_2d = np.array([
            [0, 0],        # 起点
            [1, 2],        # 控制点
            [2, -1],       # 控制点
            [3, 3],        # 控制点
            [4, 0],        # 控制点
            [5, 1],        # 控制点
            [6, -2],       # 控制点
            [7, 0]         # 终点
        ])
        
        # 生成贝塞尔曲线
        curve_2d = bezier_curve(control_points_2d, num_points=200)  # 增加点数
        
        # 创建图形
        plt.figure(figsize=(12, 6))
        
        # 绘制控制点
        plt.plot(control_points_2d[:, 0], control_points_2d[:, 1], 'o-', color='red', label='Control Points')
        
        # 绘制贝塞尔曲线
        plt.plot(curve_2d[:, 0], curve_2d[:, 1], '-', color='blue', label='Bezier Curve')
        
        plt.title('2D Bezier Curve Example')
        plt.xlabel('X-axis')
        plt.ylabel('Y-axis')
        plt.grid(True)
        plt.legend()
        plt.axis('equal')
        plt.show()
    
    # 测试2D数据点插值
    def test_2d_interpolation():
        # 创建更多示例数据点 - 2D
        data_points_2d = np.array([
            [0, 0],      # 起点
            [1, 2],      # 数据点
            [2, -1],     # 数据点
            [3, 3],      # 数据点
            [4, 0],      # 数据点
            [5, 1],      # 数据点
            [6, -1],     # 数据点
            [7, 2],      # 数据点
            [8, 0]       # 终点
        ])
        
        # 使用不同平滑度进行插值
        smooth_values = [0.0, 0.3, 0.7, 1.0]
        plt.figure(figsize=(12, 8))
        
        # 绘制数据点
        plt.plot(data_points_2d[:, 0], data_points_2d[:, 1], 'o-', color='red', label='Data Points', markersize=8)
        
        # 测试不同平滑度
        for smoothness in smooth_values:
            # 生成插值曲线
            curve = bezier_interpolate(data_points_2d, smoothness=smoothness, num_points=200)  # 增加点数
            
            # 绘制插值曲线
            plt.plot(curve[:, 0], curve[:, 1], '-', label=f'Smoothness = {smoothness}')
        
        plt.title('Bezier Curve Interpolation Example (Different Smoothness)')
        plt.xlabel('X-axis')
        plt.ylabel('Y-axis')
        plt.grid(True)
        plt.legend()
        plt.axis('equal')
        plt.show()
    
    # 测试分段贝塞尔曲线
    def test_segmented_interpolation():
        # 创建具有多个数据点的示例，增加点数
        x = np.linspace(0, 10, 20)  # 增加到20个点
        y = np.sin(x) + 0.3 * np.cos(3 * x) + np.random.normal(0, 0.1, size=len(x))
        data_points = np.column_stack((x, y))
        
        # 测试不同分段数
        segment_values = [1, 2, 4, 8]
        plt.figure(figsize=(12, 8))
        
        # 绘制原始数据点
        plt.plot(data_points[:, 0], data_points[:, 1], 'o', color='red', label='Original Data Points')
        
        # 测试不同分段数
        for segments in segment_values:
            # 生成分段插值曲线
            curve = bezier_interpolate(data_points, num_segments=segments, 
                                       smoothness=0.5, num_points=300)  # 增加点数
            
            # 绘制插值曲线
            plt.plot(curve[:, 0], curve[:, 1], '-', label=f'Segments = {segments}')
        
        plt.title('Segmented Bezier Curve Interpolation Example')
        plt.xlabel('X-axis')
        plt.ylabel('Y-axis')
        plt.grid(True)
        plt.legend()
        plt.show()
    
    # 测试复杂形状的贝塞尔曲线
    def test_complex_shape():
        # 创建一个更复杂的形状 - 心形曲线的控制点
        t = np.linspace(0, 2*np.pi, 30)  # 30个点来定义形状
        x = 16 * np.sin(t)**3
        y = 13 * np.cos(t) - 5 * np.cos(2*t) - 2 * np.cos(3*t) - np.cos(4*t)
        
        # 添加一些随机扰动
        x += np.random.normal(0, 0.5, size=len(t))
        y += np.random.normal(0, 0.5, size=len(t))
        
        data_points = np.column_stack((x, y))
        
        plt.figure(figsize=(12, 10))
        
        # 原始数据点
        plt.plot(data_points[:, 0], data_points[:, 1], 'o', color='red', label='Original Points')
        
        # 使用不同分段数进行贝塞尔插值
        for segments in [1, 5, 10, 15]:
            curve = bezier_interpolate(data_points, num_segments=segments, 
                                      smoothness=0.3, num_points=500)
            plt.plot(curve[:, 0], curve[:, 1], '-', label=f'Segments = {segments}')
        
        plt.title('Complex Shape Bezier Interpolation')
        plt.xlabel('X-axis')
        plt.ylabel('Y-axis')
        plt.grid(True)
        plt.legend()
        plt.axis('equal')
        plt.show()
    
    # 测试3D贝塞尔曲线
    def test_3d_bezier():
        # 创建示例控制点 - 3D，增加更多点
        t = np.linspace(0, 4*np.pi, 12)  # 12个控制点
        control_points_3d = np.column_stack((
            t * np.cos(t) / 4,      # x 坐标
            t * np.sin(t) / 4,      # y 坐标
            t / 4                   # z 坐标，创建螺旋形
        ))
        
        # 生成贝塞尔曲线
        curve_3d = bezier_curve(control_points_3d, num_points=300)  # 增加点数
        
        # 创建3D图形
        fig = plt.figure(figsize=(10, 8))
        ax = fig.add_subplot(111, projection='3d')
        
        # 绘制控制点
        ax.plot(control_points_3d[:, 0], control_points_3d[:, 1], control_points_3d[:, 2], 
                'o-', color='red', label='Control Points')
        
        # 绘制贝塞尔曲线
        ax.plot(curve_3d[:, 0], curve_3d[:, 1], curve_3d[:, 2], 
                '-', color='blue', label='Bezier Curve')
        
        ax.set_title('3D Bezier Curve Example')
        ax.set_xlabel('X-axis')
        ax.set_ylabel('Y-axis')
        ax.set_zlabel('Z-axis')
        ax.legend()
        plt.show()
    
    # 运行所有测试
    print("Starting Bezier curve function tests...")
    test_2d_bezier()
    test_2d_interpolation()
    test_segmented_interpolation()
    test_complex_shape()  # 新增的复杂形状测试
    test_3d_bezier()
    print("Testing completed.")