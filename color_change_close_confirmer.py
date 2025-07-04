import logging

FIRST_HEIGHT_LIMIT = 1.1
SECOND_HEIGHT_LIMIT = 0.9
THIRD_HEIGHT_LIMIT = 0.5
FORTH_HEIGHT_LIMIT = 0.25

class ColorChangeCloseConfirmer:
    def __init__(self):
        self.is_active = False  # 是否激活
        self.check_index = 0    # 当前检查的柱子索引
        self.accumulated_height = 0  # 累计高度
        self.position_color = None  # 持仓柱子的颜色

    def activate(self, position_color, bar_height):
        """在变色且柱子高度小于0.3时激活"""
        if bar_height < FIRST_HEIGHT_LIMIT:
            self.is_active = True
            self.check_index = 0
            self.accumulated_height = bar_height
            self.position_color = position_color
            return True
        return False

    def check(self, current_color, bar_height):
        """
        检查是否应该平仓
        返回: (是否平仓, 是否重置)
        """
        if not self.is_active:
            return False, False

        self.check_index += 1
        self.accumulated_height += bar_height

        # 变色后的第二根
        if self.check_index == 1:
            met = "满足" if self.accumulated_height < FIRST_HEIGHT_LIMIT + SECOND_HEIGHT_LIMIT else "不满足"
            logging.info(f"检查第{self.check_index}根，高度和：{self.accumulated_height},{met}")
            # 如果仍然没有变回 持仓颜色
            if current_color != self.position_color:
                if self.accumulated_height >= (FIRST_HEIGHT_LIMIT + SECOND_HEIGHT_LIMIT):
                    return True, True
                return False, False
            else:
                return False, True

        # 变色后的第三根
        if self.check_index == 2:
            met = "满足" if self.accumulated_height < (FIRST_HEIGHT_LIMIT + SECOND_HEIGHT_LIMIT + THIRD_HEIGHT_LIMIT) else "不满足"
            logging.info(f"检查第{self.check_index}根，高度和：{self.accumulated_height},{met}")

            if current_color != self.position_color:
                if self.accumulated_height >= (FIRST_HEIGHT_LIMIT + SECOND_HEIGHT_LIMIT + THIRD_HEIGHT_LIMIT):
                    return True, True
                return False, False
            else:
                return False, True

        if self.check_index == 3:
            met = "满足" if self.accumulated_height < (FIRST_HEIGHT_LIMIT + SECOND_HEIGHT_LIMIT + THIRD_HEIGHT_LIMIT + FORTH_HEIGHT_LIMIT) else "不满足"
            logging.info(f"检查第{self.check_index}根，高度和：{self.accumulated_height},{met}")

            if current_color != self.position_color:
                if self.accumulated_height >= (FIRST_HEIGHT_LIMIT + SECOND_HEIGHT_LIMIT + THIRD_HEIGHT_LIMIT + FORTH_HEIGHT_LIMIT):
                    return True, True
                return False, False
            else:
                return False, True

        if self.check_index == 4 or self.check_index == 5:
            met = "满足" if self.accumulated_height < (FIRST_HEIGHT_LIMIT + SECOND_HEIGHT_LIMIT + THIRD_HEIGHT_LIMIT + FORTH_HEIGHT_LIMIT) else "不满足"
            logging.info(f"检查第{self.check_index}根，高度和：{self.accumulated_height},{met}")

            if current_color != self.position_color:
                if self.accumulated_height >= (FIRST_HEIGHT_LIMIT + SECOND_HEIGHT_LIMIT + THIRD_HEIGHT_LIMIT + FORTH_HEIGHT_LIMIT):
                    return True, True
                return False, False
            else:
                return False, True

        # 其他情况，一律平仓
        return True, True

    def reset(self):
        """重置状态"""
        self.is_active = False
        self.check_index = 0
        self.accumulated_height = 0