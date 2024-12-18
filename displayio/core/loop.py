# ./core/loop.py
from collections import deque
from heapq import heappush, heappop  # 用于优先级队列管理任务
import time
from machine import Timer # type: ignore
from ..utils.decorator import timeit

class MainLoop:
    """事件循环类，管理布局、渲染和事件处理"""
    def __init__(self, display):
        self.display = display
        # 标记是否运行
        self.running = False
        # 事件队列，最多存10个事件
        self.event_queue = deque([],10,1)
        # 优先级队列存储任务
        self.task_queue = []
        # 检查是否到刷新屏幕的时间。
        if self.display.fps > 0 :
            self.frame_interval = 1/self.display.fps
        else :
            self.frame_interval = 0.001  # 1000 FPS
        # 记录上次刷新屏幕的时间
        self.last_frame_time = 0
        self.frame_count = 0  # 新增：帧计数器
        self.last_fps_time = time.ticks_ms()  # 新增：上次计算FPS的时间
        # 检查输入的定时器
        self.input_timer = Timer(0)
        
    def start(self,func):
        """启动事件循环"""
        self.running = True
        # 初始化输入检测定时器
        self.input_timer.init(mode=Timer.PERIODIC,freq=550, callback=self._check_input)
        try:
            self._run(func)
        except KeyboardInterrupt:
            print("捕获到键盘中断，正在退出...")
            self.stop()
            print("已退出。")
    
    def stop(self):
        """停止事件循环"""
        self.running = False
        self.input_timer.deinit()
        
    def post_event(self, event):
        """添加事件到队列"""
        self.event_queue.append(event)

    def _process_events(self):
        """处理所有待处理事件"""
        while self.event_queue:
            event = self.event_queue.popleft()
            if self.display.root:
                self.display.root.event_handler(event)

    def _check_input(self,timer_object):
        for device in self.display.inputs:
            event = device.check_input()
            if event is not None:
                self.post_event(event)

    def _update_layout(self):
        """更新布局"""
        if self.display.root._layout_dirty:
            self.display.root.layout(dx=0, dy=0, width=self.display.width, height=self.display.height)

    def _update_display(self):
        """更新显示"""
        if self.display.root._dirty:
            self._render_widget(self.display.root)

    def _render_widget(self, widget):
        """递归渲染widget及其子组件
                任何具有get_bitmap的组件将被视为组件树的末端
        """
        if widget._dirty:
            widget._dirty = False
            if hasattr(widget, 'get_bitmap'):
                bitmap = widget.get_bitmap()
                mem_view = memoryview(bitmap.buffer)
                if self.display.threaded:
                    with self.display.lock:
                        self.display.thread_args['bitmap_memview'] = mem_view
                        self.display.thread_args['dx'] = widget.dx
                        self.display.thread_args['dy'] = widget.dy
                        self.display.thread_args['width'] = widget.width
                        self.display.thread_args['height'] = widget.height   
                else:
                    self.display.output.refresh(mem_view, dx=widget.dx, dy=widget.dy, width=widget.width, height=widget.height)
                return # 任何具有get_bitmap的组件将被视为组件树的末端

            for child in widget.children:
                self._render_widget(child)
    
    def _update_display_fully(self):
        """全屏刷新"""
        if self.display.root._dirty:
            self._render_widget_fully(self.display.root)
        mem_view = memoryview(self.display.root._bitmap.buffer)
        self.display.output.refresh(mem_view, dx=0, dy=0, width=self.display.width, height=self.display.height)

    def _render_widget_fully(self, widget):
        """绘制整个屏幕的buffer"""
        if widget._dirty:
            widget._dirty = False
            if hasattr(widget, 'get_bitmap'):
                bitmap = widget.get_bitmap()
                self.display.root._bitmap.blit(bitmap, dx=widget.dx, dy=widget.dy)
                return
            for child in widget.children:
                self._render_widget_fully(child)

    def _should_update_frame(self):
        """检查是否应该更新帧"""
        current_time = time.ticks_ms()
        if time.ticks_diff(current_time, self.last_frame_time) >= self.frame_interval*1000:
            self.last_frame_time = current_time
            return True
        return False
        
    def update_display(self):
        # 确认 局部刷新还是全局刷新
        if self.display.partly_refresh:
            self._update_display()
        else:
            self._update_display_fully()
        # 新增：帧数计数和FPS计算
        if self.display.show_fps:
            self.frame_count += 1
            self._calculate_fps()
            
    def _run(self,func):        
        """运行事件循环"""
        func()
        while self.running:
            # 处理事件
            self._process_events()
            # 检查是否需要更新帧
            if self._should_update_frame():
                # 更新布局
                self._update_layout()
                # 更新显示
                self.update_display()

    def _calculate_fps(self):
        """计算并打印每秒帧数"""
        current_time = time.ticks_ms()
        elapsed_time = time.ticks_diff(current_time, self.last_fps_time)

        if elapsed_time >= 1000:  # 每秒计算一次
            fps = 1000 * self.frame_count / elapsed_time
            print(f"FPS: {fps:.2f}")
            # 重置计数器
            self.frame_count = 0
            self.last_fps_time = current_time

    def add_task(self, callback, period=0, priority=10, one_shot=False, on_complete=None):
        """添加一个新任务"""
        task = Task(callback, period, priority, one_shot, on_complete)
        heappush(self.task_queue, task)

    def run(self):
        """运行调度器"""
        self.add_task(self._process_events,period=2)
        self.add_task(self._update_layout,period=self.frame_interval,priority=10)
        self.add_task(self.update_display,period=self.frame_interval,priority=11)
        while self.running:
            current_time = time.ticks_ms()
            if self.task_queue:
                task = self.task_queue[0]  # 查看队列中的最高优先级任务
                if time.ticks_diff(task.next_run, current_time) <= 0:
                    heappop(self.task_queue)  # 移除任务
                    if task.execute():  # 执行任务,任务完成返回False，未完成返回True
                        task.next_run = current_time + task.period
                        heappush(self.task_queue, task)  # 重新放入队列
            time.sleep_ms(2)  # 短暂休眠以降低 CPU 占用率



class Task:
    """表示一个任务"""
    def __init__(self, callback, period=0, priority=10, one_shot=False, on_complete=None):
        if bool(callback.__code__.co_flags & 0x20):
            self.generator = callback  # 如果是生成器，保存生成器对象
            self.callback = None
        else:
            self.generator = None
            self.callback = callback  # 普通函数回调
        self.callback = callback      # 任务的回调函数
        self.period = period          # 任务的执行间隔（ms）
        self.priority = priority      # 优先级，数值越小优先级越高
        self.one_shot = one_shot      # 是否是单次任务
        self.on_complete = on_complete # 任务完成执行的回调函数
        self.next_run = time.ticks_ms() + period  # 下次运行时间

    def __lt__(self, other):
        """比较任务，优先按时间排序；时间相同时按优先级排序。"""
        if self.next_run == other.next_run:
            return self.priority < other.priority
        return self.next_run < other.next_run
    
    def execute(self):
        """执行任务,任务完成返回False,未完成返回True"""
        if self.generator:
            try:
                next(self.generator)  # 执行生成器的下一步
            except StopIteration:
                if self.on_complete:  # 任务完成后执行回调
                    self.on_complete()
                return False  # 生成器已完成，标记任务结束
        elif self.callback:
            self.callback()  # 执行普通回调
            if self.one_shot and self.on_complete:  # 单次任务完成后执行回调
                self.on_complete()
        return not self.one_shot  # 对于单次任务，标记结束
    