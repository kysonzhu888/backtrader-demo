
# ======================
# 1. 新增管理器类
# ======================
class ColorChangePendingManager:
    def __init__(self, bar_height_threshold=0.2):
        self.bar_height_threshold = bar_height_threshold
        self.color_change_pending = False
        self.pending_bars = []

    def reset(self):
        self.color_change_pending = False
        self.pending_bars = []

    def update(self, cur_color, position_color, bar_height):
        # 返回是否应平仓
        if cur_color == position_color:
            self.reset()
            return False
        # 没有pending，且变色，进入pending
        if not self.color_change_pending:
            self.color_change_pending = True
            self.pending_bars = [{'color': cur_color, 'bar_height': bar_height}]
            return False
        # pending中
        self.pending_bars.append({'color': cur_color, 'bar_height': bar_height})
        # 第一根高度<1.1，不平仓
        if len(self.pending_bars) == 1 and self.pending_bars[0]['bar_height'] < 1.1:
            return False
        # 第二根
        if len(self.pending_bars) == 2:
            if self.pending_bars[0]['bar_height'] < 2 and self.pending_bars[1]['bar_height'] < 2:
                return False
        # 第三根
        if len(self.pending_bars) == 3:
            total_height = sum(bar['bar_height'] for bar in self.pending_bars)
            if total_height > 2.5:
                self.reset()
                return True
            else:
                return False
        # 超过三根，强制重置
        if len(self.pending_bars) > 3:
            self.reset()
            return False
        return False

