from flask import Flask, jsonify, request
import redis
import psycopg2
import os
import time
import random

app = Flask(__name__)

DB_HOST = os.getenv('DB_HOST', 'postgres')
REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'postgres')
DB_NAME = os.getenv('DB_NAME', 'postgres')

def get_db():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=5432
        )
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        cur.close()
        return conn
    except Exception as e:
        print(f"DB error: {e}")
        return None

def get_redis():
    try:
        r = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)
        r.ping()
        return r
    except Exception as e:
        print(f"Redis error: {e}")
        return None

@app.route('/')
def home():
    return jsonify({
        "service": "API Gateway",
        "version": "2.0",
        "status": "running"
    })

@app.route('/health')
def health():
    db = get_db()
    r = get_redis()
    return jsonify({
        "status": "healthy",
        "database": "ok" if db else "failed",
        "redis": "ok" if r else "failed"
    })

@app.route('/api/users')
def get_users():
    conn = get_db()
    if not conn:
        return jsonify({"error": "DB connection failed"}), 500
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM users LIMIT 10")
    users = [{"id": row[0], "name": row[1]} for row in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify({"users": users, "count": len(users)})

@app.route('/api/users', methods=['POST'])
def create_user():
    data = request.json
    if not data or not data.get('name'):
        return jsonify({"error": "name required"}), 400
    conn = get_db()
    if not conn:
        return jsonify({"error": "DB connection failed"}), 500
    cur = conn.cursor()
    cur.execute("INSERT INTO users (name) VALUES (%s) RETURNING id", (data['name'],))
    new_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"id": new_id, "name": data['name']})

@app.route('/api/products')
def get_products():
    products = [
        {"id": 1, "name": "Laptop", "price": 999},
        {"id": 2, "name": "Mouse", "price": 25},
        {"id": 3, "name": "Keyboard", "price": 75}
    ]
    return jsonify({"products": products})

@app.route('/api/cache/test')
def test_cache():
    r = get_redis()
    if not r:
        return jsonify({"error": "Redis connection failed"}), 500
    r.set('test_key', 'Hello from Redis!')
    value = r.get('test_key')
    return jsonify({"message": value, "cache": "Redis works"})

@app.route('/api/metrics')
def metrics():
    return jsonify({
        "requests": random.randint(100, 1000),
        "response_time_ms": random.randint(10, 200)
    })

if __name__ == '__main__':
    print(f"Starting API on port 5000")
    print(f"DB_HOST: {DB_HOST}")
    print(f"REDIS_HOST: {REDIS_HOST}")
    app.run(host='0.0.0.0', port=5000)
