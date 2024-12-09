# ./core/event.py

class EventType:
    """事件类型枚举"""
    NORMAL = -1           # No event
    TOUCH_START = 0       # 触摸开始
    TOUCH_MOVE = 1        # 触摸移动
    TOUCH_END = 2         # 触摸结束
    PRESS = 3             # 按下
    RELEASE = 4           # 释放
    LONG_PRESS_RELEASE = 21 # 长按释放 
    CLICK = 5             # 点击v
    LONG_PRESS = 6        # 长按v
    DOUBLE_CLICK = 7      # 双击v
    DRAG_START = 8        # 拖动开始
    DRAG_MOVE = 9         # 拖动中
    DRAG_END = 10         # 拖动结束
    FOCUS = 11            # 获得焦点
    BLUR = 12             # 失去焦点
    VALUE_CHANGE = 13     # 值改变
    SELECTION_CHANGE = 14 # 选择改变
    CUSTOM = 20           # 自定义事件
"""
[Initializing] -> [Pending] -> [Scheduled] -> [Processing] -> [Completed]
                                ↘ [Cancelled]
                                ↘ [Errored]
                                ↘ [Timed Out]
"""
class Event:
    Initializing = -1 # 初始化中
    Pending = 0       # 准备中 
    Scheduled = 1     # 已调度
    Processing = 2    # 正在处理
    Completed = 10    # 已完成
    Errored = 99      # 出错
    Cancelled = 200   # 已取消
    Retrying = 201    # 重试中
    Blocked = 300     # 阻塞中
    Timed_Out = 999   # 超时

    """事件基类"""
    def __init__(self, event_type: EventType, data=None, target_position=None, target_widget=None):
        self.type: EventType = event_type    # 事件类型
        if target_position is None and target_widget is None:
            raise ValueError("事件必须指定目标位置或目标组件")
        self.target_widget = target_widget   # 事件目标对象
        self.target_position = target_position    # 事件目标位置
        self.data = data or {}              # 事件相关数据
        self.timestamp = 0                   # 事件发生时间戳
        self.status_code = self.Initializing

