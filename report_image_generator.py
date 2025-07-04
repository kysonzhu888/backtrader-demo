import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import textwrap
import os
from datetime import datetime
from pilot_helper import PilotHelper

class ReportImageGenerator:
    @staticmethod
    def text_to_image(text: str, out_path: str = None, font_size: int = 16, width: int = 100, dpi: int = 200) -> str:
        """
        将文本内容转为图片，返回图片路径
        Args:
            text: 要渲染的文本
            out_path: 输出图片路径（可选）
            font_size: 字体大小
            width: 每行最大字符数
            dpi: 图片分辨率
        Returns:
            图片文件路径
        """
        # 自动换行
        lines = []
        for paragraph in text.split('\n'):
            lines.extend(textwrap.wrap(paragraph, width=width, replace_whitespace=False) or [''])
        wrapped_text = '\n'.join(lines)

        # 计算图片高度
        line_count = len(lines)
        fig_height = max(2, line_count * font_size / 20)
        # 设置中文字体
        PilotHelper.get_cn_font(plt)

        fig, ax = plt.subplots(figsize=(12, fig_height), dpi=dpi)
        ax.axis('off')
        plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)

        ax.text(0, 1, wrapped_text, fontsize=font_size,
                va='top', ha='left', wrap=True, family='sans-serif')

        # 生成输出路径
        if not out_path:
            out_dir = 'reports/images'
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, f'report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png')
        plt.savefig(out_path, bbox_inches='tight', pad_inches=0.2)
        plt.close(fig)
        return out_path 