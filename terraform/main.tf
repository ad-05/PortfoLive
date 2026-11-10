terraform {
  required_version = ">= 1.5"
  required_providers {
    aws   = { source = "hashicorp/aws", version = "~> 5.0" }
    local = { source = "hashicorp/local", version = "~> 2.5" }
  }
}
provider "aws" { region = var.region }

locals {
  use_cf = var.enable_cloudfront
}

# ---------------- Content delivery: S3 (+ optional CloudFront) ----------------
resource "aws_s3_bucket" "sites" {
  bucket        = var.bucket_name
  force_destroy = true # lets `terraform destroy` empty the bucket of published sites
}

resource "aws_s3_bucket_public_access_block" "sites" {
  bucket                  = aws_s3_bucket.sites.id
  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = local.use_cf # relaxed only in S3-website mode (bucket must be publicly readable)
  restrict_public_buckets = local.use_cf
}

# S3-website mode only: serves /jane/ -> /jane/index.html without the CloudFront function.
resource "aws_s3_bucket_website_configuration" "site" {
  count  = local.use_cf ? 0 : 1
  bucket = aws_s3_bucket.sites.id
  index_document { suffix = "index.html" }
}

resource "aws_cloudfront_origin_access_control" "oac" {
  count                             = local.use_cf ? 1 : 0
  name                              = "${var.project}-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# Rewrites /jane/  ->  /jane/index.html
resource "aws_cloudfront_function" "index_rewrite" {
  count   = local.use_cf ? 1 : 0
  name    = "${var.project}-index-rewrite"
  runtime = "cloudfront-js-2.0"
  publish = true
  code    = <<-JS
    function handler(event) {
      var r = event.request;
      if (r.uri.endsWith('/')) r.uri += 'index.html';
      else if (!r.uri.includes('.')) r.uri += '/index.html';
      return r;
    }
  JS
}

resource "aws_cloudfront_distribution" "cdn" {
  count   = local.use_cf ? 1 : 0
  enabled = true
  origin {
    domain_name              = aws_s3_bucket.sites.bucket_regional_domain_name
    origin_id                = "sites"
    origin_access_control_id = aws_cloudfront_origin_access_control.oac[0].id
  }
  default_cache_behavior {
    target_origin_id       = "sites"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = "658327ea-f89d-4fab-a63d-7e88639e58f6" # AWS managed: CachingOptimized
    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.index_rewrite[0].arn
    }
  }
  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }
  viewer_certificate { cloudfront_default_certificate = true }
}

resource "aws_s3_bucket_policy" "allow_cf" {
  bucket     = aws_s3_bucket.sites.id
  depends_on = [aws_s3_bucket_public_access_block.sites]

  policy = local.use_cf ? jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "cloudfront.amazonaws.com" }
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.sites.arn}/*"
      Condition = { StringEquals = { "AWS:SourceArn" = aws_cloudfront_distribution.cdn[0].arn } }
    }]
    }) : jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = "*"
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.sites.arn}/*"
    }]
  })
}

# ---------------- Least-privilege identity for the backend ----------------
resource "aws_iam_user" "backend" { name = "${var.project}-backend" }
resource "aws_iam_user_policy" "backend" {
  name = "publish-sites"
  user = aws_iam_user.backend.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["s3:PutObject"], Resource = "${aws_s3_bucket.sites.arn}/*" },
    ]
  })
}

# Only needed when CloudFront is on.
resource "aws_iam_user_policy" "backend_invalidate" {
  count = local.use_cf ? 1 : 0
  name  = "invalidate-cdn"
  user  = aws_iam_user.backend.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["cloudfront:CreateInvalidation"], Resource = aws_cloudfront_distribution.cdn[0].arn },
    ]
  })
}
resource "aws_iam_access_key" "backend" { user = aws_iam_user.backend.name }

# ---------------- VPC + CI/CD servers ----------------
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  tags                 = { Name = "${var.project}-vpc" }
}
resource "aws_internet_gateway" "igw" { vpc_id = aws_vpc.main.id }
resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  map_public_ip_on_launch = true
}
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }
}
resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "ci" {
  vpc_id = aws_vpc.main.id

  # SSH, Kubernetes API, Jenkins, SonarQube, app, Prometheus, Alertmanager, Grafana: reachable only from your IP
  dynamic "ingress" {
    for_each = [22, 6443, 8080, 9000, 30080, 30090, 30093, 30300]
    content {
      from_port   = ingress.value
      to_port     = ingress.value
      protocol    = "tcp"
      cidr_blocks = [var.admin_cidr]
    }
  }

  # Servers talk to each other freely inside the VPC
  ingress {
    from_port = 0
    to_port   = 0
    protocol  = "-1"
    self      = true
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

# Servers are only *created* here. Ansible (../ansible) installs and configures the software.
locals {
  servers = {
    jenkins    = "t3.medium"
    sonarqube  = "t3.medium" # SonarQube needs ~4 GB RAM
    kubernetes = "t3.large"  # k3s + app (blue/green) + Prometheus/Grafana/Alertmanager
  }
}

resource "aws_instance" "server" {
  for_each               = local.servers
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = each.value
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.ci.id]
  key_name = aws_key_pair.main.key_name
 
  root_block_device {
    volume_size = 30
  }
  tags = { Name = "${var.project}-${each.key}" }
}

# ---------------- Hand-off to Ansible ----------------
resource "local_file" "ansible_inventory" {
  filename = "${path.module}/../ansible/inventory.ini"
  content = templatefile("${path.module}/templates/inventory.tftpl", {
    jenkins    = { public_ip = aws_instance.server["jenkins"].public_ip, private_ip = aws_instance.server["jenkins"].private_ip }
    sonarqube  = { public_ip = aws_instance.server["sonarqube"].public_ip, private_ip = aws_instance.server["sonarqube"].private_ip }
    kubernetes = { public_ip = aws_instance.server["kubernetes"].public_ip, private_ip = aws_instance.server["kubernetes"].private_ip }
    key_path   = var.ssh_private_key_path
  })
}

# Contains the backend's AWS keys, so it is "sensitive" (file mode 0600) and git-ignored.
resource "local_sensitive_file" "ansible_vars" {
  filename        = "${path.module}/../ansible/group_vars/all/terraform.yml"
  file_permission = "0600"
  content = templatefile("${path.module}/templates/terraform_vars.tftpl", {
    region          = var.region
    bucket          = aws_s3_bucket.sites.id
    distribution_id = local.use_cf ? aws_cloudfront_distribution.cdn[0].id : ""
    cdn_url         = local.use_cf ? "https://${aws_cloudfront_distribution.cdn[0].domain_name}" : "http://${aws_s3_bucket_website_configuration.site[0].website_endpoint}"
    access_key_id   = aws_iam_access_key.backend.id
    secret_key      = aws_iam_access_key.backend.secret
  })
}

resource "aws_key_pair" "main" {
  key_name   = "${var.project}-tf"   # a new name, so it can't collide with the old console key
  public_key = file(pathexpand(var.ssh_public_key_path))
}

