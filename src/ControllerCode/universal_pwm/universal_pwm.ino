#include "Wire.h"
#include <Adafruit_PWMServoDriver.h>

#define MIN_PULSE_WIDTH       700
#define MAX_PULSE_WIDTH       2300
#define FREQUENCY             50

// version check
#define FIRMWARE_VERSION "3.0.0"

/* ---------------------------------------------------------------------------------------- Joint Limits */
const int numServos = {{NUM_SERVOS}};
const int mtrPins[numServos] = { {{JOINT_PINS}} };
const int gripperPin = {{GRIPPER_PIN}};  // pin number for gripper servo (pca9685)
const int jointHomePositions[{{NUM_SERVOS}}] = { {{JOINT_HOME_POSITIONS}} };  // 每个关节的初始位置

const float jointLimits[numServos][2] = {
{{JOINT_LIMITS_ARRAY}}
};

// Gear ratios for each joint (default 1.0, negative values for reversed direction)
// Modify these values if your robot has gear ratios on specific joints
float gearRatios[numServos];

/* ---------------------------------------------------------------------------------------- Init */
Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver();

// End Effector Type
struct EOAT_Type {
    uint8_t type;          // 0: GRIPPER, 1: PEN_HOLDER, 2: VACUUM_PUMP
    uint8_t pins[4];       // multiple IO pins that the tool may use
    uint8_t pin_count;     // actual number of pins used
    int state;             // tool state (gripper: 90-180 degrees, pump: 0-1)
};
EOAT_Type currentEOAT;

// calibration offset for pulse max and min
float calibrationOffsets[numServos][2];
float gripperOffset[2] = {0.0f, 0.0f}; // Gripper offset

// Control parameters
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

int time_delay = 0;
int time_elapse = 0;

// Command queue for buffering multiple EXEC commands
#define CMD_QUEUE_SIZE 45
struct CommandBuffer {
    float angles[numServos];
    bool valid;
};
CommandBuffer commandQueue[CMD_QUEUE_SIZE];
int queueHead = 0;  // where to read from
int queueTail = 0;  // where to write to
int queueCount = 0; // number of commands in queue

// speed factors for each motor
float jointSpeedFactors[numServos];
const unsigned long BASE_MOTION_DURATION = 900;

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

// Queue helper functions
bool isQueueFull() {
    return queueCount >= CMD_QUEUE_SIZE;
}

bool isQueueEmpty() {
    return queueCount == 0;
}

bool enqueueCommand(float angles[]) {
    if (isQueueFull()) {
        return false;
    }
    
    // copy angles to queue
    for (int i = 0; i < numServos; i++) {
        commandQueue[queueTail].angles[i] = angles[i];
    }
    commandQueue[queueTail].valid = true;
    
    // move tail pointer
    queueTail = (queueTail + 1) % CMD_QUEUE_SIZE;
    queueCount++;
    
    return true;
}

bool dequeueCommand(float angles[]) {
    if (isQueueEmpty()) {
        return false;
    }
    
    // copy angles from queue
    for (int i = 0; i < numServos; i++) {
        angles[i] = commandQueue[queueHead].angles[i];
    }
    commandQueue[queueHead].valid = false;
    
    // move head pointer
    queueHead = (queueHead + 1) % CMD_QUEUE_SIZE;
    queueCount--;
    
    return true;
}

float mapFloat(float x, float in_min, float in_max, float out_min, float out_max) {
  return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min;
}

void setServoPosition(int pinNum, float position, float lowerLimit, float upperLimit) {
  setServoPosition(pinNum, position, lowerLimit, upperLimit, 0.0f, 0.0f);
}

