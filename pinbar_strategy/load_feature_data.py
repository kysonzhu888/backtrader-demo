import environment
from tushare_helper import TushareHelper
from database_helper import DatabaseHelper
import logging


class FeatureDataLoader:
    def __init__(self, exchange, product_types):
        self.exchange = exchange
        self.product_types = product_types
        self.tushare_helper = TushareHelper(product_types=self.product_types, exchange=self.exchange)
        self.db_helper = DatabaseHelper()

    def load_data(self):
        try:
            # 获取分钟线数据
            df = self.tushare_helper.fetch_minute_data()
            logging.debug(f"获取到 {len(df)} 条1分钟线数据 for {self.product_types}")

            # 将数据存储到数据库
            self.db_helper.store_data(df, self.product_types)
            logging.debug(f"数据已存储到数据库 for {self.product_types}")
        except Exception as e:
            logging.error(f"获取数据时出错 for {self.product_types}: {str(e)}")
