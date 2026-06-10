#!/usr/bin/env python3
"""CLI entry point for contain"""

import click
import yaml
import os
import subprocess
import time
from pathlib import Path

@click.group()
def cli():
    """Contain - Production-grade container orchestration"""
    pass

@cli.command()
@click.argument("name", default=".")
@cli.command()
def init():
    """Initialize new contain.yaml"""
    config = """name: my-app
services:
  redis:
    image: redis:7-alpine
    restart: always
    ports:
      - "6379:6379"
    healthcheck:
      command: ["redis-cli", "ping"]
      interval: 5
      timeout: 30

  web:
    image: nginx:alpine
    restart: always
    ports:
      - "8080:80"
    healthcheck:
      http: "/"
      interval: 5
      timeout: 30
"""
    
    if os.path.exists("contain.yaml"):
        click.echo("contain.yaml already exists!")
        return
    
    with open("contain.yaml", "w") as f:
        f.write(config)
    
    click.echo("Created contain.yaml")
    click.echo("\n Next steps:")
    click.echo("  1. Edit contain.yaml for your services")
    click.echo("  2. Run: contain up")
@cli.command()
@click.option("--file", "-f", default="contain.yaml", help="Config file")
@click.option("--env", "-e", default="dev", help="Environment (dev/staging/prod)")
def up(file, env):
    """Start all services"""
    click.echo(f"Starting services in {env} environment...")
    
    if not os.path.exists(file):
        click.echo(f"Config file {file} not found")
        return
    
    with open(file) as f:
        config = yaml.safe_load(f)
    
    config['environment'] = env
    
    from .orchestrator import Orchestrator
    orch = Orchestrator(config)
    orch.start_all()
    result = subprocess.run(["pgrep", "-f", "watchdog.py"], capture_output=True)
    if result.returncode != 0:
        subprocess.Popen(
            ["python3", "/vagrant/contain-cli/watchdog.py"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        click.echo("  Watchdog started")
    click.echo("\nAll services started!")

    result = subprocess.run(["pgrep", "-f", "contain.*metrics"], capture_output=True)
    if result.returncode != 0:
        subprocess.Popen(
            ["contain", "metrics", "--port", "9092"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        click.echo("  Metrics server started (port 9092)")

    result = subprocess.run(["pgrep", "-f", "contain.*dashboard"], capture_output=True)
    if result.returncode != 0:
        subprocess.Popen(
            ["contain", "dashboard", "--port", "5000"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        click.echo("  Dashboard started (port 5000)")

@cli.command()
@click.option("--file", "-f", default="contain.yaml")
def down(file):
    """Stop all services"""
    click.echo("Stopping services...")
    
    if not os.path.exists(file):
        click.echo(f"Config file {file} not found")
        return
    
    with open(file) as f:
        config = yaml.safe_load(f)
    
    service_name = config.get("name", "app")
    
    import docker
    client = docker.from_env()
    
    containers = client.containers.list(all=True, filters={"name": service_name})
    for container in containers:
        try:
            container.stop()
            container.remove()
            click.echo(f"  Stopped and removed {container.name}")
        except Exception as e:
            click.echo(f"  Failed to stop {container.name}: {e}")
    
    try:
        network = client.networks.get(f"{service_name}_network")
        network.remove()
        click.echo(f"  Removed network: {service_name}_network")
    except:
        pass
    
    click.echo("All services stopped")
def ps(file):
    """Show running services status"""
    if not os.path.exists(file):
        click.echo(f"Config file {file} not found")
        return
    
    with open(file) as f:
        config = yaml.safe_load(f)
    
    from .orchestrator import Orchestrator
    orch = Orchestrator(config)
    orch.status()

@cli.command()
@click.option("--port", "-p", default=9092, help="Port for Prometheus metrics")
def metrics(port):
    """Start Prometheus metrics server"""
    from .metrics import MetricsExporter
    exporter = MetricsExporter(port=port)
    click.echo(f"Prometheus metrics available at http://localhost:{port}/metrics")
    exporter.run()

@cli.command()
@click.option("--file", "-f", default="contain.yaml", help="Config file")
@click.option("--tail", "-t", default=100, help="Number of lines to show")
@click.argument("service", required=False)
def logs(file, tail, service):
    """Show logs from services"""
    if not os.path.exists(file):
        click.echo(f"Config file {file} not found")
        return
    
    with open(file) as f:
        config = yaml.safe_load(f)
    
    service_name = config.get("name", "app")
    
    import docker
    client = docker.from_env()
    
    if service:
        container_name = f"{service_name}-{service}"
        try:
            container = client.containers.get(container_name)
            logs = container.logs(tail=tail).decode('utf-8')
            click.echo(logs)
        except docker.errors.NotFound:
            click.echo(f"Service {service} not found")
    else:
        services = config.get("services", {})
        for s in services.keys():
            container_name = f"{service_name}-{s}"
            try:
                container = client.containers.get(container_name)
                click.echo(f"\n--- Logs for {s} ---")
                logs = container.logs(tail=tail).decode('utf-8')
                click.echo(logs)
            except docker.errors.NotFound:
                click.echo(f"Service {s} not running")

if __name__ == "__main__":
    cli()

@cli.command()
@click.option("--file", "-f", default="contain.yaml", help="Config file")
@click.argument("service")
@click.argument("command", nargs=-1)
def exec(file, service, command):
    """Execute command in a running container"""
    if not os.path.exists(file):
        click.echo(f"Config file {file} not found")
        return
    
    with open(file) as f:
        config = yaml.safe_load(f)
    
    service_name = config.get("name", "app")
    container_name = f"{service_name}-{service}"
    
    import docker
    client = docker.from_env()
    
    try:
        container = client.containers.get(container_name)
        cmd = ' '.join(command)
        if not cmd:
            cmd = '/bin/sh'
            click.echo(f"Opening shell in {service}...")
        
        result = container.exec_run(cmd, tty=True)
        if result.output:
            click.echo(result.output.decode('utf-8'))
    except docker.errors.NotFound:
        click.echo(f"Service {service} not found or not running")

@cli.command()
@click.option("--port", "-p", default=5000, help="Dashboard port")
def dashboard(port):
    """Start web dashboard"""
    from .dashboard import run_dashboard
    click.echo(f"Dashboard available at http://localhost:{port}")
    run_dashboard(port)

@cli.command()
@click.option('--example', is_flag=True, help='Create example config with many services')
def init(example):
    """Initialize new contain.yaml"""
    if os.path.exists("contain.yaml"):
        click.echo("contain.yaml already exists!")
        return
    
    if example:
        config = """name: full-stack
services:
  postgres:
    image: postgres:15-alpine
    restart: always
    ports: ["5432:5432"]
    environment:
      POSTGRES_PASSWORD: "secret"
    healthcheck:
      command: ["pg_isready", "-U", "postgres"]
      interval: 5
      timeout: 30

  redis:
    image: redis:7-alpine
    restart: always
    ports: ["6379:6379"]
    healthcheck:
      command: ["redis-cli", "ping"]
      interval: 5
      timeout: 30

  api:
    build: ./api
    restart: always
    ports: ["5000:5000"]
    depends_on: ["postgres", "redis"]
    healthcheck:
      http: "/health"
      interval: 5
      timeout: 30

  web:
    image: nginx:alpine
    restart: always
    ports: ["8080:80"]
    depends_on: ["api"]
    healthcheck:
      http: "/"
      interval: 5
      timeout: 30

  prometheus:
    image: prom/prometheus:latest
    restart: always
    ports: ["9090:9090"]
    healthcheck:
      http: "/-/healthy"
      interval: 10
      timeout: 30
"""
    else:
        config = """name: my-app
services:
  web:
    image: nginx:alpine
    restart: always
    ports: ["8080:80"]
    healthcheck:
      http: "/"
      interval: 5
      timeout: 30
"""
    
    with open("contain.yaml", "w") as f:
        f.write(config)
    
    click.echo(" Created contain.yaml")
    click.echo("\n Next steps:")
    click.echo("  1. Run: contain up")