void setServoPosition(int pinNum, float position, float lowerLimit, float upperLimit, float minPulseOffset, float maxPulseOffset) {
  // Find which joint index this pin belongs to
  int jointIndex = -1;
  for (int i = 0; i < numServos; i++) {
    if (mtrPins[i] == pinNum) {
      jointIndex = i;
      break;
    }
  }
  
  // Apply gear ratio if joint is found
  if (jointIndex >= 0) {
    position = position * gearRatios[jointIndex];
    
    // Apply gear ratio to limits as well
    float actualLower = lowerLimit * gearRatios[jointIndex];
    float actualUpper = upperLimit * gearRatios[jointIndex];
    
    // If gear ratio is negative (reversed direction), swap limits
    if (gearRatios[jointIndex] < 0) {
      float temp = actualLower;
      actualLower = actualUpper;
      actualUpper = temp;
    }
    
    lowerLimit = actualLower;
    upperLimit = actualUpper;
  }
  
  float pulse_wide = mapFloat(position, lowerLimit, upperLimit, 
                      MIN_PULSE_WIDTH + minPulseOffset, MAX_PULSE_WIDTH + maxPulseOffset);
  
  // add pulse width boundary check
  pulse_wide = constrain(pulse_wide, MIN_PULSE_WIDTH - 200, MAX_PULSE_WIDTH + 200);
  
  int pulse_width = int(pulse_wide / 1000000 * FREQUENCY * 4096);
  
  // add PWM value boundary check
  pulse_width = constrain(pulse_width, 0, 4095);
  
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
                setServoPosition(mtrPins[id], targetDegree, jointLimits[id][0], jointLimits[id][1], calibrationOffsets[id][0], calibrationOffsets[id][1]);
            }
            jointStates[id].isMoving = false;
            return targetDegree;
        }
        
        if(!jointStates[id].isMoving) {
            jointStates[id].startPos = curDegree;
            jointStates[id].targetPos = targetDegree;
            jointStates[id].startTime = millis();
            
            // use global unified time or independent time
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
            setServoPosition(mtrPins[id], newPosition, jointLimits[id][0], jointLimits[id][1], calibrationOffsets[id][0], calibrationOffsets[id][1]);
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
    int io = currentEOAT.pins[0];
    if (!fake) {
      setServoPosition(io, angle, 90.0f, 180.0f, gripperOffset[0], gripperOffset[1]);
    }

    return (int)angle;
}

// Convert gripper distance to motor angle for M280 command
int gripperDistanceToAngle(float distance) {
    return (int)(90 + (distance / 0.008f) * 90);
}

// Convert gripper motor angle back to original distance value for M280 command
float gripperAngleToDistance(int motorAngle) {
    return ((float)(motorAngle - 90) / 90.0f) * 0.008f;
}

int controlPump(int state, bool fake) {
    // pin[0] is suction channel, pin[1] is release channel
    uint8_t suctionPin = currentEOAT.pins[0];
    uint8_t releasePin = currentEOAT.pins[1];
    
    if (currentEOAT.state == state) {
      return state;
    }

    if (!fake) {
      if (state == 1) {
          // suction mode
          setServoPosition(suctionPin, 180.0f, 0.0f, 180.0f, 0.0f, 0.0f);
          setServoPosition(releasePin, 0.0f, 0.0f, 180.0f, 0.0f, 0.0f);
          
      } else if (state == 0) {
          setServoPosition(suctionPin, 0.0f, 0.0f, 180.0f, 0.0f, 0.0f);
          setServoPosition(releasePin, 180.0f, 0.0f, 180.0f, 0.0f, 0.0f);
          delay(50);
          setServoPosition(releasePin, 0.0f, 0.0f, 180.0f, 0.0f, 0.0f);
      }
    }

    return state;
}

// get current pulse width for a joint
int getCurrentPulseWidth(int joint) {
  if (joint >= 0 && joint < numServos) {
    float position = currentAngles[joint];
    float lowerLimit = jointLimits[joint][0];
    float upperLimit = jointLimits[joint][1];
    
    float pulse_wide = mapFloat(position, lowerLimit, upperLimit, 
                        MIN_PULSE_WIDTH + calibrationOffsets[joint][0], 
                        MAX_PULSE_WIDTH + calibrationOffsets[joint][1]);
    
    // add boundary check
    pulse_wide = constrain(pulse_wide, MIN_PULSE_WIDTH - 200, MAX_PULSE_WIDTH + 200);
    
    return int(pulse_wide);
  }
  return 0;
}

