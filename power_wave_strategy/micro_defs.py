from enum import Enum

Minimum_Data_Count = 35

class BarColor(Enum):
    RED = '红'
    GREEN = '绿'


class Direction(Enum):
    LONG = '多'
    SHORT = '空'


class MACDCross(Enum):
    GOLDEN = '金叉'
    DEAD = '死叉'
