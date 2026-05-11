"""
邮件通知模块
"""
import smtplib
import json
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# 最近一次发送的商品列表（用于解析自由回复中的编号）
LAST_SENT_FILE = './data/last_sent_products.json'


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
        
        subject = f"【SMZDM好价】{len(products)} 个热门商品 - {datetime.now().strftime('%m-%d %H:%M')}"
        html_content = self._build_html(products, feedback_email)
        
        # 保存商品列表（用于自由回复解析）
        self._save_last_sent(products)
        
        return self._send_email(subject, html_content)
    
    def _save_last_sent(self, products: List[Dict]):
        """保存最近发送的商品列表"""
        import os
        os.makedirs('./data', exist_ok=True)
        data = [{
            'id': p.get('id', ''),
            'title': p.get('title', ''),
        } for p in products]
        with open(LAST_SENT_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _build_html(self, products: List[Dict], feedback_email: str = None) -> str:
        """构建HTML邮件内容"""
        all_ids = ','.join([p.get('id', '') for p in products])
        
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

        .feedback-box {{ background: #f8f9fa; border: 2px solid #e9ecef; border-radius: 12px; padding: 24px; margin-top: 24px; }}
        .feedback-box h3 {{ margin: 0 0 8px 0; font-size: 16px; color: #333; text-align: center; }}
        .feedback-box > p {{ margin: 0 0 16px 0; font-size: 13px; color: #666; text-align: center; }}
        .feedback-batch {{ display: flex; justify-content: center; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; }}
        .fb {{ display: inline-block; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-size: 13px; font-weight: 600; }}
        .fb-good {{ background: #27ae60; color: white; }}
        .fb-bad {{ background: #e74c3c; color: white; }}
        
        .feedback-detail {{ border-top: 1px solid #dee2e6; padding-top: 16px; }}
        .feedback-detail p {{ margin: 0 0 8px 0; font-size: 13px; color: #666; }}
        .feedback-detail ol {{ margin: 0 0 12px 0; padding-left: 20px; font-size: 13px; color: #333; }}
        .feedback-detail li {{ margin-bottom: 4px; }}
        .fb-reply {{ display: inline-block; padding: 10px 20px; background: #6c757d; color: white; text-decoration: none; border-radius: 8px; font-size: 13px; font-weight: 600; }}

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
        
        # 商品列表（带编号）
        for i, product in enumerate(products, 1):
            score = product.get('score', 0)
            score_class = 'score-high' if score >= 70 else 'score-medium' if score >= 40 else 'score-low'
            
            html += f"""
            <div class="product">
                <div class="product-num">{i}</div>
                <div class="product-body">
                    <div class="product-title">
                        {product.get('title', '未知商品')}
                        <span class="score {score_class}">{score:.0f}分</span>
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
        
        # 底部反馈区
        if feedback_email:
            mapping_lines = ''.join([
                f'<li><b>{i}</b>. {p.get("title", "?")}</li>'
                for i, p in enumerate(products, 1)
            ])
            
            # 回复模板：用户只需填写编号，body 里带标题映射
            reply_body_lines = [f'{i}. {p.get("title", "?")}' for i, p in enumerate(products, 1)]
            reply_body = '%0A'.join(reply_body_lines) + '%0A%0A好评：' + ','.join(str(i) for i in range(1, len(products)+1)) + '%0A差评：'
            
            html += f"""
        </div>
        <div class="feedback-box">
            <h3>📧 这批推荐怎么样？</h3>
            <p>整体反馈点下面，具体反馈往下翻</p>
            
            <div class="feedback-batch">
                <a href="mailto:{feedback_email}?subject=feedback:batch:{all_ids}:good&body=这批推荐不错" class="fb fb-good">👍 都不错</a>
                <a href="mailto:{feedback_email}?subject=feedback:batch:{all_ids}:bad&body=这批推荐不行" class="fb fb-bad">👎 都不行</a>
            </div>
            
            <div class="feedback-detail">
                <p><b>📝 具体反馈</b> — 点击下方按钮，编辑编号后发送：</p>
                <ol>{mapping_lines}</ol>
                <p>回复格式：<code>好评 1,3,5</code> &nbsp; <code>差评 2,4</code></p>
                <a href="mailto:{feedback_email}?subject=feedback:detail:{all_ids}&body={reply_body}" class="fb-reply">✏️ 回复反馈</a>
            </div>
        </div>
"""
        else:
            html += "</div>"
        
        html += f"""
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
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.username
            msg['To'] = self.to_email
            
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)
            
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            if self.use_tls:
                server.starttls()
            server.login(self.username, self.password)
            server.sendmail(self.username, [self.to_email], msg.as_string())
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