/* ---------------------------------------------------------------------------------------- Main */

void setup() {
  delay(2000);
  
  Serial.begin(115200);
  
  // Setup PWM Controller object
  pwm.begin();
  pwm.setPWMFreq(FREQUENCY);

  delay(1000);
  
  // initialize gear ratios to 1.0 (no gear ratio by default)
  for(int i = 0; i < numServos; i++) {
    gearRatios[i] = 1.0f;
  }
  
  // initialize calibration offsets to zero
  for(int i = 0; i < numServos; i++) {
    calibrationOffsets[i][0] = 0.0f;
    calibrationOffsets[i][1] = 0.0f;
  }
  
  // initialize end effector (default configuration is gripper)
  currentEOAT.type = 0;
  currentEOAT.pins[0] = gripperPin;
  currentEOAT.pin_count = 1;
  targetToolState = 90;
  currentEOAT.state = controlGripper(targetToolState, false);
  
  // initialize all servo positions to home position
  for(int i = 0; i < numServos; i++) {
    currentAngles[i] = jointHomePositions[i];
    targetAngles[i] = jointHomePositions[i];
    tmpAngles[i] = jointHomePositions[i];
    jointStates[i].startPos = jointHomePositions[i];
    jointStates[i].targetPos = jointHomePositions[i];
    jointStates[i].isMoving = false;
    jointSpeedFactors[i] = 1.0f; // initialize speed factor to 1.0
    setServoPosition(mtrPins[i], jointHomePositions[i], jointLimits[i][0], jointLimits[i][1], calibrationOffsets[i][0], calibrationOffsets[i][1]);
  }
  
  // initialize global motion state
  globalMotion.isNewMotion = false;
  globalMotion.globalDuration = 0;
  globalMotion.activeJoints = 0;
  globalMotion.syncMode = true;

  // initialize command queue
  queueHead = 0;
  queueTail = 0;
  queueCount = 0;
  for (int i = 0; i < CMD_QUEUE_SIZE; i++) {
    commandQueue[i].valid = false;
  }
}
 
