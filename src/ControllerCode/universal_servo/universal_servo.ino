#include <Servo.h>

// version check
#define FIRMWARE_VERSION "3.0.0"

// define servo number and pins
const int numServos = {{NUM_SERVOS}}; 
const int mtrPins[numServos] = {{{JOINT_PINS}}}; 
const int gripperPin = {{GRIPPER_PIN}};  // pin number for gripper servo
const float jointLimits[numServos][2] = {
{{JOINT_LIMITS_ARRAY}}
};
const int jointHomePositions[numServos] = { {{JOINT_HOME_POSITIONS}} };  // 每个关节的初始位置

// Gear ratios for each joint (default 1.0, negative values for reversed direction)
// Modify these values if your robot has gear ratios on specific joints
float gearRatios[numServos];

// create servo objects
Servo servos[numServos];
Servo gripperServo;  // gripper servo

// End Effector Type
struct EOAT_Type {
    uint8_t type;          // 0: GRIPPER, 1: PEN_HOLDER, 2: VACUUM_PUMP
    uint8_t pins[4];       // multiple IO pins that the tool may use
    uint8_t pin_count;     // actual number of pins used
    int state;             // tool state (gripper: 90-180 degrees, pump: 0-1)
};
EOAT_Type currentEOAT;

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

// map input angle to servo actual angle range
float mapAngle(float angle, int servoIndex) {
  // ensure angle is within valid range for this servo
  return constrain(angle, jointLimits[servoIndex][0], jointLimits[servoIndex][1]);
}

void setServoPosition(int servoIndex, float position) {
  if (servoIndex < 0 || servoIndex >= numServos) return;
  
  float actualPosition = position * gearRatios[servoIndex];
  
  // Apply gear ratio to limits as well
  float actualLower = jointLimits[servoIndex][0] * gearRatios[servoIndex];
  float actualUpper = jointLimits[servoIndex][1] * gearRatios[servoIndex];
  
  // If gear ratio is negative (reversed direction), swap limits
  if (gearRatios[servoIndex] < 0) {
    float temp = actualLower;
    actualLower = actualUpper;
    actualUpper = temp;
  }
  
  // Constrain to actual limits
  actualPosition = constrain(actualPosition, actualLower, actualUpper);
  
  servos[servoIndex].write((int)actualPosition);
}

void setGripperPosition(float position) {
  float mappedAngle = constrain(position, 90.0f, 180.0f);
  gripperServo.write((int)mappedAngle);
}

// sin² interpolation
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

// Convert gripper distance to motor angle for M280 command
int gripperDistanceToAngle(float distance) {
    return (int)(90 + (distance / 0.008f) * 90);
}

// Convert gripper motor angle back to original distance value for M280 command
float gripperAngleToDistance(int motorAngle) {
    return ((float)(motorAngle - 90) / 90.0f) * 0.008f;
}

int controlPump(int state, bool fake) {
    // For standard servo library, pump control is simplified
    // In real implementation, you would control digital pins
    if (currentEOAT.state == state) {
      return state;
    }

    if (!fake) {
      // Implement pump control logic here if needed
      // This is a placeholder for compatibility
    }

    return state;
}

void setup() {
  delay(1000);
  Serial.begin(115200);
  
  // initialize gear ratios to 1.0 (no gear ratio by default)
  for(int i = 0; i < numServos; i++) {
    gearRatios[i] = 1.0f;
  }
  
  // initialize all servos
  for (int i = 0; i < numServos; i++) {
    servos[i].attach(mtrPins[i]);
    // use initial position for each servo
    currentAngles[i] = jointHomePositions[i];
    targetAngles[i] = jointHomePositions[i];
    tmpAngles[i] = jointHomePositions[i];
    jointStates[i].startPos = jointHomePositions[i];
    jointStates[i].targetPos = jointHomePositions[i];
    jointStates[i].isMoving = false;
    jointSpeedFactors[i] = 1.0f; // initialize speed factor to 1.0
    setServoPosition(i, jointHomePositions[i]);
  }
  
  // initialize end effector (default configuration is gripper)
  currentEOAT.type = 0;
  currentEOAT.pins[0] = gripperPin;
  currentEOAT.pin_count = 1;
  gripperServo.attach(gripperPin);
  targetToolState = 90;
  currentEOAT.state = controlGripper(targetToolState, false);
  
  delay(1000);
  
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
      Serial.println("Universal Servo Controller");
      Serial.println("INFOE");
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

      // reset targetAngles to current angles to prevent accidental movement
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
      currentEOAT.pins[0] = gripperPin;
      
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
      String angleCommand = Serial.readStringUntil('\n');
      // Process the incoming command as comma-separated angle values
      int startIndex = 0;
      bool parseSuccess = true;
      
      for (int i = 0; i < numServos; i++) {
        int nextIndex = angleCommand.indexOf(',', startIndex);
        if (nextIndex == -1 && i < numServos - 1) {
            parseSuccess = false;
            break; // Improper formatting of incoming data
        }
        String angleStr = (nextIndex == -1) ? angleCommand.substring(startIndex) : angleCommand.substring(startIndex, nextIndex);
        tmpAngles[i] = mapAngle(angleStr.toFloat(), i);
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
    }
  }

  bool allServosDone = true;
  bool isMoveToolDone = false;
  
  // switch case
  if (isMicroStep) {                            // REP
    for (int i = 0; i < numServos; i++) {
      setServoPosition(i, targetAngles[i]);
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
  
  delay(5);
}
