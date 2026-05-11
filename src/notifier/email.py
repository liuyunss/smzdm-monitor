"""
邮件通知模块
"""
import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


class EmailNotifier:
    """邮件通知器"""
    
    def __init__(self, config: Dict):
        self.config = config
        self._load_config()
    
    def _load_config(self):
        self.smtp_server = self.config.get('smtp_server', 'smtp.qq.com')
        self.smtp_port = self.config.get('smtp_port', 587)
        self.use_tls = self.config.get('use_tls', True)
        # 优先读环境变量（Docker/.env），再读配置文件
        self.username = os.environ.get('SMTP_USERNAME') or self.config.get('username', '')
        self.password = os.environ.get('SMTP_PASSWORD') or self.config.get('password', '')
        self.to_email = os.environ.get('SMTP_TO') or self.config.get('to_email', '')
    
    def send_notification(self, products: List[Dict]) -> bool:
        if not products:
            return False
        
        # 主题：简洁格式
        subject = f"【SMZDM好价】{len(products)}件好价 - {datetime.now().strftime('%m-%d %H:%M')}"
        
        html_content = self._build_html(products)
        return self._send_email(subject, html_content)
    
    def _build_html(self, products: List[Dict]) -> str:
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
        .product {{ border-bottom: 1px solid #eee; padding: 14px 0; display: flex; gap: 12px; }}
        .product:last-child {{ border-bottom: none; }}
        .product-num {{ background: #667eea; color: white; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: bold; flex-shrink: 0; }}
        .product-body {{ flex: 1; }}
        .product-title {{ font-size: 15px; font-weight: 600; color: #333; }}
        .product-meta {{ display: flex; gap: 16px; margin-top: 6px; font-size: 13px; }}
        .product-price {{ color: #e74c3c; font-weight: bold; }}
        .product-mall {{ color: #666; }}
        .product-stats {{ color: #888; font-size: 12px; margin-top: 4px; }}
        .product-link {{ display: inline-block; margin-top: 8px; padding: 6px 14px; background: #667eea; color: white; text-decoration: none; border-radius: 6px; font-size: 12px; }}
        .score {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; margin-left: 8px; }}
        .score-high {{ background: #27ae60; color: white; }}
        .score-medium {{ background: #f39c12; color: white; }}
        .score-low {{ background: #95a5a6; color: white; }}
        .category {{ display: inline-block; padding: 1px 6px; background: #e9ecef; color: #666; border-radius: 3px; font-size: 11px; margin-left: 6px; }}

        .guide {{ background: #f8f9fa; border: 2px solid #e9ecef; border-radius: 12px; padding: 24px; margin-top: 24px; }}
        .guide h3 {{ margin: 0 0 16px 0; font-size: 16px; color: #333; }}
        .guide-section {{ margin-bottom: 16px; }}
        .guide-section h4 {{ margin: 0 0 8px 0; font-size: 14px; color: #555; }}
        .guide-section p {{ margin: 0 0 8px 0; font-size: 13px; color: #666; }}
        .guide-section code {{ background: #e9ecef; padding: 2px 6px; border-radius: 3px; font-size: 12px; }}
        .guide-example {{ background: white; border: 1px solid #dee2e6; border-radius: 6px; padding: 12px; margin: 8px 0; font-size: 13px; color: #333; font-family: 'SF Mono', Monaco, monospace; white-space: pre-wrap; }}
        .guide-tip {{ background: #fff3cd; border: 1px solid #ffc107; border-radius: 6px; padding: 10px 12px; margin-top: 12px; font-size: 12px; color: #856404; }}

        .footer {{ text-align: center; padding: 20px; color: #999; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎯 什么值得买好价提醒</h1>
            <p>发现 {len(products)} 个高互动热门商品</p>
        </div>
        <div class="content">
"""
        
        for i, product in enumerate(products, 1):
            score = product.get('score', 0)
            score_class = 'score-high' if score >= 70 else 'score-medium' if score >= 40 else 'score-low'
            category = product.get('category', '')
            category_html = f'<span class="category">{category}</span>' if category else ''
            
            html += f"""
            <div class="product">
                <div class="product-num">{i}</div>
                <div class="product-body">
                    <div class="product-title">
                        {product.get('title', '未知商品')}
                        <span class="score {score_class}">{score:.0f}分</span>
                        {category_html}
                    </div>
                    <div class="product-meta">
                        <span class="product-price">💰 {product.get('price', '未知')}</span>
                        <span class="product-mall">🏪 {product.get('mall', '未知')}</span>
                    </div>
                    <div class="product-stats">
                        👍 {product.get('worthy', 0)} 值 &nbsp; 👎 {product.get('unworthy', 0)} 不值 &nbsp; 💬 {product.get('comments', 0)} 评论
                    </div>
                    <a href="{product.get('url', '#')}" class="product-link" target="_blank">查看详情 →</a>
                </div>
            </div>
"""
        
        html += f"""
        </div>
        <div class="guide">
            <h3>📬 如何使用</h3>
            
            <div class="guide-section">
                <h4>1. 商品反馈</h4>
                <p>回复此邮件，正文写上编号即可：</p>
                <div class="guide-example">好评 1,2,5
差评 3,4</div>
                <p>支持范围写法：</p>
                <div class="guide-example">好评 1-5
差评 6-10
好评 1-3,8,10-15</div>
            </div>
            
            <div class="guide-section">
                <h4>2. 设置品类偏好</h4>
                <p>通过邮件调整推荐权重，系统会自动学习：</p>
                <div class="guide-example">设置：母婴 -100
设置：数码 +50
设置：零食 0</div>
                <p>值范围 <code>-100</code> 到 <code>+100</code>，负数降权，正数加权</p>
            </div>
            
            <div class="guide-section">
                <h4>3. 组合使用</h4>
                <p>一封邮件可以同时反馈商品 + 调整偏好：</p>
                <div class="guide-example">好评 1-3
差评 4-5
设置：母婴 -100
设置：数码 +30</div>
            </div>
            
            <div class="guide-tip">
                💡 系统会根据你的反馈自动学习品类偏好，反馈越多推荐越精准
            </div>
        </div>
        <div class="footer">
            <p>📊 由 SMZDM 好价监控系统自动发送 | {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
            <p style="color:#ccc;font-size:10px;">商品编号: {','.join(f'{i}:{p.get("id","?")}' for i, p in enumerate(products, 1))}</p>
        </div>
    </div>
</body>
</html>
"""
        
        return html
    
    def _send_email(self, subject: str, html_content: str) -> bool:
        if not self.username or not self.password or not self.to_email:
            logger.error("邮件配置不完整，跳过发送")
            return False
        
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.username
            msg['To'] = self.to_email
            
            msg.attach(MIMEText(html_content, 'html', 'utf-8'))
            
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            if self.use_tls:
                server.starttls()
            server.login(self.username, self.password)
            server.sendmail(self.username, [self.to_email], msg.as_string())
            server.quit()
            
            logger.info(f"邮件发送成功: {len(subject)} 字符")
            return True
            
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            return False



