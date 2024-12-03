#!/bin/bash
sudo yum update -y
sudo yum install -y docker
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ec2-user
DOCKER_COMPOSE_BIN="/usr/local/bin/docker-compose"
if ! docker compose version >/dev/null 2>&1; then
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" -o $DOCKER_COMPOSE_BIN
    sudo chmod +x $DOCKER_COMPOSE_BIN
fi
docker --version
docker-compose version
aws s3 cp s3://%S3_DOMAIN%/%OBJECT_KEY% /home/ec2-user/docker-compose.yml
SHARD_NAME=%UNIQUE_SHARD_NAME%
sed -i "s/%SHARD_NAME%/$SHARD_NAME/" /home/ec2-user/docker-compose.yml

cd /home/ec2-user
docker-compose up -d

echo "Waiting for mongo-shard to be ready..."
until docker exec mongo-shard mongosh --eval "db.runCommand({ ping: 1 })" > /dev/null 2>&1; do
    echo "Waiting for mongo-shard to accept connections..."
    sleep 2
done

TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 300")

PUBLIC_IP=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/public-ipv4)
echo $PUBLIC_IP

if [ -z "$PUBLIC_IP" ]; then
    echo "Failed to retrieve public IP from metadata service."
    exit 1
fi

echo "Initializing replica set for mongo shard..."
docker exec mongo-shard mongosh --eval "rs.initiate(
    {
        _id: '${SHARD_NAME}',
        members: [
            { _id: 0, host: '${PUBLIC_IP}:27017' }
        ]
    }
)"

ROUTER_IP=%ROUTER_IP%

echo "Router IP ---- "
echo $ROUTER_IP

MAX_RETRIES=5         
INITIAL_DELAY=30       
MAX_DELAY=100          


initialize_shard() {
  docker exec mongo-shard mongosh --host "$ROUTER_IP" --eval "sh.addShard('${SHARD_NAME}/${PUBLIC_IP}:27017')"
}

retry_count=0
delay=$INITIAL_DELAY
success=false

while [ $retry_count -lt $MAX_RETRIES ]; do
  echo "Attempting to add shard (Attempt: $((retry_count + 1)) of $MAX_RETRIES)..."

  if initialize_shard; then
    echo "Shard added successfully."
    success=true
    break
  else
    echo "Failed to add shard. Retrying in $delay seconds..."
    retry_count=$((retry_count + 1))
    sleep $delay
    delay=$((delay * 2))
    if [ $delay -gt $MAX_DELAY ]; then
      delay=$MAX_DELAY
    fi
  fi
done
