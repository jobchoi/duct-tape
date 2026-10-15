FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY Server/requirements.txt /app/Server/requirements.txt
RUN pip install --no-cache-dir -r Server/requirements.txt
COPY Server /app/Server
COPY Scripts /app/Scripts
COPY Modules /app/Modules
COPY Config/Applications.json /app/Config/Applications.json
COPY Main.bat InstallAgent.bat /app/
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "Server.server:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
