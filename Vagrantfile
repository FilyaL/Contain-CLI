Vagrant.configure("2") do |config|
  config.vm.box = "ubuntu/jammy64"
  config.vm.hostname = "contain-cli"
  
  config.vm.network "forwarded_port", guest: 9092, host: 9092
  config.vm.network "forwarded_port", guest: 8081, host: 8081
  config.vm.network "forwarded_port", guest: 8001, host: 8001
  config.vm.network "forwarded_port", guest: 5000, host: 5000
  config.vm.network "forwarded_port", guest: 5432, host: 5432
  config.vm.network "forwarded_port", guest: 6379, host: 6379
  config.vm.network "forwarded_port", guest: 443, host: 443
  config.vm.network "forwarded_port", guest: 81, host: 81
  config.vm.network "forwarded_port", guest: 3000, host: 3000
  config.vm.network "forwarded_port", guest: 3100, host: 3100
  config.vm.network "forwarded_port", guest: 5672, host: 5672
  config.vm.network "forwarded_port", guest: 15672, host: 15672
  config.vm.network "forwarded_port", guest: 8080, host: 8080
  config.vm.network "private_network", ip: "192.168.56.10"
  
  config.vm.provider "virtualbox" do |vb|
    vb.memory = "2048"
    vb.cpus = 2
  end
  
  config.vm.provision "shell", inline: <<-SHELL
    apt-get update
    apt-get install -y python3-pip python3-venv docker.io
    systemctl start docker
    usermod -aG docker vagrant
  SHELL
end
