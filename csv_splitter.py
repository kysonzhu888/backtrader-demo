import pandas as pd
import os
from datetime import datetime
import logging
from back_trace_paradigm import FilePathManager

class CsvSplitter:
    """CSV文件拆分工具类"""
    
    def __init__(self, input_file, output_dir=None):
        """
        初始化拆分工具
        
        Args:
            input_file: 输入文件路径
            output_dir: 输出目录路径，如果为None则使用默认路径
        """
        self.input_file = input_file
        self.output_dir = output_dir or FilePathManager.get_split_dir()
        self._ensure_output_dir()
        
    def _ensure_output_dir(self):
        """确保输出目录存在"""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            
    def split_by_year(self):
        """按年拆分CSV文件"""
        try:
            # 读取CSV文件
            logging.info(f"开始读取文件: {self.input_file}")
            df = pd.read_csv(
                self.input_file,
                parse_dates=['date'],
                usecols=['date', 'open', 'high', 'low', 'close', 'volume', 'money', 'open_interest', 'symbol']
            )
            
            # 获取数据的时间范围
            start_date = df['date'].min()
            end_date = df['date'].max()
            logging.info(f"数据时间范围: {start_date} 到 {end_date}")
            
            # 按年份分组
            df['year'] = df['date'].dt.year
            # 获取主力合约symbol（假设主力合约symbol和文件名前缀一致）
            # 例如 data/AU9999.XSGE.csv -> AU9999.XSGE
            main_symbol = os.path.splitext(os.path.basename(self.input_file))[0]
            
            # 遍历每一年
            for year, group in df.groupby('year'):
                # 生成输出文件名
                output_file = os.path.join(
                    self.output_dir,
                    f"{main_symbol}_{year}.csv"
                )
                
                # 保存分组数据
                group.to_csv(output_file, index=False)
                logging.info(f"已保存文件: {output_file}, 数据条数: {len(group)}")
                logging.info(f"数据时间范围: {group['date'].min()} 到 {group['date'].max()}")
                
            logging.info("文件拆分完成")
            
        except Exception as e:
            logging.error(f"拆分文件时发生错误: {e}")
            raise
            
    @staticmethod
    def get_file_info(file_path):
        """获取CSV文件信息"""
        try:
            df = pd.read_csv(file_path, parse_dates=['date'])
            start_date = df['date'].min()
            end_date = df['date'].max()
            total_rows = len(df)
            file_size = os.path.getsize(file_path) / (1024 * 1024)  # 转换为MB
            
            logging.info(f"文件信息:")
            logging.info(f"总行数: {total_rows}")
            logging.info(f"文件大小: {file_size:.2f}MB")
            logging.info(f"时间范围: {start_date} 到 {end_date}")
            
        except Exception as e:
            logging.error(f"获取文件信息时发生错误: {e}")
            raise

if __name__ == "__main__":
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # 使用示例
    input_file = FilePathManager.get_csv_path('AU')
    
    # 获取文件信息
    logging.info("获取原始文件信息...")
    CsvSplitter.get_file_info(input_file)
    
    # 拆分文件
    splitter = CsvSplitter(input_file)
    splitter.split_by_year() 