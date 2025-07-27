# 定义需要获取数据的期货品种列表
shfe_product_types = ['AU', 'AG', 'CU', 'AL', 'ZN', 'NI', 'RB', 'HC', 'SS','RU','SN','AO','FU','BU','SP', 'PB']
gfex_product_types = ['SI','LC','PS']
ine_product_types = ['SC','NR','EC']
cffex_product_types = ['IC', 'IM', 'IF', 'IH','TL','T','TF','TS']
dce_product_types = ['I', 'JM', 'J', 'M','Y','P','LH','C','V','EG','EB','PG','PP','JD','A','B']
czce_product_types = ['SF', 'SM', 'FG','SA','CF','TA','SH','MA','OI','SR','RM','AP','UR','CJ','PX','PR']


# shfe_product_types = []
# gfex_product_types = []
# cffex_product_types = []
# dce_product_types = ['A']
# czce_product_types = []
# ine_product_types = []

class FeatureInfo:
    @staticmethod
    def get_exchange_product_types():
        return {
            'SHFE': shfe_product_types,
            'CFFEX': cffex_product_types,
            'DCE': dce_product_types,
            'CZCE': czce_product_types,
            'GFEX': gfex_product_types,
            'INE': ine_product_types
        }

    @staticmethod
    def get_product_name(product):
        product_names = {
            'AU': '沪金',
            'AG': '沪银',
            'A': '豆一',
            'B': '豆二',
            'CU': '沪铜',
            'AL': '沪铝',
            'ZN': '沪锌',
            'PB': '沪铅',
            'NI': '沪镍',
            'RB': '螺纹钢',
            'HC': '热轧卷板',
            'SS': '不锈钢',
            'RU': '橡胶',
            'SN': '锡',
            'AO': '铝氧化物（氧化铝）',
            'FU': '燃料油',
            'BU': '沥青',
            'SI': '工业硅',
            'EB': '聚乙烯',
            'LC': '液化天然气',
            'PS': '多晶硅',
            'SC': '原油',
            'NR': '20号胶',
            'SP':'纸浆',
            'IC': '中证500指数',
            'IM': '中证1000指数',
            'IF': '沪深300指数',
            'IH': '上证50指数',
            'TL': '三十年国债期货',
            'T': '十年国债期货',
            'TS': '二年国债期货',
            'TF': '五年国债期货',
            'I': '铁矿石',
            'JM': '焦煤',
            'J': '焦炭',
            'M': '豆粕',
            'Y': '豆油',
            'P': '棕榈油',
            'PP': '聚丙烯',
            'PR': '瓶片',
            'PX': '对二甲苯',
            'JD':'鸡蛋',
            'CJ':'红枣',
            'PG':'液化气',
            'LH': '生猪',
            'C': '玉米',
            'V': 'PVC 聚氯乙烯',
            'EG': '乙二醇',
            'SF': '硅铁',
            'SM': '锰硅',
            'FG': '玻璃',
            'SA': '纯碱',
            'CF': '棉花',
            'TA': 'PTA',
            'SH': '烧碱',
            'MA': '甲醇',
            'OI': '菜籽油',
            'SR': '白糖',
            'RM': '菜籽粕',
            'AP': '苹果',
            'UR': '尿素',
            'EC':'欧线集运',
        }
        return product_names.get(product, '未知商品')