import cv2
import numpy as np

def hex_to_rgb(hex_color):
    """Convert hex color code to RGB values (0-1 range)"""
    r = int(hex_color[1:3], 16) / 255.0
    g = int(hex_color[3:5], 16) / 255.0
    b = int(hex_color[5:7], 16) / 255.0
    return (r, g, b)

def rgba_to_hex(rgba):
    # 将0-1范围的值转换为0-255范围
    r = int(rgba[0] * 255)
    g = int(rgba[1] * 255)
    b = int(rgba[2] * 255)
    # 转换为十六进制并确保每个颜色分量都是两位数
    return f"#{r:02x}{g:02x}{b:02x}"

def rgb_to_hsv(rgb):
    """将RGB转换为OpenCV HSV格式"""
    # 使用OpenCV进行转换，直接使用RGB值（0-255范围）
    rgb_array = np.uint8([[[rgb[2], rgb[1], rgb[0]]]])  # BGR格式
    hsv_array = cv2.cvtColor(rgb_array, cv2.COLOR_BGR2HSV)
    
    return hsv_array[0][0]

def hsv_to_rgb(hsv):
    """将OpenCV HSV格式转换为RGB"""
    # 创建HSV数组
    hsv_array = np.uint8([[[hsv[0], hsv[1], hsv[2]]]])
    
    # 使用OpenCV进行转换
    bgr_array = cv2.cvtColor(hsv_array, cv2.COLOR_HSV2BGR)
    bgr = bgr_array[0][0]
    
    # 转换为RGB格式
    return [bgr[2], bgr[1], bgr[0]]