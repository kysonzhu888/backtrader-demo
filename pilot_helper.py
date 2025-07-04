import platform
import matplotlib.font_manager as font_manager
import matplotlib.dates as mdates


class PilotHelper:


    @staticmethod
    def get_cn_font(plt):
        # 根据操作系统设置字体
        if platform.system() == 'Darwin':  # macOS
            font_path = "/System/Library/Fonts/STHeiti Medium.ttc"
        elif platform.system() == 'Windows':
            font_path = "C:/Windows/Fonts/msyh.ttc"  # 微软雅黑
        else:
            font_path = None

        if font_path:
            font_prop = font_manager.FontProperties(fname=font_path)
            font_manager.fontManager.addfont(font_path)
            plt.rcParams['font.family'] = font_prop.get_name()
        plt.rcParams['axes.unicode_minus'] = False