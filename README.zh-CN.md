# Noman-app

<div align="right">

[English](README.md) | [中文](README.zh-CN.md)

</div>

Noman-app是一个轻量级、跨平台的机械臂用户界面，使用Python实现。它提供了路径规划、碰撞避免和自动化的解决方案，是MoveIt和Pinocchio等工具的替代选择。后端结合了路径规划和自动化功能，如PTP、LIN和CIRC运动，这些通常在KRL和RoboDK等工业级应用中看到。

它连接到真实机械臂进行仿真。路线图如下：

--> 带舵机的机械臂（UART），提供位置反馈
----> 带步进电机的机械臂（CAN、UART），提供位置和速度控制
-------> 支持扭矩控制的电机机械臂

**注意** 这是我们的第一个版本，仍在开发中。

**安装**

对于喜欢在本地环境使用终端的用户：

```
pip install -r requirements.txt
pip install [WHEEL-NAME] # 您需要从发布页面下载.whl文件
python src/main.py
```

对于喜欢按操作系统下载应用程序的用户，请从最新发布页面下载可执行文件。

**Linux用户**需要取消网络代理设置以避免openai方案问题：

```
unset all_proxy; unset ALL_PROXY
``` 

**主要功能**

• **机器人配置**: 上传URDF/Xacro文件，配置关节限制、初始位置和工具中心点偏移，兼容第三方机械臂

• **通信协议**: 开源协议接口，支持UART、CAN、TCP/IP等多种通信方式

• **ROS支持**: 提供URDF文件下载，支持ROS1/ROS2环境配置和MoveIt集成，推荐使用ROS1 Noetic

• **运动学**: noman-app后端：
  - **运动规划器**: RRT*、CHOMP算法，支持求解器（阻尼最小二乘法、Levenberg-Marquardt、IK track）
  - **碰撞模块**: 自碰撞和环境碰撞检测
  - **工作空间分析**: 可达工作空间计算和关节限制验证

• **视觉**: 相机内参标定、手眼变换矩阵、物体识别、颜色检测和自动抓取操作，提供实时视觉反馈

• **机器人编程语言**: 执行G代码命令（PTP、LIN、CIRC、HOME、DELAY、TOOL、M280），示教编程和text2gcode绘图任务

• **轨迹优化器**: 高级轨迹优化方法包括：
  - **笛卡尔空间**: 线性插值、三次B样条和混合优化
  - **关节空间**: 梯形和S曲线多项式优化

• **固件管理**: 支持ESP32/Arduino固件自动更新和自定义固件上传

• **仿真器**: 基于物理的碰撞检测仿真，支持URDF模型和TCP/基座位置配置

• **AI助手 (Majardomo)**: 语音控制、任务分解和知识库问答功能（开发中）

**支持**

我们提供由我们团队设计和验证的官方机器人配置文件，以确保完整的软件兼容性和功能验证。如需全面的技术文档、教程和支持资源，请访问我们的[技术支持页面](https://nomanrobotics.com/techsupport/)。


**TO-DOs**:
Priority 1 Basic Supports

- [x] speed control range to parametric
- [x] add detector types, including template matching, color detector.
- [x] Replay with speed control
- [x] Optimise text2gcode gcode trajectory
- [X] Move sys-path and initialise to config.
- [x] Detect and grab.
- [x] Make command look-up a same class file in controller frame and anytroller from
- [ ] Test the software on Parol6 stepper motors.
- [x] languange support in sub-frames
- [x] MacOS simulator gui fix, shape loading.
- [x] Majordomo only keeps API, remove local models
- [x] tool/base coordinate systems
- [ ] user can add world/tool coordinate systems
- [x] Trajectory Optimiser in joint space and cartesian space.
- [x] setting: individial speed/acc/jerk setting, real-time optimiser method switch.


Priority 2 Advanced features

- [ ] Lookahead algorithm in trajectory optimisation. (multi-joint-positions)
- [ ] Add DH param support.
- [ ] Advanced feature in gcode ui: add point selection to optimise in between.
- [ ] Slider plus/ minus button real time execution on robot arm side.
- [ ] Json trajectory to gcode
- [ ] task sequence decomposer from assembly.
- [ ] Mujoco interface
- [x] add phone as a camera for the robot arm
- [ ] tic tac tok.
- [ ] multi-robot tasking
- [ ] point cloud.
- [ ] Spatial AI


## Credits (Updated by 18/06/2025)

This project uses the following third-party components:

### Python libraries

- xacrodoc
  - Copyright (c) 2023 adamheins
  - Licensed under the [MIT License](https://opensource.org/licenses/MIT)
  - Source: https://github.com/xacrodoc/xacrodoc

- sherpa-ncnn
  - Copyright (c) 2021-2023 naivetoby et al.
  - Licensed under the [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0)
  - Source: https://github.com/k2-fsa/sherpa-ncnn


### Tools

- esptool
  - Copyright (c) 2014-2022 Fredrik Ahlberg, Angus Gratton et al.
  - Licensed under the [GPL-2.0 License](https://www.gnu.org/licenses/old-licenses/gpl-2.0.en.html)
  - Source: https://github.com/espressif/esptool

- avrdude
  - Copyright (c) 2000-2005 Brian S. Dean
  - Licensed under the [GPL-2.0 License](https://www.gnu.org/licenses/old-licenses/gpl-2.0.en.html)
  - Source: https://github.com/avrdudes/avrdude
