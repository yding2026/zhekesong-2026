FROM python:3.12-slim-bookworm

# ima 官方脚本是 Node 程序，镜像里要带上 Node.js 18。
RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

# 魔搭 docker 创空间要求服务监听 7860，并且不能只绑在容器内部的回环地址。
ENV HOST=0.0.0.0
ENV PORT=7860
EXPOSE 7860

CMD ["python", "agent/server.py"]
