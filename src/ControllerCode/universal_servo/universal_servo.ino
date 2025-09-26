#include <Servo.h>

// version check
#define FIRMWARE_VERSION "2.0.0"

// define servo number and pins
const int numServos = {{NUM_SERVOS}}; 
const int mtrPins[numServos] = {{{JOINT_PINS}}}; 
const int gripperPin = {{GRIPPER_PIN}};  // pin number for gripper servo
const float jointLimits[numServos][2] = {
{{JOINT_LIMITS_ARRAY}}
};
const int jointHomePositions[numServos] = { {{JOINT_HOME_POSITIONS}} };  // 每个关节的初始位置

// create servo objects
Servo servos[numServos];
Servo gripperServo;  // 夹爪舵机

// trackers
bool isExecute = false; 
bool isRecordingOnceJoints = false;
bool isRecordingOnceTool = false;
bool isRecording = false;
bool isMicroStep = false;
bool isMoveTool = false;

// joint var
float targetAngles[numServos];
float currentAngles[numServos];  
float tmpAngles[numServos];

// tool var
int targetToolState = 0;
int tmpToolState = 0;
int currentToolState = 90;  // 简单的工具状态，默认夹爪90度

int time_delay = 0;
int time_elapse = 0;

// 添加新的速度控制变量
float jointSpeedFactors[numServos]; // 每个关节独立的速度系数，将在setup()中初始化为1.0
const unsigned long BASE_MOTION_DURATION = 1500;

// motion state of joint
struct MotionState {
    float startPos;
    float targetPos;
    unsigned long startTime;
    unsigned long duration;
    bool isMoving;
};
MotionState jointStates[numServos];

// 全局运动管理
struct GlobalMotionState {
    bool isNewMotion;           // 是否是新的运动命令
    unsigned long globalDuration;   // 全局统一运动时间
    int activeJoints;          // 活动关节数量
    bool syncMode;             // 同步模式（true=同步，false=独立）
} globalMotion;

const float MIN_STEP = 1.5f;     // minimum step degree

/* ------------------------------------------------------------------------------ Helper Functions */

// 将输入角度映射到舵机实际角度范围
float mapAngle(float angle, int servoIndex) {
  // 确保角度在该舵机的有效范围内
  return constrain(angle, jointLimits[servoIndex][0], jointLimits[servoIndex][1]);
}

void setServoPosition(int servoIndex, float position) {
  float mappedAngle = mapAngle(position, servoIndex);
  servos[servoIndex].write((int)mappedAngle);
}

void setGripperPosition(float position) {
  float mappedAngle = constrain(position, 90.0f, 180.0f);
  gripperServo.write((int)mappedAngle);
}

// 修改 smoothInterpolation 函数，使用 sin² 插值
float smoothInterpolation(float start, float target, float progress) {
    if (progress <= 0.0f) return start;
    if (progress >= 1.0f) return target;
    
    // use sin²(t) interpolation
    float smoothProgress = sin(progress * PI / 2.0f);
    smoothProgress = smoothProgress * smoothProgress;
    
    // calculate angle difference (considering shortest path)
    float angleDiff = target - start;
    while (angleDiff > 180) angleDiff -= 360;
    while (angleDiff < -180) angleDiff += 360;
    
    return start + angleDiff * smoothProgress;
}

unsigned long calculateMotionDuration(float angleChange, int jointId) {
    float absChange = abs(angleChange);
    // 根据角度变化计算基础时间，然后应用该关节的速度系数
    unsigned long duration = (unsigned long)(BASE_MOTION_DURATION * (absChange / 90.0f));
    if (jointId >= 0 && jointId < numServos) {
        return (unsigned long)(duration / jointSpeedFactors[jointId]);
    }
    return duration;
}

