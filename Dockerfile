FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY templates ./templates
COPY static ./static
ENV DATA_DIR=/tmp/wanxiang_data
ENV UPLOAD_DIR=/tmp/wanxiang_uploads
ENV PORT=5000
CMD ["python", "app.py"]
