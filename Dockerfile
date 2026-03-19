FROM python:3.11-slim

WORKDIR /app

# 安裝依賴
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製程式碼
COPY monitor.py .

EXPOSE 80

# 執行監測器
CMD ["python", "monitor.py"]
