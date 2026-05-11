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
        self.from_name = self.config.get('from_name', 'SMZDM监控')
        self.to_email = self.config.get('to_email', '')
    
    def send_notification(self, products: List[Dict], feedback_email: str = None) -> bool:
        """发送通知邮件"""
        if not products:
            return False
        
        # 构建邮件内容
        subject = f"【SMZDM好价】{len(products)} 个热门商品 - {datetime.now().strftime('%m-%d %H:%M')}"
        html_content = self._build_html(products, feedback_email)
        
        # 发送邮件
        return self._send_email(subject, html_content)
    
    def _build_html(self, products: List[Dict], feedback_email: str = None) -> str:
        """构建HTML邮件内容"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background: #f5f5f5; }}
        .container {{ max-width: 700px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 24px; border-radius: 12px 12px 0 0; }}
        .header h1 {{ margin: 0 0 8px 0; font-size: 22px; }}
        .header p {{ margin: 0; opacity: 0.9; font-size: 14px; }}
        .content {{ background: white; padding: 20px; border-radius: 0 0 12px 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .product {{ border-bottom: 1px solid #eee; padding: 16px 0; }}
        .product:last-child {{ border-bottom: none; }}
        .product-header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; }}
        .product-title {{ font-size: 16px; font-weight: 600; color: #333; flex: 1; }}
        .score {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; margin-left: 8px; }}
        .score-high {{ background: #27ae60; color: white; }}
        .score-medium {{ background: #f39c12; color: white; }}
        .score-low {{ background: #95a5a6; color: white; }}
        .product-price {{ color: #e74c3c; font-size: 20px; font-weight: bold; margin: 4px 0; }}
        .product-mall {{ color: #666; font-size: 13px; }}
        .product-stats {{ color: #888; font-size: 12px; margin-top: 8px; }}
        .product-stats span {{ margin-right: 12px; }}
        .product-link {{ display: inline-block; margin-top: 10px; padding: 8px 16px; background: #667eea; color: white; text-decoration: none; border-radius: 6px; font-size: 13px; }}
        .product-link:hover {{ background: #5a6fd6; }}
        .feedback-section {{ margin-top: 12px; padding: 12px; background: #f8f9fa; border-radius: 8px; }}
        .feedback-label {{ font-size: 13px; color: #666; margin-bottom: 8px; }}
        .feedback-btn {{ display: inline-block; padding: 6px 14px; margin: 0 4px; border-radius: 6px; text-decoration: none; font-size: 13px; font-weight: 500; }}
        .feedback-btn.helpful {{ background: #27ae60; color: white; }}
        .feedback-btn.not-helpful {{ background: #e74c3c; color: white; }}
        .feedback-btn.remind {{ background: #f39c12; color: white; }}
        .footer {{ text-align: center; padding: 20px; color: #999; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎯 什么值得买好价提醒</h1>
            <p>发现 {len(products)} 个互动增长热门商品</p>
        </div>
        <div class="content">
"""
        
        # 添加商品列表
        for i, product in enumerate(products, 1):
            score = product.get('score', 0)
            score_class = 'score-high' if score >= 70 else 'score-medium' if score >= 40 else 'score-low'
            
            # 构建反馈按钮（mailto 方式）
            feedback_buttons = ""
            if feedback_email:
                pid = product.get('id', '')
                title = product.get('title', '')[:20]
                feedback_buttons = f"""
                <div class="feedback-section">
                    <div class="feedback-label">这个推荐对你有用吗？</div>
                    <a href="mailto:{feedback_email}?subject=feedback:{pid}:helpful&body=商品:{title}" class="feedback-btn helpful">👍 有用</a>
                    <a href="mailto:{feedback_email}?subject=feedback:{pid}:not_helpful&body=商品:{title}" class="feedback-btn not-helpful">👎 没用</a>
                    <a href="mailto:{feedback_email}?subject=feedback:{pid}:remind&body=商品:{title}" class="feedback-btn remind">⏰ 再提醒</a>
                </div>
"""
            
            html += f"""
            <div class="product">
                <div class="product-header">
                    <div class="product-title">
                        {product.get('title', '未知商品')}
                        <span class="score {score_class}">{score:.0f}分</span>
                    </div>
                </div>
                <div class="product-price">💰 {product.get('price', '未知')}</div>
                <div class="product-mall">🏪 {product.get('mall', '未知')}</div>
                <div class="product-stats">
                    <span>👍 {product.get('worthy', 0)} 值</span>
                    <span>👎 {product.get('unworthy', 0)} 不值</span>
                    <span>💬 {product.get('comments', 0)} 评论</span>
                    <span>⭐ {product.get('collection', 0)} 收藏</span>
                </div>
                <a href="{product.get('url', '#')}" class="product-link" target="_blank">🔗 查看详情</a>
                {feedback_buttons}
            </div>
"""
        
        # 添加页脚
        html += f"""
        </div>
        <div class="footer">
            <p>📊 由 SMZDM 好价监控系统自动发送 | {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
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
