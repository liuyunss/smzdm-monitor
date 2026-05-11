FROM python:3.11-slim

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev && \
    rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 代码
COPY . .

# 数据目录
RUN mkdir -p /app/data /app/logs

# 环境变量默认值
ENV SMTP_USERNAME=""
ENV SMTP_PASSWORD=""
ENV SMTP_TO=""

EXPOSE 5000

CMD ["python3", "main.py", "--daemon"]
