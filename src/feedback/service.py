"""
反馈服务模块
"""
import logging
from typing import Dict
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string

logger = logging.getLogger(__name__)

class FeedbackService:
    """反馈服务"""
    
    def __init__(self, config: Dict, database=None):
        self.config = config
        self.database = database
        self.app = Flask(__name__)
        self._setup_routes()
    
    def _setup_routes(self):
        """设置路由"""
        
        @self.app.route('/feedback', methods=['GET'])
        def feedback_page():
            """反馈页面"""
            product_id = request.args.get('product_id')
            feedback_type = request.args.get('type')
            
            if not product_id or not feedback_type:
                return "缺少参数", 400
            
            # 保存反馈
            if self.database:
                self.database.save_feedback(product_id, feedback_type)
            
            # 返回感谢页面
            return render_template_string(THANK_YOU_TEMPLATE, 
                                        product_id=product_id,
                                        feedback_type=feedback_type)
        
        @self.app.route('/api/feedback', methods=['POST'])
        def api_feedback():
            """API反馈接口"""
            data = request.get_json()
            
            if not data:
                return jsonify({'error': '无效数据'}), 400
            
            product_id = data.get('product_id')
            feedback_type = data.get('type')
            category = data.get('category')
            
            if not product_id or not feedback_type:
                return jsonify({'error': '缺少必要参数'}), 400
            
            # 保存反馈
            if self.database:
                self.database.save_feedback(product_id, feedback_type, category)
            
            return jsonify({'message': '反馈已记录'})
        
        @self.app.route('/api/stats', methods=['GET'])
        def api_stats():
            """获取反馈统计"""
            if not self.database:
                return jsonify({'error': '数据库未初始化'}), 500
            
            category = request.args.get('category')
            stats = self.database.get_feedback_stats(category)
            
            return jsonify(stats)
    
    def start(self, host: str = '0.0.0.0', port: int = 5000):
        """启动反馈服务"""
        self.app.run(host=host, port=port, debug=False)

# 感谢页面模板
THANK_YOU_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>感谢反馈</title>
    <style>
        body { font-family: Arial, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: #f0f0f0; }
        .card { background: white; padding: 40px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; max-width: 400px; }
        .icon { font-size: 48px; margin-bottom: 20px; }
        .title { font-size: 24px; color: #333; margin-bottom: 10px; }
        .message { color: #666; margin-bottom: 20px; }
        .button { display: inline-block; padding: 10px 20px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; }
        .button:hover { background: #5a6fd6; }
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">✅</div>
        <div class="title">感谢您的反馈！</div>
        <div class="message">
            您的反馈对我们非常重要，它将帮助我们改进推荐算法。
        </div>
        <div class="message" style="font-size: 14px; color: #888;">
            商品ID: {{ product_id }}<br>
            反馈类型: {{ feedback_type }}
        </div>
        <a href="javascript:window.close()" class="button">关闭页面</a>
    </div>
</body>
</html>
"""

# 全局反馈服务实例
_feedback_service_instance = None

def get_feedback_service(config: Dict, database=None) -> FeedbackService:
    """获取全局反馈服务"""
    global _feedback_service_instance
    if _feedback_service_instance is None:
        _feedback_service_instance = FeedbackService(config, database)
    return _feedback_service_instance
