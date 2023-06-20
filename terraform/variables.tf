variable "versions" {
  type = object({
    process_feed   = string
    process_events = string
  })
  description = "Lambda which should be deployed"
}

variable "aws" {
  type = object({
    region     = string
    access_key = string
    secret_key = string
  })
  sensitive   = true
  description = "AWS configuration"
}

variable "dmm" {
  type = object({
    api_key = string
  })
  sensitive = true
  description = "Data Mesh Manager configuration"
}
