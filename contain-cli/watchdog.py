#!/usr/bin/env python3
"""Watchdog - monitors and restarts containers"""
import docker
import time
import os
import yaml

client = docker.from_env()

config_path = os.environ.get('CONTAIN_CONFIG', '/vagrant/contain-cli/devops-stack/contain.yaml')
try:
    with open(config_path) as f:
        config = yaml.safe_load(f)
    service_name = config.get('name', 'devops-stack')
    services = config.get('services', {})
    
    containers_to_watch = []
    for name, spec in services.items():
        if spec.get('restart') == 'always':
            containers_to_watch.append(f"{service_name}-{name}")
except Exception as e:
    service_name = 'devops-stack'
    containers_to_watch = []
    for container in client.containers.list(all=True):
        if container.name.startswith(service_name):
            containers_to_watch.append(container.name)

print(f"Watchdog started. Monitoring: {containers_to_watch}")

while True:
    for name in containers_to_watch:
        try:
            container = client.containers.get(name)
            if container.status != 'running':
                print(f"Restarting {name} (status: {container.status})")
                container.start()
                print(f" {name} restarted")
        except docker.errors.NotFound:
            print(f"ontainer {name} not found, skipping")
        except Exception as e:
            print(f" Error with {name}: {e}")
    time.sleep(5)