// 计算所有活动关节的最大运动时间
unsigned long calculateGlobalMotionDuration(float targetAngles[], float currentAngles[]) {
    unsigned long maxDuration = 0;
    int activeCount = 0;
    
    for (int i = 0; i < numServos; i++) {
        float angleChange = abs(targetAngles[i] - currentAngles[i]);
        if (angleChange >= MIN_STEP) {
            activeCount++;
            unsigned long duration = (unsigned long)(BASE_MOTION_DURATION * (angleChange / 90.0f));
            duration = (unsigned long)(duration / jointSpeedFactors[i]);
            if (duration > maxDuration) {
                maxDuration = duration;
            }
        }
    }
    
    globalMotion.activeJoints = activeCount;
    globalMotion.syncMode = (activeCount > 1); // 多关节同步，单关节独立
    
    return maxDuration;
}

float moveMotor(float targetDegree, float curDegree, int id, bool fake) {
    if(id >= 0 && id < numServos) {
        
        if(abs(targetDegree - curDegree) < MIN_STEP) {
            if (!fake) {
                setServoPosition(id, targetDegree);
            }
            jointStates[id].isMoving = false;
            return targetDegree;
        }
        
        if(!jointStates[id].isMoving) {
            jointStates[id].startPos = curDegree;
            jointStates[id].targetPos = targetDegree;
            jointStates[id].startTime = millis();
            
            // 使用全局统一时间或独立时间
            if (globalMotion.syncMode && globalMotion.globalDuration > 0) {
                jointStates[id].duration = globalMotion.globalDuration;
            } else {
                float angleChange = abs(targetDegree - curDegree);
                jointStates[id].duration = (unsigned long)(BASE_MOTION_DURATION * (angleChange / 90.0f) / jointSpeedFactors[id]);
            }
            
            jointStates[id].isMoving = true;
        }
        
        unsigned long currentTime = millis();
        unsigned long elapsedTime = currentTime - jointStates[id].startTime;
        float progress = constrain((float)elapsedTime / jointStates[id].duration, 0.0f, 1.0f);
        
        float newPosition = smoothInterpolation(
            jointStates[id].startPos,
            jointStates[id].targetPos,
            progress
        );
        
        if (!fake) {
            setServoPosition(id, newPosition);
        }
        
        if(progress >= 1.0f) {
            jointStates[id].isMoving = false;
        }
        
        return newPosition;
    }
    return curDegree;  // if id is invalid, return current position
}

int controlGripper(float state, bool fake) {
    float angle = constrain(state, 90.0f, 180.0f);
    if (!fake) {
      setGripperPosition(angle);
    }

    return (int)angle;
}

void setup() {
  delay(1000);
  Serial.begin(115200);
  
  // 初始化所有舵机
  for (int i = 0; i < numServos; i++) {
    servos[i].attach(mtrPins[i]);
    // 使用每个舵机的初始位置
    currentAngles[i] = jointHomePositions[i];
    targetAngles[i] = jointHomePositions[i];
    tmpAngles[i] = jointHomePositions[i];
    jointStates[i].startPos = jointHomePositions[i];
    jointStates[i].targetPos = jointHomePositions[i];
    jointStates[i].isMoving = false;
    jointSpeedFactors[i] = 1.0f; // 初始化速度因子为1.0
    setServoPosition(i, jointHomePositions[i]);
  }
  
  // 初始化夹爪舵机
  gripperServo.attach(gripperPin);
  targetToolState = 90;
  currentToolState = controlGripper(targetToolState, false);
  
  delay(1000);
  
  // 初始化全局运动状态
  globalMotion.isNewMotion = false;
  globalMotion.globalDuration = 0;
  globalMotion.activeJoints = 0;
  globalMotion.syncMode = true;
}

