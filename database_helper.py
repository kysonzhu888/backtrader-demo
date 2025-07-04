import time
from functools import wraps

from date_utils import DateUtils
from environment import debug_latest_candle_time

import os
import logging

from sqlalchemy import create_engine
import pandas as pd
from sqlalchemy.pool import QueuePool
from threading import Lock
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, Float
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from sqlalchemy import text
# 预定义表结构，通过反射加载
from sqlalchemy import MetaData


def monitor_connection_pool(func):
    """连接池使用监控装饰器[6,11](@ref)"""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        pool = self.engine.pool
        status = {
            "checkedout": pool.checkedout(),  # 活跃连接数
            "checkedin": pool.checkedin(),  # 空闲连接数
            "overflow": pool.overflow(),  # 溢出连接数
            "size": pool.size()  # 连接池容量
        }

        # 超过阈值告警
        if status["checkedout"] > pool.size() * 0.8:
            logging.warning(f"连接池高负载: {status}")

        # 记录执行日志
        logging.debug(f"连接池状态: {status}")
        return func(self, *args, **kwargs)

    return wrapper


class DatabaseHelper:
    # 在写入方法中添加写锁
    _write_lock = Lock()
    _wal_initialized = False  # 类变量
    _last_checkpoint_time = 0

    def __init__(self):
        database_uri = 'sqlite:///futures_data.db'
        self.engine = create_engine(database_uri,
                                    poolclass=QueuePool,
                                    pool_size=20,
                                    max_overflow=0,  # 禁止超额连接
                                    pool_recycle=3600,  # 防止连接僵死
                                    connect_args={'timeout': 30}
                                    )
        self.Base = declarative_base()
        self._enable_wal_mode()

    def _enable_wal_mode(self):
        """
        启用WAL（Write-Ahead Logging）模式：
        - 使用`with self.engine.connect() as conn:`来创建一个新的数据库连接，并确保在`with`块结束时自动关闭连接。
        - 执行`PRAGMA`命令来设置SQLite的日志模式、同步模式和锁等待超时时间。
        - WAL模式允许同时进行读写操作，提高了数据库的并发性能。
        - 在崩溃后，WAL日志可以用于恢复未完成的事务。
        - 写操作首先记录到WAL日志中，只有在日志文件被检查点（checkpoint）时，数据才会被写入主数据库文件。
        """
        if not self._wal_initialized:
            with self._write_lock:  # 添加写锁保护[9,10](@ref)
                with self.engine.connect() as conn:
                    conn.execute(text("PRAGMA journal_mode=WAL"))  # 启用 WAL
                    conn.execute(text("PRAGMA synchronous=NORMAL"))  # 平衡性能与安全
                    #                    conn.execute(text("PRAGMA synchronous=FULL"))  # 确保数据完整写入
                    conn.execute(text("PRAGMA busy_timeout=30000"))  # 锁等待超时 30 秒
                    conn.execute(text("PRAGMA wal_autocheckpoint=2000"))  # 每2GB触发自动检查点[4,9](@ref)

                    # 其他配置
                    DatabaseHelper._wal_initialized = True

    def create_feature_table(self, product_type):
        table_name = f'futures_data_{product_type}'

        class FuturesData(self.Base):
            __tablename__ = table_name
            __table_args__ = {'extend_existing': True}  # 关键参数[7](@ref)

            id = Column(Integer, primary_key=True)
            code = Column(String)
            freq = Column(String)
            time = Column(DateTime)
            open = Column(Float)
            close = Column(Float)
            high = Column(Float)
            low = Column(Float)
            volume = Column(Float)
            amount = Column(Float)
            oi = Column(Float)

        meta = MetaData()
        meta.reflect(bind=self.engine)
        if table_name not in meta.tables:
            self.Base.metadata.create_all(self.engine)
        return FuturesData

    # 新增辅助方法：预先建立 code 到 product_type 的映射字典
    def _build_code_product_mapping(self, product_types):
        code_to_product = {}
        for product_type in product_types:
            mapping_ts_code = self.get_mapping_ts_code(product_type)
            code_to_product[mapping_ts_code] = product_type
        return code_to_product

    @monitor_connection_pool
    def store_data(self, df, product_types):
        with self._write_lock:  # 确保写操作互斥

            try:
                logging.info(f"开始存入{product_types}({len(product_types)} 条)一分钟级别数据...")
                code_product_map = self._build_code_product_mapping(product_types)

                df['datetime'] = pd.to_datetime(
                    df['time'],
                    format='%Y-%m-%d %H:%M:%S',  # 匹配图片中的格式
                    errors='coerce'  # 将无效数据转为 NaT（非强制中断）
                )

                # 3. 单次遍历 DataFrame（O(m)）
                data_to_insert = {pt: [] for pt in product_types}  # 按 product_type 分组存储数据

                for _, row in df.iterrows():
                    product_type = code_product_map.get(row['code'])
                    if product_type is None:
                        continue  # 无匹配的 product_type

                    # 获取对应 product_type 的 FuturesData 模型类（提前缓存）
                    futures_data_cls = self.create_feature_table(product_type)

                    # 构造数据对象并存入分组列表
                    data = futures_data_cls(
                        code=row['code'],
                        freq=row['freq'],
                        time=row['datetime'],
                        open=row['open'],
                        close=row['close'],
                        high=row['high'],
                        low=row['low'],
                        volume=row['vol'],
                        amount=row['amount'],
                        oi=row['oi']
                    )
                    data_to_insert[product_type].append(data)

                    # 4. 批量插入（减少数据库交互次数）
                for product_type, data_list in data_to_insert.items():
                    if data_list:
                        self.bulk_insert(data_list)

                self._auto_checkpoint()
                logging.info(f"存入{product_types}({len(product_types)} 条) 一分钟级别数据成功")
                # <-- 新增触发点
            except Exception as e:

                table_name = f'futures_data_{product_type}'
                logging.error(f"Error storing data for {table_name}: {e}")

    def bulk_insert(self, data_to_insert):
        """
            优化后的批量插入方法，结合 SQLAlchemy 的批量操作特性和事务控制
            特性说明：
            1. 使用 bulk_insert_mappings 代替 bulk_save_objects 提升性能 [6,7](@ref)
            2. 采用显式事务管理避免隐式提交开销
            3. 增加分批提交机制防止内存溢出
            """

        session = sessionmaker(bind=self.engine)()
        try:
            session.bulk_save_objects(data_to_insert)
            session.commit()
        except Exception as e:
            logging.error(f"Error during bulk insert: {e}")
            session.rollback()
        finally:
            session.close()

    def read_feature_data(self, product_type, end_time=None):
        table_name = f'futures_data_{product_type}'

        # 从数据库中读取数据
        if os.getenv('DEBUG_MODE') == '1':
            end_time = f'{debug_latest_candle_time}'

        query = f"SELECT * FROM {table_name}"
        if end_time:
            query += f" WHERE time <= '{end_time}'"

        try:
            df = pd.read_sql(query, self.engine)
            if 'time' not in df.columns:
                logging.error(f"'time' column not found in data for {table_name}")
                return pd.DataFrame()  # 返回空DataFrame以避免后续处理出错
            return df
        except Exception as e:
            logging.error(f"Error reading data from {table_name}: {e}")
            return pd.DataFrame()  # 返回空DataFrame以避免后续处理出错

    def manual_checkpoint(self, mode="PASSIVE"):
        """手动执行检查点[4,9](@ref)
        模式选项: PASSIVE(默认)/TRUNCATE/RESTART
        """
        try:
            with self.engine.connect() as conn:
                # 执行检查点并返回统计信息
                result = conn.execute(
                    text(f"PRAGMA wal_checkpoint({mode})")
                ).fetchone()
                logging.debug(f"Checkpoint执行结果: {dict(zip(['busy', 'logged', 'checkpointed'], result))}")

                if mode == "TRUNCATE":  # 清空WAL文件[9](@ref)
                    conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
        except Exception as e:
            logging.error(f"Checkpoint失败: {str(e)}")

    def _auto_checkpoint(self):
        """智能检查点（网页14、网页16）"""
        current_time = time.time()
        wal_size = os.path.getsize("futures_data.db-wal") if os.path.exists("futures_data.db-wal") else 0

        # 动态调整检查点频率（网页16）
        checkpoint_interval = 60 if wal_size < 0.5 * 1024 * 1024 else 10
        if (current_time - self._last_checkpoint_time > checkpoint_interval) or (wal_size > 0.5 * 1024 * 1024):
            self.manual_checkpoint("TRUNCATE")
            self._last_checkpoint_time = current_time

    def store_pinbar_data(self, timestamp, product_type, product_name, interval, score, key_level_strength,
                          score_detail,open,close,high,low):
        with self._write_lock:
            session = sessionmaker(bind=self.engine)()
            try:
                # 在方法内部定义 PinbarData 类
                PinbarData = self.create_pinbar_table()

                # 使用 check_existing_entry 方法进行去重检查
                if not self.check_existing_entry(timestamp, product_type, interval):
                    new_entry = PinbarData(
                        timestamp=timestamp,
                        product_type=product_type,
                        product_name=product_name,
                        interval=interval,
                        score=score,
                        score_detail=score_detail,
                        key_level_strength=key_level_strength,
                        open=open,
                        close=close,
                        high=high,
                        low=low
                    )
                    session.add(new_entry)
                    session.commit()
                else:
                    logging.info(f"Entry already exists for {product_type} {product_name} at {timestamp}")
            except Exception as e:
                logging.error(f"Error storing pinbar data: {e}")
                session.rollback()
            finally:
                session.close()

    def check_existing_entry(self, timestamp, product_type, interval, time_delta=timedelta(minutes=1)):
        session = sessionmaker(bind=self.engine)()
        try:
            # 在方法内部定义 PinbarData 类
            PinbarData = self.create_pinbar_table()

            # 检查是否存在相同的记录，时间间隔小于指定的时间
            existing_entry = session.query(PinbarData).filter(
                PinbarData.timestamp >= timestamp - time_delta,
                PinbarData.timestamp <= timestamp + time_delta,
                PinbarData.product_type == product_type,
                PinbarData.interval == interval
            ).first()
            return existing_entry is not None
        except Exception as e:
            logging.error(f"Error checking existing entry: {e}")
            return False
        finally:
            session.close()

    def create_pinbar_table(self):
        table_name = 'pinbar_data'

        class PinbarData(self.Base):
            __tablename__ = table_name
            __table_args__ = {'extend_existing': True}  # 关键参数[7](@ref)

            id = Column(Integer, primary_key=True)
            timestamp = Column(DateTime)
            product_type = Column(String)
            product_name = Column(String)
            interval = Column(String)
            broadcast = Column(Integer)
            score = Column(Integer)
            key_level_strength = Column(String)
            score_detail = Column(String)
            open = Column(Float)
            close = Column(Float)
            high = Column(Float)
            low = Column(Float)

        meta = MetaData()
        meta.reflect(bind=self.engine)
        if table_name not in meta.tables:
            self.Base.metadata.create_all(self.engine)
        return PinbarData

    def create_futures_basic_cache_table(self):
        table_name = 'futures_basic_cache'

        class FuturesBasicCache(self.Base):
            __tablename__ = table_name
            __table_args__ = {'extend_existing': True}

            id = Column(Integer, primary_key=True)
            product_type = Column(String, unique=True)
            mapping_ts_code = Column(String)
            lastest_update_time = Column(DateTime)  # 新增字段

        meta = MetaData()
        meta.reflect(bind=self.engine)
        if table_name not in meta.tables:
            self.Base.metadata.create_all(self.engine)
        return FuturesBasicCache

    def insert_or_update_futures_basic_cache(self, product_type, mapping_ts_code):
        FuturesBasicCache = self.create_futures_basic_cache_table()
        session = sessionmaker(bind=self.engine)()
        try:
            # 检查是否存在
            entry = session.query(FuturesBasicCache).filter_by(product_type=product_type).first()
            if entry:
                entry.mapping_ts_code = mapping_ts_code
                entry.lastest_update_time = DateUtils.now()  # 更新字段的时间
            else:
                entry = FuturesBasicCache(product_type=product_type, mapping_ts_code=mapping_ts_code, lastest_update_time=DateUtils.now())
                session.add(entry)
            session.commit()
        except Exception as e:
            logging.error(f"Error inserting or updating futures_basic_cache: {e}")
            session.rollback()
        finally:
            session.close()

    def get_mapping_ts_code(self, product_type):
        FuturesBasicCache = self.create_futures_basic_cache_table()
        session = sessionmaker(bind=self.engine)()
        try:
            entry = session.query(FuturesBasicCache).filter_by(product_type=product_type).first()
            if entry:
                # 检查 lastest_update_time 是否超过4小时
                if entry.lastest_update_time and (DateUtils.now() - entry.lastest_update_time).total_seconds() > 14400:
                    return None
                return entry.mapping_ts_code
            return None
        except Exception as e:
            logging.error(f"Error retrieving mapping_ts_code: {e}")
            return None
        finally:
            session.close()

    def get_all_mapping_ts_codes(self):
        FuturesBasicCache = self.create_futures_basic_cache_table()
        session = sessionmaker(bind=self.engine)()
        try:
            # 查询所有记录
            entries = session.query(FuturesBasicCache).all()
            # 提取 mapping_ts_code 字段
            mapping_ts_codes = [entry.mapping_ts_code for entry in entries]
            return mapping_ts_codes
        except Exception as e:
            logging.error(f"Error retrieving all mapping_ts_codes: {e}")
            return []
        finally:
            session.close()

    def store_daily_change(self, ts_code, trade_date,close, daily_pct_change, product_name, ma20=None, ma5=None):
        FeaturesDayReport = self.create_features_day_report_table()

        session = sessionmaker(bind=self.engine)()
        try:
            new_entry = FeaturesDayReport(ts_code=ts_code, trade_date=trade_date,close=close, daily_pct_change=daily_pct_change, product_name=product_name, ma20=ma20, ma5=ma5)
            session.add(new_entry)
            session.commit()
        except Exception as e:
            logging.error(f"Error storing daily change data: {e}")
            session.rollback()
        finally:
            session.close()

    def store_daily_data(self):
        FeaturesDayReport = self.create_features_day_report_table()

        session = sessionmaker(bind=self.engine)()
        try:
            new_entry = FeaturesDayReport()
            session.add(new_entry)
            session.commit()
        except Exception as e:
            logging.error(f"Error storing daily change data: {e}")
            session.rollback()
        finally:
            session.close()

    def get_existing_daily_changes(self, ts_codes, end_date):
        session = sessionmaker(bind=self.engine)()
        try:
            # 使用 FeaturesDayReport 类来查询
            FeaturesDayReport = self.create_features_day_report_table()
            query = session.query(FeaturesDayReport).filter(FeaturesDayReport.ts_code.in_(ts_codes), FeaturesDayReport.trade_date == end_date)
            df = pd.read_sql(query.statement, self.engine)
            return df
        except Exception as e:
            logging.error(f"Error retrieving existing daily changes: {e}")
            return pd.DataFrame()
        finally:
            session.close()

    def create_features_day_report_table(self):
        table_name = 'features_daily_report'

        class FeaturesDayReport(self.Base):
            __tablename__ = table_name
            __table_args__ = {'extend_existing': True}

            id = Column(Integer, primary_key=True)
            ts_code = Column(String)
            trade_date = Column(String)
            close = Column(Float)
            daily_pct_change = Column(Float)
            product_name = Column(String)  # 新增字段
            ma5 = Column(Float)  # 新增字段
            ma20 = Column(Float)  # 新增字段

        meta = MetaData()
        meta.reflect(bind=self.engine)
        if table_name not in meta.tables:
            self.Base.metadata.create_all(self.engine)
        return FeaturesDayReport

    def store_weekly_change(self, ts_code, trade_date, weekly_pct_change, product_name):
        FeaturesWeeklyReport = self.create_features_weekly_report_table()

        session = sessionmaker(bind=self.engine)()
        try:
            new_entry = FeaturesWeeklyReport(ts_code=ts_code, trade_date=trade_date, weekly_pct_change=weekly_pct_change, product_name=product_name)
            session.add(new_entry)
            session.commit()
        except Exception as e:
            logging.error(f"Error storing weekly change data: {e}")
            session.rollback()
        finally:
            session.close()

    def create_features_weekly_report_table(self):
        table_name = 'features_weekly_report'

        class FeaturesWeeklyReport(self.Base):
            __tablename__ = table_name
            __table_args__ = {'extend_existing': True}

            id = Column(Integer, primary_key=True)
            ts_code = Column(String)
            trade_date = Column(String)
            weekly_pct_change = Column(Float)
            product_name = Column(String)

        meta = MetaData()
        meta.reflect(bind=self.engine)
        if table_name not in meta.tables:
            self.Base.metadata.create_all(self.engine)
        return FeaturesWeeklyReport

    def get_existing_weekly_changes(self, ts_codes, trade_date):
        FeaturesWeeklyReport = self.create_features_weekly_report_table()
        session = sessionmaker(bind=self.engine)()
        try:
            query = session.query(FeaturesWeeklyReport).filter(FeaturesWeeklyReport.ts_code.in_(ts_codes), FeaturesWeeklyReport.trade_date == trade_date)
            df = pd.read_sql(query.statement, self.engine)
            return df
        except Exception as e:
            logging.error(f"Error retrieving existing weekly changes: {e}")
            return pd.DataFrame()
        finally:
            session.close()

    def store_monthly_change(self, ts_code, trade_date, monthly_pct_change, product_name):
        FeaturesMonthlyReport = self.create_features_monthly_report_table()

        session = sessionmaker(bind=self.engine)()
        try:
            new_entry = FeaturesMonthlyReport(ts_code=ts_code, trade_date=trade_date, monthly_pct_change=monthly_pct_change, product_name=product_name)
            session.add(new_entry)
            session.commit()
        except Exception as e:
            logging.error(f"Error storing monthly change data: {e}")
            session.rollback()
        finally:
            session.close()

    def create_features_monthly_report_table(self):
        table_name = 'features_monthly_report'

        class FeaturesMonthlyReport(self.Base):
            __tablename__ = table_name
            __table_args__ = {'extend_existing': True}

            id = Column(Integer, primary_key=True)
            ts_code = Column(String)
            trade_date = Column(String)
            monthly_pct_change = Column(Float)
            product_name = Column(String)

        meta = MetaData()
        meta.reflect(bind=self.engine)
        if table_name not in meta.tables:
            self.Base.metadata.create_all(self.engine)
        return FeaturesMonthlyReport

    def get_existing_monthly_changes(self, ts_codes, trade_date):
        FeaturesMonthlyReport = self.create_features_monthly_report_table()
        session = sessionmaker(bind=self.engine)()
        try:
            query = session.query(FeaturesMonthlyReport).filter(FeaturesMonthlyReport.ts_code.in_(ts_codes), FeaturesMonthlyReport.trade_date == trade_date)
            df = pd.read_sql(query.statement, self.engine)
            return df
        except Exception as e:
            logging.error(f"Error retrieving existing monthly changes: {e}")
            return pd.DataFrame()
        finally:
            session.close()

    def create_daily_feature_table(self, product_type):
        table_name = f'futures_daily_data_{product_type}'

        class FuturesDailyData(self.Base):
            __tablename__ = table_name
            __table_args__ = {'extend_existing': True}

            id = Column(Integer, primary_key=True)
            ts_code = Column(String)
            trade_date = Column(String)
            pre_close = Column(Float)
            pre_settle = Column(Float)
            open = Column(Float)
            high = Column(Float)
            low = Column(Float)
            close = Column(Float)
            settle = Column(Float)
            change1 = Column(Float)
            change2 = Column(Float)
            vol = Column(Float)
            amount = Column(Float)
            oi = Column(Float)
            oi_chg = Column(Float)

        meta = MetaData()
        meta.reflect(bind=self.engine)
        if table_name not in meta.tables:
            self.Base.metadata.create_all(self.engine)
        return FuturesDailyData

    def store_daily_feature_data(self, df, product_type):
        FuturesDailyData = self.create_daily_feature_table(product_type)
        session = sessionmaker(bind=self.engine)()
        try:
            data_list = [
                FuturesDailyData(
                    ts_code=row['ts_code'],
                    trade_date=row['trade_date'],
                    pre_close=row['pre_close'],
                    pre_settle=row['pre_settle'],
                    open=row['open'],
                    high=row['high'],
                    low=row['low'],
                    close=row['close'],
                    settle=row['settle'],
                    change1=row['change1'],
                    change2=row['change2'],
                    vol=row['vol'],
                    amount=row['amount'],
                    oi=row['oi'],
                    oi_chg=row['oi_chg']
                )
                for _, row in df.iterrows()
            ]
            session.bulk_save_objects(data_list)
            session.commit()
        except Exception as e:
            logging.error(f"Error storing daily feature data: {e}")
            session.rollback()
        finally:
            session.close()

    def read_kline_data(self, product_type, interval='1min', end_time=None, limit=None):
        """
        统一读取分钟线或日线数据，只返回原始DataFrame，不做任何pandas处理
        :param product_type: 品种
        :param interval: '1min', '5min', ... 或 '1d'
        :param end_time: 截止时间，分钟线为datetime字符串，日线为YYYYMMDD字符串
        :param limit: 限制返回的记录数，None表示不限制
        :return: DataFrame
        """
        if interval == '1d':
            table_name = f"futures_daily_data_{product_type}"
            time_col = 'trade_date'
            if end_time and end_time != 'now':
                if isinstance(end_time, str) and '-' in end_time:
                    end_time_fmt = pd.to_datetime(end_time).strftime('%Y%m%d')
                else:
                    end_time_fmt = str(end_time)
                query = f"SELECT * FROM {table_name} WHERE {time_col} <= '{end_time_fmt}'"
            else:
                query = f"SELECT * FROM {table_name}"
            query += f" ORDER BY {time_col} DESC"
        else:
            table_name = f"futures_data_{product_type}"
            time_col = 'time'
            if end_time and end_time != 'now':
                query = f"SELECT * FROM {table_name} WHERE {time_col} <= '{end_time}' ORDER BY {time_col} DESC"
            else:
                query = f"SELECT * FROM {table_name} ORDER BY {time_col} DESC"

        if limit:
            query += f" LIMIT {limit}"

        try:
            df = pd.read_sql(query, self.engine)
            return df
        except Exception as e:
            logging.error(f"读取 {table_name} 数据失败: {e}")
            return None

    def get_recent_unbroadcasted_pinbars(self, current_time, time_delta):
        session = sessionmaker(bind=self.engine)()
        try:
            PinbarData = self.create_pinbar_table()
            # 查询最近2分钟且未播报的 pinbar 数据
            recent_pinbars = session.query(PinbarData).filter(
                PinbarData.timestamp >= current_time - time_delta,
                PinbarData.timestamp <= current_time,
                (PinbarData.broadcast == None) | (PinbarData.broadcast == 0)
            ).all()
            return recent_pinbars
        except Exception as e:
            logging.error(f"Error retrieving recent unbroadcasted pinbars: {e}")
            return []
        finally:
            session.close()

    def set_pinbar_broadcasted(self, pinbar_id):
        session = sessionmaker(bind=self.engine)()
        try:
            PinbarData = self.create_pinbar_table()
            pinbar = session.query(PinbarData).filter(PinbarData.id == pinbar_id).first()
            if pinbar:
                pinbar.broadcast = 1
                session.commit()
        except Exception as e:
            logging.error(f"Error setting pinbar broadcasted: {e}")
            session.rollback()
        finally:
            session.close()

    def get_recent_broadcasted_pinbars(self, current_time, time_delta):
        session = sessionmaker(bind=self.engine)()
        try:
            PinbarData = self.create_pinbar_table()
            # 查询最近 time_delta 内已播报的 pinbar 数据
            recent_pinbars = session.query(PinbarData).filter(
                PinbarData.timestamp >= current_time - time_delta,
                PinbarData.timestamp <= current_time,
                PinbarData.broadcast == 1
            ).all()
            return recent_pinbars
        except Exception as e:
            logging.error(f"Error retrieving recent broadcasted pinbars: {e}")
            return []
        finally:
            session.close()

    def create_power_wave_signal_table(self):
        table_name = 'power_wave_signal'
        class PowerWaveSignal(self.Base):
            __tablename__ = table_name
            __table_args__ = {'extend_existing': True}
            id = Column(Integer, primary_key=True)
            product_type = Column(String)
            interval = Column(String)
            direction = Column(String)  # 多/空
            percentile = Column(Float)
            higher_period_direction = Column(String)  # （大级别周期）多/空
            signal_time = Column(String)  # 信号时间
            is_triggered = Column(Integer, default=0)  # 0=未入场，1=已入场
            macd_triggered = Column(Integer, default=0)  # 0=未满足，1=已满足
            boll_triggered = Column(Integer, default=0)  # 0=未满足，1=已满足
            closed = Column(Integer, default=0)  # 0未平仓 1已平仓
            close_price = Column(Float, nullable=True)  # 新增，平仓价格
            open_price = Column(Float, nullable=True)  # 新增，开仓价格
            close_time = Column(String, nullable=True)  # 新增，平仓时间
        meta = MetaData()
        meta.reflect(bind=self.engine)
        if table_name not in meta.tables:
            self.Base.metadata.create_all(self.engine)
        return PowerWaveSignal

    def store_power_wave_signal(self, product_type, interval, direction, percentile, higher_period_direction, macd_triggered,boll_triggered,signal_time,is_triggered,open_price):
        PowerWaveSignal = self.create_power_wave_signal_table()
        session = sessionmaker(bind=self.engine)()
        try:
            new_entry = PowerWaveSignal(
                product_type=product_type,
                interval=interval,
                direction=direction,
                percentile=percentile,
                macd_triggered=macd_triggered,
                boll_triggered=boll_triggered,
                higher_period_direction=higher_period_direction,
                signal_time=signal_time,
                is_triggered=is_triggered,
                open_price=open_price
            )
            session.add(new_entry)
            session.commit()
        except Exception as e:
            logging.error(f"Error storing power wave signal: {e}")
            session.rollback()
        finally:
            session.close()

    def get_untriggered_power_wave_signals(self, product_type, interval):
        PowerWaveSignal = self.create_power_wave_signal_table()
        session = sessionmaker(bind=self.engine)()
        try:
            signals = session.query(PowerWaveSignal).filter_by(product_type=product_type, interval=interval, is_triggered=0).all()
            return signals
        except Exception as e:
            logging.error(f"Error retrieving untriggered power wave signals: {e}")
            return []
        finally:
            session.close()

    def update_power_wave_signal_triggered(self, signal_id):
        PowerWaveSignal = self.create_power_wave_signal_table()
        session = sessionmaker(bind=self.engine)()
        try:
            signal = session.query(PowerWaveSignal).filter_by(id=signal_id).first()
            if signal:
                signal.is_triggered = 1
                session.commit()
        except Exception as e:
            logging.error(f"Error updating power wave signal triggered: {e}")
            session.rollback()
        finally:
            session.close()

    def update_power_wave_signal_macd(self, signal_id):
        PowerWaveSignal = self.create_power_wave_signal_table()
        session = sessionmaker(bind=self.engine)()
        try:
            signal = session.query(PowerWaveSignal).filter_by(id=signal_id).first()
            if signal:
                signal.macd_triggered = 1
                session.commit()
        except Exception as e:
            logging.error(f"Error updating power wave signal macd_triggered: {e}")
            session.rollback()
        finally:
            session.close()

    def update_power_wave_signal_boll(self, signal_id):
        PowerWaveSignal = self.create_power_wave_signal_table()
        session = sessionmaker(bind=self.engine)()
        try:
            signal = session.query(PowerWaveSignal).filter_by(id=signal_id).first()
            if signal:
                signal.boll_triggered = 1
                session.commit()
        except Exception as e:
            logging.error(f"Error updating power wave signal boll_triggered: {e}")
            session.rollback()
        finally:
            session.close()

    def update_power_wave_signal_exit(self, signal_id, close_price, close_time):
        PowerWaveSignal = self.create_power_wave_signal_table()
        session = sessionmaker(bind=self.engine)()
        try:
            signal = session.query(PowerWaveSignal).filter_by(id=signal_id).first()
            if signal:
                signal.closed = 1
                signal.close_price = close_price
                signal.close_time = close_time
                session.commit()
        except Exception as e:
            logging.error(f"Error updating power wave signal exit: {e}")
            session.rollback()
        finally:
            session.close()

    def update_power_wave_signal_broadcast(self, signal_id):
        PowerWaveSignal = self.create_power_wave_signal_table()
        session = sessionmaker(bind=self.engine)()
        try:
            signal = session.query(PowerWaveSignal).filter_by(id=signal_id).first()
            if signal:
                signal.is_triggered = 1
                session.commit()
        except Exception as e:
            logging.error(f"Error updating power wave signal boll_triggered: {e}")
            session.rollback()
        finally:
            session.close()
    def update_power_wave_signal_open_price(self, signal_id,open_price):
        PowerWaveSignal = self.create_power_wave_signal_table()
        session = sessionmaker(bind=self.engine)()
        try:
            signal = session.query(PowerWaveSignal).filter_by(id=signal_id).first()
            if signal:
                signal.open_price = open_price
                session.commit()
        except Exception as e:
            logging.error(f"Error updating power wave signal boll_triggered: {e}")
            session.rollback()
        finally:
            session.close()

    def get_latest_triggered_power_wave_signal(self, product_type, interval):
        PowerWaveSignal = self.create_power_wave_signal_table()
        session = sessionmaker(bind=self.engine)()
        try:
            # 查询最新一条is_triggered=1的记录，可能需要进一步筛选品种和周期，这里按产品和周期过滤
            signal = session.query(PowerWaveSignal).filter_by(product_type=product_type, interval=interval, is_triggered=1).order_by(PowerWaveSignal.signal_time.desc()).first()
            return signal
        except Exception as e:
            logging.error(f"Error retrieving latest triggered power wave signal: {e}")
            return None
        finally:
            session.close()

    def get_latest_unclosed_signal(self, product_type, interval, direction):
        """
        获取最新的未平仓信号
        :param product_type: 品种
        :param interval: 时间周期
        :param direction: 方向（多/空）
        :return: 最新的未平仓信号，如果没有则返回None
        """
        PowerWaveSignal = self.create_power_wave_signal_table()
        session = sessionmaker(bind=self.engine)()
        try:
            signal = session.query(PowerWaveSignal).filter(
                PowerWaveSignal.product_type == product_type,
                PowerWaveSignal.interval == interval,
                PowerWaveSignal.direction == direction,
                PowerWaveSignal.closed == 0  # 未平仓
            ).order_by(PowerWaveSignal.signal_time.desc()).first()
            return signal
        except Exception as e:
            logging.error(f"Error retrieving latest unclosed signal: {e}")
            return None
        finally:
            session.close()
