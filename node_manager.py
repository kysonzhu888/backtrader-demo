import os
import json
import logging
import threading
import time
from datetime import datetime
from flask import Flask, request, jsonify
import requests
from environment import (
    MACHINE_ID, IS_MASTER, MASTER_HOST, 
    MASTER_PORT, SHARED_STORAGE_PATH
)

class NodeManager:
    def __init__(self):
        self.node_id = MACHINE_ID
        self.is_master = IS_MASTER
        self.active_nodes = {}  # 活跃节点列表
        self.last_heartbeat = {}  # 最后心跳时间
        self.app = Flask(__name__)
        self._setup_routes()
        
        # 确保共享存储目录存在
        os.makedirs(SHARED_STORAGE_PATH, exist_ok=True)
        
        # 启动心跳检测
        if self.is_master:
            threading.Thread(target=self._check_nodes_health, daemon=True).start()
        else:
            threading.Thread(target=self._send_heartbeat, daemon=True).start()

    def _setup_routes(self):
        """设置API路由"""
        @self.app.route('/heartbeat', methods=['POST'])
        def heartbeat():
            data = request.json
            node_id = data.get('node_id')
            if node_id:
                self.active_nodes[node_id] = data
                self.last_heartbeat[node_id] = datetime.now()
                return jsonify({"status": "ok"})
            return jsonify({"status": "error", "message": "Invalid node_id"}), 400

        @self.app.route('/nodes', methods=['GET'])
        def get_nodes():
            return jsonify(self.active_nodes)

    def _send_heartbeat(self):
        """发送心跳到主节点"""
        while True:
            try:
                data = {
                    "node_id": self.node_id,
                    "timestamp": datetime.now().isoformat(),
                    "status": "active"
                }
                url = f"http://{MASTER_HOST}:{MASTER_PORT}/heartbeat"
                requests.post(url, json=data, timeout=5)
            except Exception as e:
                logging.error(f"发送心跳失败: {e}")
            time.sleep(30)  # 30秒发送一次心跳

    def _check_nodes_health(self):
        """检查节点健康状态"""
        while True:
            now = datetime.now()
            dead_nodes = []
            for node_id, last_time in self.last_heartbeat.items():
                if (now - last_time).total_seconds() > 90:  # 90秒无心跳视为离线
                    dead_nodes.append(node_id)
            
            for node_id in dead_nodes:
                logging.warning(f"节点 {node_id} 已离线")
                self.active_nodes.pop(node_id, None)
                self.last_heartbeat.pop(node_id, None)
            
            time.sleep(30)

    def start(self):
        """启动节点管理器"""
        if self.is_master:
            self.app.run(host='0.0.0.0', port=MASTER_PORT)
        else:
            # 从节点先注册到主节点
            self._send_heartbeat()

    def get_active_nodes(self):
        """获取活跃节点列表"""
        if self.is_master:
            return list(self.active_nodes.keys())
        else:
            try:
                url = f"http://{MASTER_HOST}:{MASTER_PORT}/nodes"
                response = requests.get(url, timeout=5)
                return list(response.json().keys())
            except Exception as e:
                logging.error(f"获取节点列表失败: {e}")
                return []

    def is_node_active(self, node_id):
        """检查节点是否活跃"""
        if self.is_master:
            return node_id in self.active_nodes
        else:
            try:
                nodes = self.get_active_nodes()
                return node_id in nodes
            except Exception:
                return False 