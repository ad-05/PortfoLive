variable "region" {
  type    = string
  default = "ap-south-1"
}
variable "project" {
  type    = string
  default = "portfolive"
}
variable "bucket_name" {
  type        = string
  description = "Globally unique S3 bucket name for published sites"
}
variable "key_name" {
  type        = string
  description = "Existing EC2 key pair name for SSH"
}
variable "admin_cidr" {
  type        = string
  description = "Your public IP as CIDR, e.g. 203.0.113.5/32"
}
variable "enable_cloudfront" {
  type        = bool
  default     = false
  description = "Serve published sites through CloudFront (new AWS accounts must be verified first). If false, sites are served from S3 website hosting over HTTP."
}
variable "ssh_private_key_path" {
  type        = string
  default     = "~/.ssh/portfolive.pem"
  description = "Private key file matching key_name; written into the Ansible inventory"
}

variable "ssh_public_key_path" {
  type        = string
  default     = "~/.ssh/portfolive.pub"
  description = "Public key matching ssh_private_key_path; uploaded as the EC2 key pair"
}
