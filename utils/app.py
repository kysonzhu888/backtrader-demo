from flask import Flask
import os
from werkzeug.utils import secure_filename

# 创建共享的Flask应用实例
app = Flask(__name__)

# 配置上传文件存储路径
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'csv', 'xls', 'xlsx'}

# 确保上传目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_app():
    """获取Flask应用实例"""
    return app

def register_blueprint(blueprint):
    """注册蓝图"""
    app.register_blueprint(blueprint)

def run_app(host=None, port=None, debug=False):
    """运行Flask应用"""
    app.run(host=host, port=port, debug=debug) 