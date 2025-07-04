import logging
import schedule
import time
from datetime import datetime, timedelta
from threading import Thread
from sqlalchemy import text
from database_helper import DatabaseHelper

class DatabaseCleaner:
    def __init__(self):
        self.db_helper = DatabaseHelper()
        self.max_records = 10000  # 每张表最大记录数
        self.cleanup_time = "07:45"  # 每天清理时间
        self.is_running = False

    def get_all_tables(self):
        """获取所有表名"""
        try:
            with self.db_helper.engine.connect() as conn:
                # 获取所有表名
                result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
                tables = [row[0] for row in result]
                return tables
        except Exception as e:
            logging.error(f"获取表名失败: {e}")
            return []

    def get_table_record_count(self, table_name):
        """获取表的记录数"""
        try:
            with self.db_helper.engine.connect() as conn:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                return result.scalar()
        except Exception as e:
            logging.error(f"获取表 {table_name} 记录数失败: {e}")
            return 0

    def get_table_time_column(self, table_name):
        """获取表的时间列名"""
        try:
            with self.db_helper.engine.connect() as conn:
                # 获取表结构
                result = conn.execute(text(f"PRAGMA table_info({table_name})"))
                columns = result.fetchall()
                
                # 查找可能的时间列
                time_columns = ['time', 'timestamp', 'trade_date', 'created_at', 'updated_at']
                for col in columns:
                    if col[1].lower() in time_columns:
                        return col[1]
                return None
        except Exception as e:
            logging.error(f"获取表 {table_name} 时间列失败: {e}")
            return None

    def cleanup_table(self, table_name):
        """清理单个表的数据"""
        try:
            # 获取记录数
            count = self.get_table_record_count(table_name)
            if count <= self.max_records:
                return

            # 获取时间列
            time_col = self.get_table_time_column(table_name)
            if not time_col:
                logging.warning(f"表 {table_name} 未找到时间列，跳过清理")
                return

            # 计算需要删除的记录数
            records_to_delete = count - self.max_records

            # 删除较早的记录
            with self.db_helper.engine.connect() as conn:
                # 使用子查询找到要保留的记录的时间点
                query = f"""
                DELETE FROM {table_name}
                WHERE {time_col} < (
                    SELECT {time_col}
                    FROM {table_name}
                    ORDER BY {time_col} DESC
                    LIMIT 1 OFFSET {self.max_records}
                )
                """
                conn.execute(text(query))
                conn.commit()

            logging.info(f"表 {table_name} 清理完成，删除了 {records_to_delete} 条记录")
        except Exception as e:
            logging.error(f"清理表 {table_name} 失败: {e}")

    def cleanup_all_tables(self):
        """清理所有表的数据"""
        logging.info("开始清理数据库...")
        tables = self.get_all_tables()
        for table in tables:
            self.cleanup_table(table)
        logging.info("数据库清理完成")

    def run_cleanup_task(self):
        """运行清理任务"""
        while self.is_running:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次

    def start(self):
        """启动清理服务"""
        if self.is_running:
            return

        self.is_running = True
        # 设置每天定时任务
        schedule.every().day.at(self.cleanup_time).do(self.cleanup_all_tables)
        
        # 启动定时任务线程
        thread = Thread(target=self.run_cleanup_task)
        thread.daemon = True
        thread.start()
        
        logging.info(f"数据库清理服务已启动，将在每天 {self.cleanup_time} 执行清理任务")

    def stop(self):
        """停止清理服务"""
        self.is_running = False
        schedule.clear()
        logging.info("数据库清理服务已停止")

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # 创建并启动清理服务
    cleaner = DatabaseCleaner()
    cleaner.start()

    try:
        # 保持主线程运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        cleaner.stop()
        logging.info("程序已退出")
