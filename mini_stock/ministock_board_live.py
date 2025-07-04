import matplotlib.pyplot as plt
import pandas as pd

class MiniStockBoardLive:
    def __init__(self, code_list):
        self.code_list = code_list
        self.fig, self.ax = plt.subplots(figsize=(12, 0.5*len(code_list)+2))
        plt.ion()
        self.table = None

    def show_board(self, stock_snap_list, now=None):
        df = pd.DataFrame(stock_snap_list)
        df = df[['code', 'name', 'price', 'chg', 'pct']]
        df.columns = ['代码', '名称', '现价', '涨跌额', '涨跌幅%']
        self.ax.clear()
        self.ax.axis('off')
        table = self.ax.table(cellText=df.values, colLabels=df.columns, loc='center', cellLoc='center', colLoc='center')
        for i in range(len(df)):
            chg = df.iloc[i]['涨跌额']
            pct = df.iloc[i]['涨跌幅%']
            color_chg = 'red' if chg > 0 else ('green' if chg < 0 else 'black')
            color_pct = 'red' if pct > 0 else ('green' if pct < 0 else 'black')
            table[(i+1, 3)].set_text_props(color=color_chg)
            table[(i+1, 4)].set_text_props(color=color_pct)
        table.auto_set_font_size(False)
        table.set_fontsize(14)
        table.scale(1.2, 1.2)
        self.ax.set_title(f"小市值成分股快照 {now}", fontsize=16)
        plt.pause(0.01) 