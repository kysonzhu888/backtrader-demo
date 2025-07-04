import environment
import requests
import logging
import base64


class MarketDataClient:
    def __init__(self, market_data_url=None):
        if market_data_url is None:
            # 优先从environment读取
            host = getattr(environment, 'STOCK_MARKET_SERVICE_HOST', 'localhost')
            port = getattr(environment, 'STOCK_MARKET_SERVICE_PORT', 5000)
            self.market_data_url = f"http://{host}:{port}/stock"
        else:
            self.market_data_url = market_data_url
        
    def fetch_data(self):
        """获取最新行情数据"""
        try:
            response = requests.get(f"{self.market_data_url}/market_data")
            if response.status_code == 200:
                return response.json()
            logging.error(f"获取市场数据失败: {response.status_code}")
            return {}
        except Exception as e:
            logging.error(f"获取市场数据失败: {e}")
            return {}
            
    def fetch_preclose(self):
        """获取前收盘价"""
        try:
            response = requests.get(f"{self.market_data_url}/preclose")
            if response.status_code == 200:
                return response.json()
            logging.error(f"获取前收盘价失败: {response.status_code}")
            return {}
        except Exception as e:
            logging.error(f"获取前收盘价失败: {e}")
            return {}
            
    def fetch_stock_list(self):
        """获取股票列表"""
        try:
            response = requests.get(f"{self.market_data_url}/stock_list")
            if response.status_code == 200:
                return response.json()
            logging.error(f"获取股票列表失败: {response.status_code}")
            return []
        except Exception as e:
            logging.error(f"获取股票列表失败: {e}")
            return []

    def fetch_alerts(self):
        """获取异常提示"""
        try:
            response = requests.get(f"{self.market_data_url}/alerts/recent?minutes=30")
            if response.status_code == 200:
                return response.json()
            logging.error(f"获取异常提示失败: {response.status_code}")
            return []
        except Exception as e:
            logging.error(f"获取异常提示失败: {e}")
            return []

    def fetch_alert_stats(self):
        """获取异常统计"""
        try:
            response = requests.get(f"{self.market_data_url}/alerts/stats")
            if response.status_code == 200:
                return response.json()
            logging.error(f"获取异常统计失败: {response.status_code}")
            return {}
        except Exception as e:
            logging.error(f"获取异常统计失败: {e}")
            return {}

    def fetch_futures_alerts(self, minutes=30):
        """获取股指期货异常提示"""
        try:
            response = requests.get(f"{self.market_data_url}/futures/alerts/recent?minutes={minutes}")
            if response.status_code == 200:
                return response.json()
            logging.error(f"获取股指期货异常提示失败: {response.status_code}")
            return []
        except Exception as e:
            logging.error(f"获取股指期货异常提示失败: {e}")
            return []

    def fetch_futures_alert_stats(self):
        """获取股指期货异常统计"""
        try:
            response = requests.get(f"{self.market_data_url}/futures/alerts/stats")
            if response.status_code == 200:
                return response.json()
            logging.error(f"获取股指期货异常统计失败: {response.status_code}")
            return {}
        except Exception as e:
            logging.error(f"获取股指期货异常统计失败: {e}")
            return {}

    def upload_stock_list(self, file_content, filename):
        """上传股票列表文件"""
        try:
            files = {'file': (filename, file_content)}
            response = requests.post(f"{self.market_data_url}/set_stock_list", files=files)
            if response.status_code == 200:
                return True, response.json().get('message', '上传成功')
            return False, response.json().get('error', '上传失败')
        except Exception as e:
            logging.error(f"上传股票列表失败: {e}")
            return False, str(e) 