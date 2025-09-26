import numpy as np

class RobotState:
    def __init__(self):
        self._state = {
            'id': 0,
            'tcp_offset': np.array([0, 0, 0, 0, 0, 0]),
            'end_effector_link': 0,
            'home_values': np.array([0,0,360,0]),
            'joint_angles': np.array([0,0,360,0]),
            'tool_state': [],
            'target_position': np.array([0, 0, 0]),
            'target_orientation': np.array([0, 0, 0, 1]),
            'base_position': np.array([0, 0, 0]),
            'base_orientation': np.array([0, 0, 0, 1])
        }
        self._observers = []

    def add_observer(self, observer):
        """添加观察者"""
        if observer not in self._observers:
            self._observers.append(observer)

    def remove_observer(self, observer):
        """移除观察者"""
        if observer in self._observers:
            self._observers.remove(observer)

    def notify_observers(self, sender=None):
        """通知所有观察者，排除sender自身
        
        Args:
            sender: 消息发送者，不会收到自己发送的通知
        """
        for observer in self._observers:
            if observer != sender:  # 排除自己
                observer.update(self._state)

    def update_state(self, key, value, sender=None):
        """更新状态并通知观察者，可排除sender
        
        Args:
            key: 要更新的状态键
            value: 新的状态值
            sender: 消息发送者，不会收到自己发送的通知
        """
        if key in self._state:
            self._state[key] = value
            self.notify_observers(sender)

    def get_state(self, key=None):
        """获取当前状态"""
        if key is None:
            return self._state
        else:
            return self._state[key]