void loop() {
  String command;
  if (Serial.available()) {
    command = Serial.readStringUntil('\n');
    
    if (command.startsWith("DELAY,")) {
      String param = command.substring(6);
      if (param.startsWith("S")) { 
          float seconds = param.substring(1).toFloat();
          time_delay = int(seconds * 1000);
      } else if (param.startsWith("MS")) {
          time_delay = param.substring(2).toInt();
      }
      delay(time_delay);
    } else if (command == "RECSTART") {
      isRecording = true;
    } else if (command == "RECSTOP") {
      isRecording = false;
      isRecordingOnceJoints = false;
      isRecordingOnceTool = false;

      // 重置targetAngles为当前角度，防止意外移动
      for (int i = 0; i < numServos; i++) {
        currentAngles[i] = targetAngles[i];
      }
    } else if (command.startsWith("REP,")) {
      int startIndex = command.indexOf(',') + 1;
      for (int i = 0; i < numServos; i++) {
        int nextIndex = command.indexOf(',', startIndex);
        if (nextIndex == -1 && i < numServos - 1) {
            return; // 数据格式不正确
        }
        String angleStr = (nextIndex == -1) ? command.substring(startIndex) : command.substring(startIndex, nextIndex);
        targetAngles[i] = angleStr.toFloat();
        startIndex = nextIndex + 1;
      }
      
      isMicroStep = true;
    } else if (command.startsWith("M280")) {
      // 格式: M280,<state> 其中state是工具的目标状态
      int commaIndex = command.indexOf(',');
      if (commaIndex != -1) {
        String stateStr = command.substring(commaIndex + 1);
        targetToolState = stateStr.toInt();
        isMoveTool = true;
      }
    } else if (command == "EXEC") {
      String angleCommand = Serial.readStringUntil('\n');
      processAngleCommand(angleCommand);
      
      // 计算全局运动参数
      globalMotion.globalDuration = calculateGlobalMotionDuration(targetAngles, currentAngles);
      globalMotion.isNewMotion = true;
      
      isExecute = true;
    } else if (command == "RECONCEJ") {
      isRecordingOnceJoints = true;
    } else if (command == "RECONCET") {
      isRecordingOnceTool = true;
    } else if (command.startsWith("SPD,")) {
        // 格式：SPD,J1:0.2,J2:0.3,J4:0.1 为特定关节设置速度系数
        String paramStr = command.substring(4); // 去掉"SPD,"前缀
        
        // 解析逗号分隔的关节速度设置
        int startIndex = 0;
        while (startIndex < paramStr.length()) {
            int endIndex = paramStr.indexOf(',', startIndex);
            if (endIndex == -1) endIndex = paramStr.length();
            
            String jointSpeedStr = paramStr.substring(startIndex, endIndex);
            jointSpeedStr.trim(); // 去除空格
            
            // 解析格式如"J1:0.2"
            int colonIndex = jointSpeedStr.indexOf(':');
            if (colonIndex != -1) {
                String jointStr = jointSpeedStr.substring(0, colonIndex);
                String speedStr = jointSpeedStr.substring(colonIndex + 1);
                
                // 提取关节编号 (J1 -> 0, J2 -> 1, 等等)
                if (jointStr.startsWith("J") && jointStr.length() > 1) {
                    int jointId = jointStr.substring(1).toInt() - 1; // J1=0, J2=1, etc.
                    float speed = speedStr.toFloat();
                    
                    // 验证关节ID有效性和速度值
                    if (jointId >= 0 && jointId < numServos && speed > 0.0f) {
                        jointSpeedFactors[jointId] = speed;
                    }
                }
            }
            
            startIndex = endIndex + 1;
        }
    }
    
    // 兼容旧命令格式
    else if (command == "RECONCE") {
      isRecordingOnceJoints = true;
    } else if (command == "START") {
      isRecording = true;
    } else if (command == "STOP") {
      isRecording = false;
    } else if (command == "EXEC_ONCE") {
      // 处理延时参数
      String delayCommand = Serial.readStringUntil('\n');
      time_delay = delayCommand.toInt();
      time_elapse = 0;
      
      // 处理角度命令
      String angleCommand = Serial.readStringUntil('\n');
      processAngleCommand(angleCommand);
    }
  }

  bool allServosDone = true;
  bool isMoveToolDone = false;
  
  // switch case
  if (isMicroStep) {                            // REP
    for (int i = 0; i < numServos; i++) {
      setServoPosition(i, targetAngles[i]);
      currentAngles[i] = targetAngles[i]; // 更新当前角度
    }
    Serial.println("CP1");
    isMicroStep = false;
  } else if (isExecute) {                             // EXEC
    if (isRecording) {
      // 在录制期间，使用tmpAngles类似原来的MOVEONCE行为
      for (int i = 0; i < numServos; i++) {
        tmpAngles[i] = moveMotor(targetAngles[i],tmpAngles[i],i,false);
      }
    } else {
      // 正常执行模式
      for (int i = 0; i < numServos; i++) {
        currentAngles[i] = moveMotor(targetAngles[i],currentAngles[i],i,false);
      }
    }
  } else if (isMoveTool) {                            // M280
    if (!isRecording) {
      currentToolState = controlGripper(targetToolState, false);
    } else {
      tmpToolState = controlGripper(targetToolState, false);
    }
    isMoveTool = false;
  } else if (isRecordingOnceJoints) {                 // RECONCEJ
    for (int i = 0; i < numServos; i++) {
      currentAngles[i] = moveMotor(targetAngles[i],currentAngles[i],i,true);
    }
  } else if (isRecordingOnceTool) {                   // RECONCET
    currentToolState = controlGripper(targetToolState, true);
  }

  // check if all joint motors have reached target angles
  for (int i = 0; i < numServos; i++) {
    if (jointStates[i].isMoving) {
      allServosDone = false;
      break;
    }
  }

  // check if tool has reached target state
  if (currentToolState == targetToolState) {
    isMoveToolDone = true;
  }

  // callbacks
  if (allServosDone) {
    if (isExecute) {
      Serial.println("CP0");
      isExecute = false;
    }
  }

  // recording callbacks
  if (isRecording) {
    if (!allServosDone && isRecordingOnceJoints) {
      Serial.print("REC,");  // add REC verification
      for (int i = 0; i < numServos; i++) {
          Serial.print(currentAngles[i]);
          if (i < numServos - 1) {
              Serial.print(",");
          } else {
              Serial.println();
          }
      }
    } else if (allServosDone && isRecordingOnceJoints) {
      Serial.println("RP0");
      isRecordingOnceJoints = false;
    }
    
    if (isMoveToolDone && isRecordingOnceTool) {
      Serial.print("M280,");
      Serial.println(currentToolState);
      Serial.println("RP1");
      isRecordingOnceTool = false;
    }
    
    // 兼容旧的录制逻辑
    else if (time_elapse <= time_delay) {
      // 处理EXEC_ONCE的延时输出
      time_elapse += 0.005;
      outputDesiredAngles();
    }
  }
  
  delay(5);
}

