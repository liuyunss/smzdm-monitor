"""
邮件通知模块
"""
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class EmailNotifier:
    """邮件通知器"""
    
    def __init__(self, config: Dict):
        self.config = config
        self._load_config()
    
    def _load_config(self):
        """加载邮件配置"""
        self.smtp_server = self.config.get('smtp_server', 'smtp.qq.com')
        self.smtp_port = self.config.get('smtp_port', 587)
        self.use_tls = self.config.get('use_tls', True)
        self.username = self.config.get('username', '')
        self.password = self.config.get('password', '')
        self.from_name = self.config.get('from_name', 'SRZDM监控')
        self.to_email = self.config.get('to_email', '')
    
    def send_notification(self, products: List[Dict], feedback_url: str = None) -> bool:
        """发送通知邮件"""
        if not products:
            return False
        
        # 构建邮件内容
        subject = f"【什么值得买】发现 {len(products)} 个好价商品 - {datetime.now().strftime('%Y-%m-%d')}"
        html_content = self._build_html(products, feedback_url)
        
        # 发送邮件
        return self._send_email(subject, html_content)
    
    def _build_html(self, products: List[Dict], feedback_url: str = None) -> str:
        """构建HTML邮件内容"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px 10px 0 0; }}
        .content {{ background: #f9f9f9; padding: 20px; }}
        .product {{ background: white; margin: 15px 0; padding: 15px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
        .product-title {{ font-size: 18px; font-weight: bold; color: #333; margin-bottom: 10px; }}
        .product-price {{ color: #e74c3c; font-size: 24px; font-weight: bold; }}
        .product-mall {{ color: #666; font-size: 14px; }}
        .product-stats {{ color: #888; font-size: 12px; margin-top: 10px; }}
        .product-link {{ display: inline-block; margin-top: 10px; padding: 8px 15px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; }}
        .product-link:hover {{ background: #5a6fd6; }}
        .feedback-buttons {{ margin-top: 10px; padding: 10px; background: #f0f0f0; border-radius: 5px; }}
        .feedback-btn {{ display: inline-block; padding: 5px 10px; margin: 0 5px; border-radius: 3px; text-decoration: none; font-size: 12px; }}
        .feedback-btn.helpful {{ background: #27ae60; color: white; }}
        .feedback-btn.not-helpful {{ background: #e74c3c; color: white; }}
        .feedback-btn.remind {{ background: #f39c12; color: white; }}
        .footer {{ text-align: center; padding: 20px; color: #888; font-size: 12px; }}
        .score {{ display: inline-block; padding: 3px 8px; border-radius: 3px; font-size: 12px; font-weight: bold; }}
        .score-high {{ background: #27ae60; color: white; }}
        .score-medium {{ background: #f39c12; color: white; }}
        .score-low {{ background: #e74c3c; color: white; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎯 什么值得买好价提醒</h1>
            <p>发现 {len(products)} 个优质好价商品</p>
        </div>
        <div class="content">
"""
        
        # 添加商品列表
        for i, product in enumerate(products, 1):
            score = product.get('score', 0)
            score_class = 'score-high' if score >= 70 else 'score-medium' if score >= 40 else 'score-low'
            
            # 构建反馈按钮URL
            feedback_buttons = ""
            if feedback_url:
                product_id = product.get('id', '')
                feedback_buttons = f"""
                <div class="feedback-buttons">
                    <span>这个推荐对你有用吗？</span>
                    <a href="{feedback_url}/feedback?product_id={product_id}&type=helpful" class="feedback-btn helpful">👍 有用</a>
                    <a href="{feedback_url}/feedback?product_id={product_id}&type=not_helpful" class="feedback-btn not-helpful">👎 没用</a>
                    <a href="{feedback_url}/feedback?product_id={product_id}&type=remind" class="feedback-btn remind">⏰ 再提醒</a>
                </div>
"""
            
            html += f"""
            <div class="product">
                <div class="product-title">
                    <span class="score {score_class}">评分 {score}</span>
                    {product.get('title', '未知商品')}
                </div>
                <div class="product-price">💰 {product.get('price', '未知')}</div>
                <div class="product-mall">🏪 {product.get('mall', '未知')}</div>
                <div class="product-stats">
                    👍 {product.get('worthy', 0)} 值 | 👎 {product.get('unworthy', 0)} 不值 | 💬 {product.get('comments', 0)} 评论 | ⭐ {product.get('collection', 0)} 收藏
                </div>
                <a href="{product.get('url', '#')}" class="product-link" target="_blank">🔗 查看详情</a>
                {feedback_buttons}
            </div>
"""
        
        # 添加页脚
        html += f"""
        </div>
        <div class="footer">
            <p>📊 本邮件由什么值得买好价监控系统自动发送</p>
            <p>⏰ 发送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </div>
</body>
</html>
"""
        
        return html
    
    def _send_email(self, subject: str, html_content: str) -> bool:
        """发送邮件"""
        if not self.username or not self.password or not self.to_email:
            logger.warning("邮件配置不完整，跳过发送")
            return False
        
        try:
            # 创建邮件
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.username
            msg['To'] = self.to_email
            
            # 添加HTML内容
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)
            
            # 连接SMTP服务器
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            if self.use_tls:
                server.starttls()
            
            # 登录
            server.login(self.username, self.password)
            
            # 发送
            server.sendmail(self.username, [self.to_email], msg.as_string())
            
            # 关闭连接
            server.quit()
            
            logger.info(f"邮件发送成功: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            return False

# 全局通知器实例
_notifier_instance = None

def get_notifier(config: Dict) -> EmailNotifier:
    """获取全局通知器"""
    global _notifier_instance
    if _notifier_instance is None:
        _notifier_instance = EmailNotifier(config)
    return _notifier_instance
