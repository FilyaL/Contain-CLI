FROM python:3.11-slim
WORKDIR /app
RUN pip install flask psycopg2-binary redis
COPY app.py .
CMD ["python", "app.py"]
