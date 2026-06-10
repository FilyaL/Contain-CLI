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
@click.argument('name', required=False, default=None)
@click.option('--example', is_flag=True, help='Create full-stack example')
def init(name, example):
    """Initialize a new contain configuration"""
    if name:
        config_dir = Path(name)
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "contain.yaml"
    else:
        config_path = Path("contain.yaml")
    
    if config_path.exists():
        click.echo(f" {config_path} already exists")
        return
    
    if example:
        project_name = Path(name).name if name else "full-stack"
        config = {
            "name": project_name,
            "version": "2.0",
            "services": {
                "postgres": {
                    "image": "postgres:15-alpine",
                    "restart": "always",
                    "ports": ["5432:5432"],
                    "environment": {
                        "POSTGRES_PASSWORD": "secret"
                    },
                    "healthcheck": {
                        "command": ["pg_isready", "-U", "postgres"],
                        "interval": 5,
                        "timeout": 30
                    }
                },
                "redis": {
                    "image": "redis:7-alpine",
                    "restart": "always",
                    "ports": ["6379:6379"],
                    "healthcheck": {
                        "command": ["redis-cli", "ping"],
                        "interval": 5,
                        "timeout": 30
                    }
                },
                "api": {
                    "build": "./api",
                    "restart": "always",
                    "ports": ["5000:5000"],
                    "depends_on": ["postgres", "redis"],
                    "healthcheck": {
                        "http": "/health",
                        "interval": 5,
                        "timeout": 30
                    }
                },
                "web": {
                    "image": "nginx:alpine",
                    "restart": "always",
                    "ports": ["8080:80"],
                    "depends_on": ["api"],
                    "healthcheck": {
                        "http": "/",
                        "interval": 5,
                        "timeout": 30
                    }
                },
                "prometheus": {
                    "image": "prom/prometheus:latest",
                    "restart": "always",
                    "ports": ["9090:9090"],
                    "healthcheck": {
                        "http": "/-/healthy",
                        "interval": 10,
                        "timeout": 30
                    }
                },
                "grafana": {
                    "image": "grafana/grafana:latest",
                    "restart": "always",
                    "ports": ["3000:3000"],
                    "healthcheck": {
                        "http": "/api/health",
                        "interval": 10,
                        "timeout": 30
                    }
                }
            }
        }
    else:
        project_name = Path(name).name if name else "example"
        config = {
            "name": project_name,
            "version": "1.0",
            "services": {
                "web": {
                    "image": "nginx:alpine",
                    "restart": "always",
                    "ports": ["8080:80"],
                    "healthcheck": {
                        "http": "/",
                        "interval": 5,
                        "timeout": 30
                    }
                },
                "redis": {
                    "image": "redis:7-alpine",
                    "restart": "always",
                    "ports": ["6379:6379"],
                    "healthcheck": {
                        "command": ["redis-cli", "ping"],
                        "interval": 5,
                        "timeout": 30
                    }
                }
            }
        }
    
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    
    click.echo(f" Created {config_path}")
    
    if name:
        click.echo(f"\n Project: {name}/")
    
    click.echo("\n Next steps:")
    if name:
        click.echo(f"  cd {name}")
    click.echo("  contain up")
    
    if example:
        click.echo("\n Services included:")
        click.echo("  • PostgreSQL (port 5432)")
        click.echo("  • Redis (port 6379)")
        click.echo("  • API (port 5000)")
        click.echo("  • Nginx (port 8080)")
        click.echo("  • Prometheus (port 9090)")
        click.echo("  • Grafana (port 3000)")
    else:
        click.echo("\n Services included:")
        click.echo("  • Nginx (port 8080)")
        click.echo("  • Redis (port 6379)")

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
    
@cli.command()
@click.argument('file', default='contain.yaml')
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
