# ---------------------------------------------------------------------------------------------
# EC2 DE MENSAJERIA: cluster RabbitMQ (2 nodos) + cluster Kafka (3 Zookeeper + 3 brokers) + Kafka-UI,
# todo con docker compose, en UNA instancia aparte del backend.
#
# Por que aparte y por que grande: los 3 Zookeeper + 3 brokers + 2 nodos RabbitMQ + Kafka-UI usan
# ~4.5 GB de RAM. En una t2.micro (1 GB) no arrancan. Con t3.large (8 GB) sobra holgura.
# Aislarlos tambien evita que un pico de Kafka tumbe los microservicios (y al reves).
#
# Los 3 archivos compose NO se copian aqui: se leen de desarrollo/ (UNICA fuente de verdad, los mismos
# que se usan en local) y se inyectan comprimidos en el user_data (el limite de user_data es 16 KB).
# ---------------------------------------------------------------------------------------------

# Seguridad: AMQP y Kafka SOLO desde el backend (por security group, no por IP). Las 3 consolas web
# (RabbitMQ 15672/15673 y Kafka-UI 8090) se abren al CIDR `messaging_admin_cidr`; ademas piden usuario
# y clave. Para la demo el valor por defecto es todo Internet: restringelo a tu IP si puedes.
resource "aws_security_group" "sg_mensajeria" {
  name_prefix = "mensajeria-sg"
  vpc_id      = var.vpc_id

  ingress {
    description     = "AMQP (RabbitMQ) desde el backend"
    from_port       = 5672
    to_port         = 5672
    protocol        = "tcp"
    security_groups = [aws_security_group.sg_backend.id]
  }

  ingress {
    description     = "Kafka (listener EXTERNAL de los 3 brokers) desde el backend"
    from_port       = 9092
    to_port         = 9094
    protocol        = "tcp"
    security_groups = [aws_security_group.sg_backend.id]
  }

  ingress {
    description = "Consolas web de RabbitMQ (nodo 1 y 2)"
    from_port   = 15672
    to_port     = 15673
    protocol    = "tcp"
    cidr_blocks = [var.messaging_admin_cidr]
  }

  ingress {
    description = "Kafka-UI"
    from_port   = 8090
    to_port     = 8090
    protocol    = "tcp"
    cidr_blocks = [var.messaging_admin_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "ec2_mensajeria" {
  ami                         = data.aws_ami.amazon_linux_2023.id
  instance_type               = var.messaging_instance_type
  subnet_id                   = var.public_subnet_id
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.sg_mensajeria.id]
  iam_instance_profile        = "LabInstanceProfile"

  # Kafka y RabbitMQ guardan sus datos en volumenes de Docker bajo /var/lib/docker.
  root_block_device {
    volume_size = 30
    volume_type = "gp3"
  }

  # Si cambian los compose o las claves, se REEMPLAZA la instancia (cloud-init solo corre una vez por
  # instancia: sin esto el cambio quedaria sin aplicar en silencio). Perdera los datos de Kafka/RabbitMQ.
  user_data_replace_on_change = true

  tags = {
    Name = "mensajeria-ec2"
  }

  user_data = <<-EOF
    #!/bin/bash
    exec > >(tee /var/log/mensajeria-setup.log) 2>&1
    set -x

    dnf update -y
    dnf install -y docker
    systemctl enable --now docker
    usermod -aG docker ec2-user

    mkdir -p /usr/libexec/docker/cli-plugins
    curl -SL https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-linux-x86_64 -o /usr/libexec/docker/cli-plugins/docker-compose
    chmod +x /usr/libexec/docker/cli-plugins/docker-compose

    # IP privada (IMDSv2): los brokers de Kafka la anuncian en su listener EXTERNAL, que es el que usa
    # el backend. Si anunciaran "localhost", los productores/consumidores del backend no podrian conectar.
    TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 300")
    PRIV_IP=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/local-ipv4)

    mkdir -p /opt/pidealtoke/infra/rabbitmq
    cd /opt/pidealtoke

    # Los compose se leen de desarrollo/ (misma fuente que en local) y viajan comprimidos (gzip + base64).
    echo '${base64gzip(file("${path.module}/../../../docker-compose.rabbitmq.yml"))}' | base64 -d | gunzip > docker-compose.rabbitmq.yml
    echo '${base64gzip(file("${path.module}/../../../docker-compose.kafka.yml"))}' | base64 -d | gunzip > docker-compose.kafka.yml
    echo '${base64gzip(file("${path.module}/../../../docker-compose.kafka-ui.yml"))}' | base64 -d | gunzip > docker-compose.kafka-ui.yml
    echo '${base64gzip(file("${path.module}/../../../infra/rabbitmq/rabbitmq.conf"))}' | base64 -d | gunzip > infra/rabbitmq/rabbitmq.conf

    # docker compose lee este .env (esta junto a los compose). Todo se publica en 0.0.0.0 porque el
    # acceso lo restringe el security group (AMQP/Kafka: solo backend; consolas: messaging_admin_cidr).
    cat > .env << ENV_EOF
    RABBITMQ_USER=${var.rabbitmq_user}
    RABBITMQ_PASSWORD=${var.rabbitmq_password}
    RABBITMQ_ERLANG_COOKIE=${var.rabbitmq_erlang_cookie}
    RABBITMQ_AMQP_BIND=0.0.0.0
    RABBITMQ_UI_BIND=0.0.0.0
    KAFKA_BIND=0.0.0.0
    KAFKA_EXTERNAL_HOST=$PRIV_IP
    KAFKA_UI_BIND=0.0.0.0
    KAFKA_UI_USER=${var.kafka_ui_user}
    KAFKA_UI_PASSWORD=${var.kafka_ui_password}
    ENV_EOF
    chmod 600 .env

    # Misma red compartida que en local (los 3 compose la declaran como externa).
    docker network create pidealtoke-net

    docker compose -f docker-compose.rabbitmq.yml up -d
    docker compose -f docker-compose.kafka.yml up -d
    docker compose -f docker-compose.kafka-ui.yml up -d
    echo "Mensajeria lista: $(date)"
EOF
}

# ---------------------------------------------------------------------------------------------
# API GATEWAY: rutas de los dos servicios nuevos que consume el dashboard (analitica y notificaciones).
# ms-mensajeria (8005) y ms-kafka-admin (8006) NO se publican: son operativos (acceso por SSM).
# ---------------------------------------------------------------------------------------------

resource "aws_apigatewayv2_integration" "analitica_integration" {
  api_id             = aws_apigatewayv2_api.http_api.id
  integration_type   = "HTTP_PROXY"
  integration_method = "ANY"
  integration_uri    = "http://${aws_instance.ec2_backend.public_ip}:8007/api/v1/analitica/{proxy}"
  connection_type    = "INTERNET"
}

resource "aws_apigatewayv2_integration" "notificaciones_integration" {
  api_id             = aws_apigatewayv2_api.http_api.id
  integration_type   = "HTTP_PROXY"
  integration_method = "ANY"
  integration_uri    = "http://${aws_instance.ec2_backend.public_ip}:8008/api/v1/notificaciones/{proxy}"
  connection_type    = "INTERNET"
}

resource "aws_apigatewayv2_integration" "notificaciones_integration_base" {
  api_id             = aws_apigatewayv2_api.http_api.id
  integration_type   = "HTTP_PROXY"
  integration_method = "ANY"
  integration_uri    = "http://${aws_instance.ec2_backend.public_ip}:8008/api/v1/notificaciones"
  connection_type    = "INTERNET"
}

resource "aws_apigatewayv2_route" "route_analitica" {
  api_id             = aws_apigatewayv2_api.http_api.id
  route_key          = "ANY /api/v1/analitica/{proxy+}"
  target             = "integrations/${aws_apigatewayv2_integration.analitica_integration.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt_auth.id
}

resource "aws_apigatewayv2_route" "route_notificaciones_base" {
  api_id             = aws_apigatewayv2_api.http_api.id
  route_key          = "ANY /api/v1/notificaciones"
  target             = "integrations/${aws_apigatewayv2_integration.notificaciones_integration_base.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt_auth.id
}

resource "aws_apigatewayv2_route" "route_notificaciones" {
  api_id             = aws_apigatewayv2_api.http_api.id
  route_key          = "ANY /api/v1/notificaciones/{proxy+}"
  target             = "integrations/${aws_apigatewayv2_integration.notificaciones_integration.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt_auth.id
}

# El preflight CORS (OPTIONS) va SIN authorizer, igual que el resto de rutas.
resource "aws_apigatewayv2_route" "route_analitica_options" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "OPTIONS /api/v1/analitica/{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.analitica_integration.id}"
}

resource "aws_apigatewayv2_route" "route_notificaciones_base_options" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "OPTIONS /api/v1/notificaciones"
  target    = "integrations/${aws_apigatewayv2_integration.notificaciones_integration_base.id}"
}

resource "aws_apigatewayv2_route" "route_notificaciones_options" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "OPTIONS /api/v1/notificaciones/{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.notificaciones_integration.id}"
}
