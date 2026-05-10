# 什么值得买好价监控系统

智能监控什么值得买好价商品，通过邮件提醒并支持用户反馈学习。

## 功能特性
- 🔄 自动抓取好价商品数据
- 📊 多维度智能评分（历史低价、评论增速、热度）
- 📧 邮件合并提醒（含反馈按钮）
- 🎯 黑名单/过滤规则（支持商品ID、关键词、店铺、品类）
- 📈 用户反馈学习（根据反馈调整评分权重）
- 🛡️ 代理IP池保护（自动轮换、定期验证）
- ⚙️ 配置驱动（所有参数通过YAML配置）

## 项目结构
```
srzdm-monitor/
├── src/
│   ├── crawler/          # 爬虫模块
│   ├── proxy/            # 代理管理模块
│   ├── scorer/           # 评分算法模块
│   ├── storage/          # 数据库存储模块
│   ├── notifier/         # 邮件通知模块
│   ├── feedback/         # 反馈服务模块
│   └── config/           # 配置加载模块
├── data/                 # SQLite数据库
├── logs/                 # 日志文件
├── templates/            # 邮件模板
├── config.yaml           # 配置文件
├── main.py               # 主程序入口
└── requirements.txt      # 依赖
```

## 快速开始
1. 安装依赖：`pip install -r requirements.txt`
2. 配置：编辑 `config.yaml`
3. 运行：`python main.py`

## 定时任务
使用 cron 定时执行：
```bash
*/30 * * * * cd /opt/data/home/srzdm-monitor && python main.py >> logs/cron.log 2>&1
```
