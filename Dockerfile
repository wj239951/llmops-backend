FROM python:3.11-slim

WORKDIR /app

# 先只拷依赖清单再安装：利用 Docker 层缓存，
# 只要 requirements.txt 不变，改业务代码时不会重装依赖，build 快很多。pip 装依赖时不去默认的 pypi.org，改从阿里云镜像下载
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt

# 再拷业务代码（.venv/.env/chroma_db 等由 .dockerignore 排除，不进镜像）
COPY . .

EXPOSE 8000

# 容器里必须监听 0.0.0.0（127.0.0.1 外面连不进来），且不开 reload（生产模式）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
