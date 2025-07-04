"""
导入工具模块
用于处理项目路径和模块导入
"""

import os
import sys
from pathlib import Path


def setup_project_path():
    """
    设置项目根目录到Python路径
    确保无论从哪里运行都能正确导入项目模块
    """
    # 获取当前文件的目录
    current_file = Path(__file__).resolve()
    
    # 向上查找项目根目录（包含main.py的目录）
    project_root = current_file.parent.parent
    
    # 如果当前目录就是项目根目录，直接使用
    if (project_root / "main.py").exists():
        pass
    else:
        # 否则向上查找包含main.py的目录
        for parent in project_root.parents:
            if (parent / "main.py").exists():
                project_root = parent
                break
    
    # 将项目根目录添加到Python路径
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    return project_root


def get_project_root():
    """
    获取项目根目录
    """
    return setup_project_path()


# 在模块导入时自动设置路径
setup_project_path() 