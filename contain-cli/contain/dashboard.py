from flask import Flask, jsonify, render_template_string
import docker
import psutil
import time

app = Flask(__name__)
client = docker.from_env()

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Contain Dashboard</title>
    <meta http-equiv="refresh" content="5">
    <style>
        body { font-family: Arial; margin: 20px; }
        .container { margin-bottom: 20px; border: 1px solid #ccc; padding: 10px; }
        .running { color: green; }
        .stopped { color: red; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <h1>Contain Dashboard</h1>
    <h2>System Stats</h2>
    <p>CPU: {{ cpu }}%</p>
    <p>Memory: {{ memory }} MB</p>
    <p>Total Containers: {{ total_containers }}</p>
    
    <h2>Containers</h2>
    <table>
        <tr><th>Name</th><th>Status</th><th>Image</th><th>Uptime</th></tr>
        {% for container in containers %}
        <tr>
            <td>{{ container.name }}</td>
            <td class="{{ container.status }}">{{ container.status }}</td>
            <td>{{ container.image }}</td>
            <td>{{ container.uptime }}</td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
'''

@app.route('/')
def dashboard():
    containers = []
    for c in client.containers.list(all=True):
        status = 'running' if c.status == 'running' else 'stopped'
        uptime = ''
        if c.status == 'running':
            started = c.attrs['State']['StartedAt']
            uptime = 'running'
        containers.append({
            'name': c.name,
            'status': status,
            'image': c.image.tags[0] if c.image.tags else 'unknown',
            'uptime': uptime
        })
    
    cpu = psutil.cpu_percent()
    memory = psutil.virtual_memory().used / 1024 / 1024
    
    return render_template_string(HTML_TEMPLATE,
                                  cpu=cpu,
                                  memory=round(memory, 1),
                                  total_containers=len(containers),
                                  containers=containers)

@app.route('/api/containers')
def api_containers():
    containers = []
    for c in client.containers.list(all=True):
        containers.append({
            'name': c.name,
            'status': c.status,
            'image': c.image.tags[0] if c.image.tags else 'unknown'
        })
    return jsonify(containers)

def run_dashboard(port=5000):
    app.run(host='0.0.0.0', port=port)
