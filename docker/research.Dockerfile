FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir python-docx python-pptx
COPY src/research/ ./src/research/
COPY src/notifications/ ./src/notifications/
ENV PYTHONPATH=/app
EXPOSE 8080
CMD ["python3", "src/research/api.py"]
