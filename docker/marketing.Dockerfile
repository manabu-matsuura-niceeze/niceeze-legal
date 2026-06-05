FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir python-docx python-pptx
COPY src/marketing/ ./src/marketing/
COPY src/notifications/ ./src/notifications/
ENV PYTHONPATH=/app
EXPOSE 8081
CMD ["python3", "src/marketing/api.py"]
