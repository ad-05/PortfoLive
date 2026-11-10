output "site_base_url" {
  description = "Where published portfolios are served (CloudFront if enabled, otherwise the S3 website endpoint)"
  value       = local.use_cf ? "https://${aws_cloudfront_distribution.cdn[0].domain_name}" : "http://${aws_s3_bucket_website_configuration.site[0].website_endpoint}"
}

output "s3_bucket" {
  value = aws_s3_bucket.sites.id
}

output "server_public_ips" {
  value = { for k, v in aws_instance.server : k => v.public_ip }
}

output "next_steps" {
  value = <<-EOT
    Inventory and secrets for Ansible were written to ../ansible/.
    Next:  cd ../ansible && cp group_vars/all/secrets.yml.example group_vars/all/secrets.yml  (edit it)
           ansible-playbook site.yml
  EOT
}
