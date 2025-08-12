# coding:utf-8
import logging
import environment
from datetime import datetime
from xtquant import xtdata
from utils.wechat import send_message, send_message_to_multiple_recipients

# 沪深300指数代码
code = '510300.SH'

# 添加计数器变量
daily_alert_count = 0
last_reset_date = datetime.now().date()

def reset_counter_if_new_day():
    global daily_alert_count, last_reset_date
    current_date = datetime.now().date()
    if current_date != last_reset_date:
        daily_alert_count = 0
        last_reset_date = current_date

def format_time(timestamp):
    try:
        # 将时间戳转换为datetime对象
        dt = datetime.fromtimestamp(timestamp / 1000)  # 将毫秒转换为秒
        # 返回格式化的时间字符串
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        print(f"时间格式化错误: {timestamp}, {str(e)}")
        return str(timestamp)


def callback_func(data):
    try:
        # 检查是否需要重置计数器
        reset_counter_if_new_day()

        # 获取最新数据
        if code in data:
            latest_data = data[code][-1]  # 获取最新的一条数据

            amount = latest_data['amount']
            close = latest_data['close']
            time_str = format_time(latest_data['time'])

            # 将成交额转换为亿元单位
            amount_in_yi = amount / 100000000

            # 如果成交额超过1亿，打印信息
            if amount > 100000000:
                global daily_alert_count
                daily_alert_count += 1

                msg = f'【沪深300异动播报】\n时间: {time_str}, 成交额: {amount_in_yi:.2f}亿, 收盘价: {close:.3f}'
                
                # 如果当天播报次数超过3次，添加提示信息
                if daily_alert_count > 3:
                    msg += "\n疑似国家队托底，请关注！"
                
                send_message_to_multiple_recipients(msg, [environment.group_chat_name_dlb,environment.group_chat_name_vip])
            else:
                logging.info(f"【沪深300正常播报】\n时间: {time_str}, 成交额: {amount_in_yi:.2f}亿, 收盘价: {close:.3f}")
        else:
            logging.warning(f"\n警告: 未找到代码 {code} 的数据")
            logging.error("可用的代码:", list(data.keys()))

    except Exception as e:
        logging.error(f'\n处理数据时出错：{str(e)}')
        logging.error('原始数据:', data)
        import traceback
        logging.error("详细错误信息:", traceback.format_exc())


try:
    # 发送启动通知  
    startup_msg = f"【策略启动通知】\n沪深300异动监控已启动\n品种: {code}\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    send_message(startup_msg, environment.group_chat_name_monitor)
    logging.info(f"🚀 沪深300异动监控启动成功 - 品种: {code}")

    # 订阅实时行情
    xtdata.subscribe_quote(code, period='1m', count=-1, callback=callback_func)

    # 使用xtdata.run()保持程序运行
    xtdata.run()

except KeyboardInterrupt:
    logging.info("\n程序已退出")
    # 发送停止通知
    stop_msg = f"【策略停止通知】\n沪深300异动监控已停止\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    try:
        send_message(stop_msg, environment.group_chat_name_monitor)
    except:
        pass
except Exception as e:
    logging.error(f'发生错误：{str(e)}')
    import traceback
    logging.error("详细错误信息:", traceback.format_exc())
    # 发送异常通知
    error_msg = f"【策略异常】\n沪深300异动监控出现异常\n错误: {str(e)[:100]}\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    try:
        send_message(error_msg, environment.group_chat_name_monitor)
    except:
        pass