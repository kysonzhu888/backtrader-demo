import environment
import threading
import time
import logging
import urllib.parse
import urllib3
import ssl  # 导入ssl模块
from datetime import datetime, timedelta
import pytz  # 用于处理时区，确保定时准确性
import json  # 导入json模块
import os

from date_utils import DateUtils
from wechat_helper import WeChatHelper

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

#https://market.aliyun.com/apimarket/detail/cmapi013828#sku=yuncode782800000


# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class WeatherReport:
    HOST = 'https://aliv18.data.moji.com'
    PATH = '/whapi/json/alicityweather/condition'
    METHOD = 'POST'

    def __init__(self, appcode, city_id, token):
        self._appcode = appcode
        self._city_id = city_id
        self._token = token
        self._url = self.HOST + self.PATH
        # 使用 urllib3.PoolManager，并在创建时禁用SSL证书验证
        # cert_reqs='NONE' 禁用证书验证
        self._http = urllib3.PoolManager(cert_reqs='NONE')
        logging.info("WeatherReport instance created with SSL verification disabled.")

    def broadcast_news(self):
        """
        执行天气/新闻播报逻辑。
        通过墨迹天气API获取天气信息并进行播报（单次执行）。
        """
        logging.info(f"[{datetime.now()}] Fetching weather data...")
        try:
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Authorization': 'APPCODE ' + self._appcode
            }
            bodys = {}
            bodys['cityId'] = self._city_id
            bodys['token'] = self._token  # 恢复token参数
            post_data = urllib.parse.urlencode(bodys).encode('utf-8')

            # SSL证书验证已在PoolManager中禁用，这里无需额外参数
            response = self._http.request(self.METHOD, self._url, body=post_data, headers=headers)
            content = response.data.decode('utf-8')

            if content:
                # 解析API返回的JSON数据
                data = json.loads(content)

                # 检查code和msg判断API调用是否成功
                if data.get('code') == 0 and data.get('msg') == 'success':
                    city_info = data.get('data', {}).get('city', {})
                    condition_info = data.get('data', {}).get('condition', {})

                    if city_info and condition_info:
                        # 提取天气信息
                        city_name = city_info.get('name', '未知城市')
                        weather_condition = condition_info.get('condition', '未知天气')
                        temp = condition_info.get('temp', '未知温度')
                        real_feel = condition_info.get('realFeel', '未知体感')
                        wind_dir = condition_info.get('windDir', '未知风向')
                        wind_level = condition_info.get('windLevel', '未知风力')
                        humidity = condition_info.get('humidity', '未知湿度')
                        tips = condition_info.get('tips', '暂无建议')
                        update_time_str = condition_info.get('updatetime', '未知时间')
                        # 格式化更新时间
                        try:
                            update_time = datetime.strptime(update_time_str, '%Y-%m-%d %H:%M:%S').strftime('%H:%M')
                            update_time_formatted = f'({update_time}更新)'
                        except ValueError:
                            update_time_formatted = ''

                        # 生成播报消息
                        broadcast_message = (
                            f"{city_name}天气：{weather_condition}，气温 {temp}°C (体感 {real_feel}°C)。\n"
                            f"风向：{wind_dir}{wind_level}级，湿度：{humidity}%。\n"
                            f"生活建议：{tips}。{update_time_formatted}"
                        )

                        logging.info(f"Weather broadcast message: {broadcast_message}")

                        # 例如：发送到微信
                        wx_helper = WeChatHelper()
                        wx_helper.send_message(broadcast_message, "老公老婆") # 请替换为你的目标群聊名

                    else:
                        logging.warning("API response missing city or condition info.")
                else:
                    logging.warning(f"API call failed: code={data.get('code')}, msg={data.get('msg')}")

            else:
                logging.warning("Failed to fetch weather data: Empty response.")

        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON response: {e}")
        except Exception as e:
            logging.error(f"Error during weather data fetching and broadcasting: {e}")
        finally:
            logging.info("Weather broadcast attempt finished.")


# 定时任务函数，安排在下一个小时的0分执行
def schedule_weather_report(appcode, city_id, token):
    now = DateUtils.now()

    # 计算下一个小时的整点
    if now.minute == 26:
        # 如果正好是整点，下次执行就是2小时后
        next_run = now + timedelta(hours=2)
    else:
        # 计算距离下一个小时整点的秒数
        next_hour = now.replace(minute=26) + timedelta(hours=2)
        next_run = next_hour

    # 计算延迟时间
    delay = (next_run - now).total_seconds()

    # 如果是 debug 模式，则立刻执行（例如设置 delay 为几秒）
    if os.getenv('DEBUG_MODE') == '1':
        delay = 3  # Debug模式下5秒后执行

    logging.info(f"下次天气日报计划在 {next_run.strftime('%Y-%m-%d %H:%M:%S')} 执行，延迟 {delay:.2f} 秒...")

    # 定义一个 wrapper 函数，用于执行播报并重新安排定时任务
    def run_and_reschedule():
        logging.info("定时天气播报任务开始执行...")
        # 实例化 WeatherReport 并执行播报
        report_task = WeatherReport(appcode, city_id, token)
        report_task.broadcast_news()
        logging.info("定时天气播报任务执行完毕。")
        time.sleep(60)
        # 安排下一次定时任务
        schedule_weather_report(appcode, city_id, token)  # 循环调用

    # 设置定时器
    timer = threading.Timer(delay, run_and_reschedule)
    timer.start()


# 示例用法
if __name__ == "__main__":
    # 请替换为你的实际 AppCode, CityId, Token
    your_appcode = '3fc303daf2f743b480a1828854f0e6af'
    your_city_id = '39'  # 例如：城市ID为2
    your_token = '50b53ff8dd7d9fa320d3d3ca32cf8ed1'

    # 启动首次定时任务安排
    schedule_weather_report(your_appcode, your_city_id, your_token)