// 处理角度命令（确保数据格式正确）
void processAngleCommand(String command) {
  int startIndex = 0;
  for (int i = 0; i < numServos; i++) {
    int nextIndex = command.indexOf(',', startIndex);
    if (nextIndex == -1 && i < numServos - 1) {
      return;
    }
    String angleStr = (nextIndex == -1) ? command.substring(startIndex) : command.substring(startIndex, nextIndex);
    targetAngles[i] = mapAngle(angleStr.toFloat(), i);
    startIndex = nextIndex + 1;
  }
}

// 处理角度命令到临时数组
void processAngleCommandToTmp(String command) {
  int startIndex = 0;
  for (int i = 0; i < numServos; i++) {
    int nextIndex = command.indexOf(',', startIndex);
    if (nextIndex == -1 && i < numServos - 1) {
      return;
    }
    String angleStr = (nextIndex == -1) ? command.substring(startIndex) : command.substring(startIndex, nextIndex);
    targetAngles[i] = mapAngle(angleStr.toFloat(), i);
    startIndex = nextIndex + 1;
  }
}

// 输出当前角度
void outputCurrentAngles() {
  Serial.print("REC,");  //添加 REC 验证
  for (int i = 0; i < numServos; i++) {
    Serial.print(currentAngles[i]);
    if (i < numServos - 1) {
      Serial.print(",");
    }
  }
  Serial.println();
}

// 输出目标角度
void outputDesiredAngles() {
  Serial.print("REC,");  //添加 REC 验证
  for (int i = 0; i < numServos; i++) {
    Serial.print(targetAngles[i]);
    if (i < numServos - 1) {
      Serial.print(",");
    }
  }
  Serial.println();
}