void loop() {
  String command;
  if (Serial.available()) {
    command = Serial.readStringUntil('\n');
    
    if (command == "VERC") {
      Serial.println("INFOS");
      Serial.println("VER," + String(FIRMWARE_VERSION));
      Serial.println("Universal PWM Controller");
      Serial.println("INFOE");
    } else if (command.startsWith("CALIBRATE,")) {
      // format: CALIBRATE,joint,minOffset,maxOffset
      int firstComma = command.indexOf(',');
      int secondComma = command.indexOf(',', firstComma + 1);
      int thirdComma = command.indexOf(',', secondComma + 1);
      
      if (firstComma != -1 && secondComma != -1 && thirdComma != -1) {
        int joint = command.substring(firstComma + 1, secondComma).toInt();
        float minOffset = command.substring(secondComma + 1, thirdComma).toFloat();
        float maxOffset = command.substring(thirdComma + 1).toFloat();
        
        if (joint >= 0 && joint < numServos) {
          calibrationOffsets[joint][0] = minOffset;
          calibrationOffsets[joint][1] = maxOffset;
          
          for (int i = 0; i < numServos; i++) {
            setServoPosition(mtrPins[i], targetAngles[i], jointLimits[i][0], jointLimits[i][1], calibrationOffsets[i][0], calibrationOffsets[i][1]);
            currentAngles[i] = targetAngles[i];
          }
        }
      }
    } else if (command.startsWith("DELAY,")) {
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
    } else if (command.startsWith("TOOL[GRIPPER]")) {
      currentEOAT.type = 0;
      currentEOAT.pin_count = 1;
      currentEOAT.state = 90;

      int startIndex = command.indexOf(',') + 1;  // skip TOOL[GRIPPER],
      String io_str = command.substring(startIndex);
      if(io_str.startsWith("IO")) {
          int pin = io_str.substring(2).toInt();
          currentEOAT.pins[0] = pin;
          currentEOAT.pin_count = 1;
      } else {
          currentEOAT.pins[0] = gripperPin;
      }
      
      Serial.println("CP2");
    } else if (command.startsWith("TOOL[PEN]")) {  // pen holder does not need IO
      currentEOAT.type = 1;
      currentEOAT.pin_count = 0;
      currentEOAT.state = 0;
      
      Serial.println("CP2");
    } else if (command.startsWith("TOOL[PUMP]")) {
      currentEOAT.type = 2;
      currentEOAT.pin_count = 0;
      currentEOAT.state = 0;

      int startIndex = command.indexOf(',') + 1;  // skip TOOL[PUMP],
      while (startIndex < command.length()) {
          int endIndex = command.indexOf(',', startIndex);
          if (endIndex == -1) endIndex = command.length();
          
          String io_str = command.substring(startIndex, endIndex);
          if(io_str.startsWith("IO")) {
              int pin = io_str.substring(2).toInt();
              currentEOAT.pins[currentEOAT.pin_count++] = pin;  // use actual GPIO pin number
          }
          
          startIndex = endIndex + 1;
      }
      
      Serial.println("CP2");
    } else if (command.startsWith("M280")) {
      // format: M280,<value1>[,<value2>] where value1 and value2 are optional
      int firstComma = command.indexOf(',');
      if (firstComma != -1) {
        int secondComma = command.indexOf(',', firstComma + 1);
        
        if (secondComma != -1) {
          // there are two values: M280,value1,value2
          float value1 = command.substring(firstComma + 1, secondComma).toFloat();
          float value2 = command.substring(secondComma + 1).toFloat();
          
          if (currentEOAT.type == 0) { // gripper mode
            // for gripper, use the first value (usually the same) and convert to motor angle
            targetToolState = gripperDistanceToAngle(value1);
          } else if (currentEOAT.type == 2) { // pump mode
            // for pump, use the first value as the state
            targetToolState = (int)value1;
          }
        } else {
          // only one value case: M280,value
          float value = command.substring(firstComma + 1).toFloat();
          
          if (currentEOAT.type == 0) { // gripper mode
            // for gripper, convert the slider length to motor angle
            targetToolState = gripperDistanceToAngle(value);
          } else if (currentEOAT.type == 2) { // pump mode
            // for pump, use the value as the state
            targetToolState = (int)value;
          } else {
            // other mode, use the value directly
            targetToolState = (int)value;
          }
        }
        
        isMoveTool = true;
      }
    } else if (command == "EXEC") {
      String command = Serial.readStringUntil('\n');
      // Process the incoming command as comma-separated angle values
      int startIndex = 0;
      bool parseSuccess = true;
      
      for (int i = 0; i < numServos; i++) {
        int nextIndex = command.indexOf(',', startIndex);
        if (nextIndex == -1 && i < numServos - 1) {
            parseSuccess = false;
            break; // Improper formatting of incoming data
        }
        String inputStr = (nextIndex == -1) ? command.substring(startIndex) : command.substring(startIndex, nextIndex);
        tmpAngles[i] = inputStr.toFloat();
        startIndex = nextIndex + 1;
      }
      
      if (parseSuccess) {
        // Try to add command to queue
        if (enqueueCommand(tmpAngles)) {
          // Successfully added to queue, send immediate confirmation
          Serial.println("CP0");
          
          // If not currently executing, start execution with the first queued command
          if (!isExecute && queueCount > 0) {
            if (dequeueCommand(targetAngles)) {
              globalMotion.globalDuration = calculateGlobalMotionDuration(targetAngles, currentAngles);
              globalMotion.isNewMotion = true;
              isExecute = true;
            }
          }
        } else {
          // Queue is full, send error
          Serial.println("QFULL");
        }
      }
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
    } else if (command.startsWith("GPULSE,")) {
      // format: GPULSE,J1 to get the current pulse value of joint 1
      String jointStr = command.substring(7); // skip "GPULSE," prefix
      if (jointStr.startsWith("J") && jointStr.length() > 1) {
        int jointId = jointStr.substring(1).toInt() - 1; // J1=0, J2=1, etc.
        if (jointId >= 0 && jointId < numServos) {
          int pulseWidth = getCurrentPulseWidth(jointId);
          // send a single command response
          Serial.println("PULSE,J" + String(jointId + 1) + "," + String(pulseWidth));
        }
      }
    }
  }

  bool allServosDone = true;
  bool isMoveToolDone = false;
  
  // switch case
  if (isMicroStep) {                            // REP
    for (int i = 0; i < numServos; i++) {
      setServoPosition(mtrPins[i], targetAngles[i], jointLimits[i][0], jointLimits[i][1], calibrationOffsets[i][0], calibrationOffsets[i][1]);
      currentAngles[i] = targetAngles[i]; // update current angle
    }
    Serial.println("CP1");
    isMicroStep = false;
  } else if (isExecute) {                             // EXEC
    if (isRecording) {
      // during recording, use tmpAngles
      for (int i = 0; i < numServos; i++) {
        tmpAngles[i] = moveMotor(targetAngles[i],tmpAngles[i],i,false);
      }
    } else {
      // normal execution mode
      for (int i = 0; i < numServos; i++) {
        currentAngles[i] = moveMotor(targetAngles[i],currentAngles[i],i,false);
      }
    }
  } else if (isMoveTool) {                            // M280
    if (currentEOAT.type == 0) {
      currentEOAT.state = controlGripper(targetToolState, false);
    } else if (currentEOAT.type == 2) {
      currentEOAT.state = controlPump(targetToolState, false);
    }
  } else if (isRecordingOnceJoints) {                 // RECONCEJ
    for (int i = 0; i < numServos; i++) {
      currentAngles[i] = moveMotor(targetAngles[i],currentAngles[i],i,true);
    }
  } else if (isRecordingOnceTool) {                   // RECONCET
    if (currentEOAT.type == 0) {
      currentEOAT.state = controlGripper(targetToolState, true);
    } else if (currentEOAT.type == 2) {
      currentEOAT.state = controlPump(targetToolState, true);
    }
  }

  // check if all joint motors have reached target angles
  for (int i = 0; i < numServos; i++) {
    if (jointStates[i].isMoving) {
      allServosDone = false;
      break;
    }
  }

  // check if tool has reached target state
  if (currentEOAT.state == targetToolState) {
    isMoveToolDone = true;
    if (isMoveTool) {
      Serial.println("TP0");
      isMoveTool = false;
    }
  }

  // Check if current motion is complete and handle queue
  if (allServosDone && isExecute) {
    // Try to load next command from queue
    if (dequeueCommand(targetAngles)) {
      // Successfully loaded next command from queue
      // Calculate new motion parameters
      globalMotion.globalDuration = calculateGlobalMotionDuration(targetAngles, currentAngles);
      globalMotion.isNewMotion = true;
      // Continue executing (don't set isExecute to false)
    } else {
      // Queue is empty, stop executing
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
      Serial.println("CP0");
      isRecordingOnceJoints = false;
    }
    
    if (isMoveToolDone && isRecordingOnceTool) {
      Serial.print("M280,");
      if (currentEOAT.type == 0) { // gripper - convert back to distance
        Serial.println(gripperAngleToDistance(currentEOAT.state));
      } else {
        Serial.println(currentEOAT.state);
      }
      Serial.println("TP0");
      isRecordingOnceTool = false;
    }
  }
  
  delay(5); // Adjust based on your needs
}