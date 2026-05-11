# 什么值得买好价监控系统

智能监控什么值得买好价商品，通过邮件提醒并支持用户反馈学习。

## ✨ 功能特性

- 🔄 **自动抓取** - 使用什么值得买API自动获取好价商品
- 📊 **智能评分** - 多维度评分算法（历史低价、评论增速、热度）
- 🎯 **精准过滤** - 黑名单/白名单规则，屏蔽低质商品
- 🛡️ **代理保护** - 代理IP池自动轮换，保护原始IP
- 📧 **邮件提醒** - HTML格式邮件，包含反馈按钮
- 📈 **反馈学习** - 根据用户反馈调整推荐权重
- ⚙️ **配置驱动** - 所有参数通过YAML配置，灵活可调

## 🚀 快速开始

### 1. 安装依赖

```bash
git clone https://github.com/liuyunss/smzdm-monitor.git
cd smzdm-monitor
pip install -r requirements.txt
```

### 2. 配置系统

编辑 `config.yaml`，填写邮箱配置：

```yaml
notifier:
  email:
    smtp_server: "smtp.qq.com"
    smtp_port: 587
    username: "your_email@qq.com"
    password: "your_auth_code"
    to_email: "target@email.com"
```

### 3. 运行监控

```bash
# 单次运行
python main.py --monitor

# 运行反馈服务
python main.py --feedback
```

### 4. 设置定时任务（可选）

```bash
crontab -e
# 添加：每30分钟运行一次
*/30 * * * * cd /opt/data/home/smzdm-monitor && python main.py --monitor >> logs/cron.log 2>&1
```

## 📊 评分算法

### 综合评分公式

```
总分 = 历史低价分 × 0.4 + 评论增速分 × 0.3 + 热度分 × 0.3
```

### 评分维度

| 维度 | 权重 | 说明 |
|------|------|------|
| 历史低价 | 40% | 当前价格与历史最低价的比较 |
| 评论增速 | 30% | 每小时评论数量增长速度 |
| 热度 | 30% | 综合评论、收藏、值/不值投票 |

### 过滤规则

- **黑名单关键词**：拼多多、百亿补贴等
- **黑名单店铺**：指定店铺屏蔽
- **白名单优先**：白名单商品不受黑名单影响

## 📁 项目结构

```
smzdm-monitor/
├── src/
│   ├── config/         # 配置加载模块
│   ├── storage/        # 数据库存储模块
│   ├── proxy/          # 代理管理模块
│   ├── crawler/        # 爬虫模块
│   ├── scorer/         # 评分算法模块
│   ├── notifier/       # 通知模块
│   └── feedback/       # 反馈服务模块
├── config.yaml         # 配置文件
├── main.py             # 主入口
└── requirements.txt    # 依赖
```

## 🔧 配置说明

### 监控设置

```yaml
monitor:
  interval: 1800           # 扫描间隔（秒）
  max_pages: 50            # 最大扫描页数
  max_history_hours: 24    # 扫描时间范围
```

### 评分权重

```yaml
scorer:
  weights:
    historical_low: 0.4    # 历史低价权重
    comment_growth: 0.3    # 评论增速权重
    popularity: 0.3        # 热度权重
```

### 代理配置

```yaml
proxy:
  enabled: true
  source: "free"           # 免费代理源
  rotation:
    on_request: true       # 每次请求轮换
    on_failure: true       # 失败自动切换
```

## 📝 数据字段

从什么值得买API获取的数据：

| 字段 | 说明 | 示例 |
|------|------|------|
| article_id | 商品ID | 12345678 |
| article_title | 商品标题 | "iPhone 15 128G" |
| article_price | 商品价格 | "5999" |
| article_mall | 店铺名称 | "京东" |
| article_worthy | 值投票 | 150 |
| article_unworthy | 不值投票 | 10 |
| article_comment | 评论数 | 89 |

## 🤝 反馈学习

系统支持用户反馈学习：

1. 邮件中包含反馈按钮（有用/没用/再提醒）
2. 用户点击后记录到数据库
3. 系统根据反馈调整评分权重
4. 个性化推荐更准确

## ⚠️ 注意事项

1. **邮箱配置**：需要开启SMTP服务并获取授权码
2. **代理质量**：免费代理不稳定，建议先测试可用性
3. **API限制**：什么值得买API可能有访问频率限制
4. **数据存储**：SQLite数据库文件在 `data/smzdm.db`

## 📄 License

MIT License

## 🔗 相关链接

- [什么值得买](https://www.smzdm.com/)
- [GitHub仓库](https://github.com/liuyunss/smzdm-monitor)
