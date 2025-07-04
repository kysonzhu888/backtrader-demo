import pandas as pd
from sqlalchemy import create_engine
import pymysql
pymysql.install_as_MySQLdb()



def mypandasview():
    # the usual pandas settings
    pd.set_option('display.unicode.east_asian_width', True)
    pd.set_option('display.unicode.ambiguous_as_wide', True)
    pd.set_option('display.colheader_justify', 'right')
    pd.set_option('expand_frame_repr', True)
    pd.set_option('display.column_space', 50)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.max_rows', None)
    pd.set_option('display.width', 2000)



def df_2_mysql(df, name, user='root', psw='root', ip='xx.xx.yy.yy:3306', db='stockdbleigh'):
    """
    :param df: The data to pass
    :param name: The name of the table in db
    :param psw: Your password of your database
    :param ip: Your IP
    :param db: The name of your database
    :param user: root
    :return: None
    """

    con = create_engine('mysql+pymysql://{}:{}@{}/{}'.format(user, psw, ip, db))  # mysql+pymysql的意思为：指定引擎为pymysql
    df.to_sql(name, con, index=False, if_exists='replace', chunksize=None)




# mytoken = {
#         "Leigh": "570………………33ade",
#         "Healer": "f6b51………………cfd8",
#         "Leo": "c09c………………ee8c",
#     }
#
# import tushare as ts
# token = ml.mytoken['Leigh']
# ts.set_token(token)
# pro = ts.pro_api(token)

