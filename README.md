# 什么值得买好价监控

监控什么值得买好价频道，评分过滤后邮件推送，支持邮件回复反馈调整品类偏好。

## 功能

- API 抓取好价商品，动态翻页覆盖指定时间段
- 绝对互动量评分 + 品类偏好加权
- 邮件推送，免打扰时段攒数据批量发
- 邮件回复反馈（好评/差评/跳过），学习品类偏好
- 去重推送，同一商品最多推 2 次

## 快速开始

```bash
git clone https://github.com/liuyunss/smzdm-monitor.git
cd smzdm-monitor
pip install -r requirements.txt

cp config.yaml.example config.yaml
cp .env.example .env
# 编辑 .env 填写邮箱授权码
```

### 运行

```bash
# 前台单次运行
python main.py

# 后台持续运行（默认 5 分钟一轮）
python main.py --daemon
```

### Docker

```bash
docker compose up -d
```

`config.yaml` 和 `.env` 已挂载为外部卷，可随时修改后重启生效。

## 配置

### .env（敏感信息，不提交 Git）

```env
SMTP_USERNAME=809153781@qq.com
SMTP_PASSWORD=你的授权码
SMTP_TO=809153781@qq.com
```

### config.yaml（从 example 复制）

```yaml
monitor:
  interval: 300            # 扫描间隔（秒）
  items_per_page: 20       # 每页条数
  max_pages: 50            # 最大翻页数
  target_minutes: 30       # 动态翻页目标覆盖时间
  quiet_hours:             # 免打扰（北京时间）
    enabled: false
    start: '00:30'
    end: '07:30'

scorer:
  min_age_hours: 1
  min_composite_score: 50  # 低于此分不推送
  weights:
    comments: 0.1          # 评论权重低（很多是空的）
    collection: 3          # 收藏
    worthy: 1.5            # 值
    unworthy: -2           # 不值（一个不值抵消一个值+）
    price: 0.15            # 价格优势

notifier:
  email:
    from_name: SMZDM监控
    smtp_server: smtp.qq.com
    smtp_port: 587
    use_tls: true
    username: 809153781@qq.com
    to_email: 809153781@qq.com
```

## 评分逻辑

```
score = log1p(comments×0.1 + collection×3 + worthy×1.5 + unworthy×(-2)) × 14
      + 价格优势分 × 0.15
      × 品类偏好权重（0.3~1.5）
```

推送门槛：
- 收藏+值 ≥ 15
- 值 ≥ 收藏 且 值 ≥ 评论
- 综合分 ≥ 50
- 同一商品最多推 2 次，第二次需分数增长 ≥ 10

## 邮件反馈

邮件标题包含商品编号（如 `1:400001,2:400002`），回复邮件时在正文写：

- `1` 或 `1值` — 好评（品类权重 +0.3）
- `1差` — 差评（品类权重 -0.3）
- `1跳` — 跳过（不调整）
- `set 科技 1.2` — 手动设置品类权重
- `prefs` — 查看当前偏好

系统每 5 分钟检查邮箱，解析回复并更新品类偏好。

## 项目结构

```
smzdm-monitor/
├── main.py                 # 主入口
├── config.yaml.example     # 配置模板
├── .env.example            # 环境变量模板
├── docker-compose.yml      # Docker 部署
├── Dockerfile
├── requirements.txt
├── scripts/
│   └── cleanup.py          # 数据清理（30天保留）
├── export_prefs.py         # 导出品类偏好为 JSON
└── src/
    ├── config/loader.py    # YAML + 环境变量加载
    ├── crawler/smzdm.py    # SMZDM API 爬虫
    ├── scorer/
    │   ├── algorithm.py    # 评分算法
    │   ├── category.py     # 品类标签（12类）
    │   └── preference.py   # 品类偏好学习
    ├── storage/database.py # SQLite 存储
    ├── notifier/email.py   # 邮件推送
    ├── feedback/parser.py  # IMAP 反馈解析
    └── proxy/manager.py    # 代理管理（暂未启用）
```

## 安全

- `.env` 和 `config.yaml` 在 `.gitignore` 中，不会提交
- 凭据通过环境变量注入，`config.yaml` 不含密码
- `data/` 和 `logs/` 目录不提交

## License

MIT
