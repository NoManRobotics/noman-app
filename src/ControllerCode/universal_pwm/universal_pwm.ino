#include "Wire.h"
#include <Adafruit_PWMServoDriver.h>

#define MIN_PULSE_WIDTH       650
#define MAX_PULSE_WIDTH       2350
#define FREQUENCY             50

// version check
#define FIRMWARE_VERSION "2.0.0"

/* ---------------------------------------------------------------------------------------- Joint Limits */
const int numServos = {{NUM_SERVOS}};
const int mtrPins[numServos] = { {{JOINT_PINS}} };
const int gripperPin = {{GRIPPER_PIN}};  // pin number for gripper servo (pca9685)
const int jointHomePositions[{{NUM_SERVOS}}] = { {{JOINT_HOME_POSITIONS}} };  // 每个关节的初始位置

const float jointLimits[numServos][2] = {
{{JOINT_LIMITS_ARRAY}}
};

/* ---------------------------------------------------------------------------------------- Init */
Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver();

bool isExecute = false; 
bool isRecordingOnceJoints = false;
bool isRecordingOnceTool = false;
bool isRecording = false;
bool isMicroStep = false;
bool isMoveTool = false;

float targetAngles[numServos];
float currentAngles[numServos];  
float tmpAngles[numServos];

// M280 command tracking
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

float mapFloat(float x, float in_min, float in_max, float out_min, float out_max) {
  return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min;
}

void setServoPosition(int pinNum, float position, float lowerLimit, float upperLimit) {
  float pulse_wide = mapFloat(position, lowerLimit, upperLimit, 
                      MIN_PULSE_WIDTH, MAX_PULSE_WIDTH);
  int pulse_width = int(pulse_wide / 1000000 * FREQUENCY * 4096);
  pwm.setPWM(pinNum, 0, pulse_width);
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
                setServoPosition(mtrPins[id], targetDegree, jointLimits[id][0], jointLimits[id][1]);
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
            setServoPosition(mtrPins[id], newPosition, jointLimits[id][0], jointLimits[id][1]);
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
      setServoPosition(gripperPin, angle, 90.0f, 180.0f);
    }

    return (int)angle;
}

/* ---------------------------------------------------------------------------------------- Main */

void setup() {
  delay(2000);
  
  Serial.begin(115200);
  
  // Setup PWM Controller object
  pwm.begin();
  pwm.setPWMFreq(FREQUENCY);

  delay(1000);
  
  // 初始化末端执行器 (默认配置为夹爪)
  targetToolState = 90;             // 初始化目标状态
  currentToolState = controlGripper(targetToolState, false);
  
  // 初始化所有舵机位置到home position
  for(int i = 0; i < numServos; i++) {
    currentAngles[i] = jointHomePositions[i];
    targetAngles[i] = jointHomePositions[i];
    tmpAngles[i] = jointHomePositions[i];
    jointStates[i].startPos = jointHomePositions[i];
    jointStates[i].targetPos = jointHomePositions[i];
    jointStates[i].isMoving = false;
    jointSpeedFactors[i] = 1.0f; // 初始化速度因子为1.0
    setServoPosition(mtrPins[i], jointHomePositions[i], jointLimits[i][0], jointLimits[i][1]);
  }
  
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
      String command = Serial.readStringUntil('\n');
      // Process the incoming command as comma-separated angle values
      int startIndex = 0;
      for (int i = 0; i < numServos; i++) {
        int nextIndex = command.indexOf(',', startIndex);
        if (nextIndex == -1 && i < numServos - 1) {
            return; // Improper formatting of incoming data
        }
        String inputStr = (nextIndex == -1) ? command.substring(startIndex) : command.substring(startIndex, nextIndex);
        targetAngles[i] = inputStr.toFloat();
        startIndex = nextIndex + 1;
      }
      
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
  }

  bool allServosDone = true;
  bool isMoveToolDone = false;
  
  // switch case
  if (isMicroStep) {                            // REP
    for (int i = 0; i < numServos; i++) {
      setServoPosition(mtrPins[i], targetAngles[i], jointLimits[i][0], jointLimits[i][1]);
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
  }
  
  delay(5); // Adjust based on your needs
}