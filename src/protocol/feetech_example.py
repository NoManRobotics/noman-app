#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Feetech协议使用示例
演示如何使用FeetechProtocol类控制Feetech舵机
"""

from feetech_protocol import FeetechProtocol, FeetechCommands
import time

def main():
    """主函数 - 演示Feetech协议的基本使用"""
    
    # 1. 连接到串口
    port = "COM3"  # Windows示例，Linux使用如"/dev/ttyUSB0"
    baudrate = 1000000  # 1Mbps，Feetech舵机的常用波特率
    
    print(f"正在连接到 {port}，波特率：{baudrate}")
    if not FeetechProtocol.connect(port, baudrate):
        print("连接失败！请检查串口设置。")
        return
    
    print("连接成功！")
    
    try:
        # 2. 扫描舵机
        print("\n=== 扫描舵机 ===")
        servo_ids = []
        for servo_id in range(1, 11):  # 扫描ID 1-10
            if FeetechProtocol.ping(servo_id):
                print(f"发现舵机 ID: {servo_id}")
                servo_ids.append(servo_id)
        
        if not servo_ids:
            print("未发现任何舵机！")
            return
        
        # 使用第一个发现的舵机进行演示
        demo_servo_id = servo_ids[0]
        print(f"\n使用舵机 ID {demo_servo_id} 进行演示")
        
        # 3. 获取舵机状态
        print("\n=== 获取舵机状态 ===")
        status = FeetechProtocol.get_status(demo_servo_id)
        print(f"舵机状态：")
        print(f"  连接状态: {status['connected']}")
        print(f"  当前位置: {status['position']}")
        print(f"  当前速度: {status['speed']}")
        print(f"  负载: {status['load']}")
        print(f"  电压: {status['voltage']}V")
        print(f"  温度: {status['temperature']}°C")
        
        # 4. 使能扭矩
        print("\n=== 使能扭矩 ===")
        if FeetechProtocol.set_torque_enable(demo_servo_id, True):
            print("扭矩使能成功")
        else:
            print("扭矩使能失败")
        
        # 5. 位置控制演示
        print("\n=== 位置控制演示 ===")
        positions = [512, 300, 724, 512]  # 中间位置，左侧，右侧，回到中间
        speed = 200  # 移动速度
        
        for i, position in enumerate(positions):
            print(f"移动到位置 {position}...")
            if FeetechProtocol.set_position(demo_servo_id, position, speed):
                time.sleep(2)  # 等待移动完成
                
                # 读取当前位置确认
                current_pos, success = FeetechProtocol.get_position(demo_servo_id)
                if success:
                    print(f"  当前位置: {current_pos}")
                else:
                    print("  位置读取失败")
            else:
                print(f"  位置设置失败")
        
        # 6. 使用execute_command方法演示
        print("\n=== 使用execute_command方法 ===")
        
        # 获取位置
        result = FeetechProtocol.execute_command(FeetechCommands.GET_POSITION, demo_servo_id)
        if result:
            position, success = result
            if success:
                print(f"当前位置（通过execute_command）: {position}")
        
        # 设置新位置
        result = FeetechProtocol.execute_command(FeetechCommands.SET_POSITION, demo_servo_id, 600, 150)
        if result:
            print("位置设置成功（通过execute_command）")
            time.sleep(2)
        
        # 获取状态
        status = FeetechProtocol.execute_command(FeetechCommands.GET_STATUS, demo_servo_id)
        if status:
            print(f"舵机状态（通过execute_command）: 位置={status['position']}, 温度={status['temperature']}°C")
        
        # 7. 禁用扭矩
        print("\n=== 禁用扭矩 ===")
        if FeetechProtocol.set_torque_enable(demo_servo_id, False):
            print("扭矩禁用成功")
        else:
            print("扭矩禁用失败")
            
    except Exception as e:
        print(f"执行过程中出现错误: {e}")
        
    finally:
        # 8. 断开连接
        print("\n=== 断开连接 ===")
        if FeetechProtocol.disconnect():
            print("断开连接成功")
        else:
            print("断开连接失败")

def test_multiple_servos():
    """测试多舵机控制"""
    print("\n" + "="*50)
    print("多舵机控制测试")
    print("="*50)
    
    port = "COM3"
    if not FeetechProtocol.connect(port, 1000000):
        print("连接失败！")
        return
    
    try:
        # 扫描所有舵机
        servo_ids = []
        for servo_id in range(1, 255):
            if FeetechProtocol.ping(servo_id):
                servo_ids.append(servo_id)
        
        print(f"发现 {len(servo_ids)} 个舵机: {servo_ids}")
        
        if len(servo_ids) >= 2:
            # 同时控制多个舵机
            print("同时使能所有舵机扭矩...")
            for servo_id in servo_ids:
                FeetechProtocol.set_torque_enable(servo_id, True)
            
            print("同时移动所有舵机...")
            for servo_id in servo_ids:
                position = 512 + (servo_id - servo_ids[0]) * 100  # 不同舵机不同位置
                FeetechProtocol.set_position(servo_id, position, 200)
            
            time.sleep(3)
            
            # 检查位置
            print("检查各舵机位置:")
            for servo_id in servo_ids:
                position, success = FeetechProtocol.get_position(servo_id)
                if success:
                    print(f"  舵机 {servo_id}: 位置 {position}")
            
            # 禁用所有扭矩
            print("禁用所有舵机扭矩...")
            for servo_id in servo_ids:
                FeetechProtocol.set_torque_enable(servo_id, False)
        
    finally:
        FeetechProtocol.disconnect()

if __name__ == "__main__":
    # 运行基本演示
    main()
    
    # 运行多舵机测试（可选）
    # test_multiple_servos()
