import os


class CSVFilePathManager:
    """文件路径管理器，统一管理所有文件路径和命名规则"""

    BASE_DATA_DIR = "data"
    SPLIT_DIR = os.path.join(BASE_DATA_DIR, "split")

    @staticmethod
    def get_main_symbol(product_type, market="XSGE"):
        """获取主力合约symbol（如 AU9999.XSGE）"""
        return f"{product_type}9999.{market}"

    @classmethod
    def get_csv_path(cls, product_type, market="XSGE"):
        """获取原始CSV文件路径"""
        return os.path.join(cls.BASE_DATA_DIR, f"{cls.get_main_symbol(product_type, market)}.csv")

    @classmethod
    def get_split_dir(cls):
        """获取拆分文件目录"""
        return cls.SPLIT_DIR

    @classmethod
    def get_split_file_path_by_year(cls, product_type, year, market="XSGE"):
        """获取按年分割的文件路径"""
        main_symbol = cls.get_main_symbol(product_type, market)
        return os.path.join(
            cls.get_split_dir(),
            f"{main_symbol}_{year}.csv"
        )

