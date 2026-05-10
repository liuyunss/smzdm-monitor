#!/usr/bin/env python3
"""
项目结构测试脚本
"""
import os
import sys

def test_structure():
    """测试项目结构"""
    print("🔍 测试项目结构...")
    
    # 检查目录结构
    required_dirs = [
        'src/config',
        'src/storage',
        'src/proxy',
        'src/crawler',
        'src/scorer',
        'src/notifier',
        'src/feedback',
        'data',
        'logs',
        'templates'
    ]
    
    for dir_path in required_dirs:
        if os.path.exists(dir_path):
            print(f"✅ {dir_path}")
        else:
            print(f"❌ {dir_path} 不存在")
    
    # 检查文件
    required_files = [
        'main.py',
        'config.yaml',
        'requirements.txt',
        'README.md',
        'src/config/loader.py',
        'src/storage/database.py',
        'src/proxy/manager.py',
        'src/crawler/smzdm.py',
        'src/scorer/algorithm.py',
        'src/notifier/email.py',
        'src/feedback/service.py'
    ]
    
    print("\n📄 测试文件...")
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} 不存在")

def test_imports():
    """测试模块导入"""
    print("\n📦 测试模块导入...")
    
    try:
        from src.config.loader import get_config
        print("✅ config.loader")
    except Exception as e:
        print(f"❌ config.loader: {e}")
    
    try:
        from src.storage.database import get_db
        print("✅ storage.database")
    except Exception as e:
        print(f"❌ storage.database: {e}")
    
    try:
        from src.proxy.manager import get_proxy_manager
        print("✅ proxy.manager")
    except Exception as e:
        print(f"❌ proxy.manager: {e}")
    
    try:
        from src.crawler.smzdm import get_crawler
        print("✅ crawler.smzdm")
    except Exception as e:
        print(f"❌ crawler.smzdm: {e}")
    
    try:
        from src.scorer.algorithm import get_scorer
        print("✅ scorer.algorithm")
    except Exception as e:
        print(f"❌ scorer.algorithm: {e}")
    
    try:
        from src.notifier.email import get_notifier
        print("✅ notifier.email")
    except Exception as e:
        print(f"❌ notifier.email: {e}")
    
    try:
        from src.feedback.service import get_feedback_service
        print("✅ feedback.service")
    except Exception as e:
        print(f"❌ feedback.service: {e}")

if __name__ == '__main__':
    # 切换到项目目录
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    print("=" * 50)
    print("什么值得买好价监控系统 - 项目测试")
    print("=" * 50)
    
    test_structure()
    test_imports()
    
    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)
