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
  sensitive   = true
  description = "Data Mesh Manager configuration"
}

variable "versions" {
  type = object({
    process_feed   = string
    process_events = string
  })
  description = "Lambda which should be deployed"
}

variable "bucket_name" {
  type        = string
  default     = "dmm-integration"
  description = "The name of the S3 bucket which stores lambda code and application state"
}

variable "secrets_manager_prefix" {
  type        = string
  default     = "dmm_integration__"
  description = "A prefix for sensitive values stored in the secrets manager"
}

variable "event_queue_name" {
  type        = string
  default     = "dmm-events.fifo"
  description = "The name of the sqs queue in which the dmm events get forwarded. Must end with '.fifo'."
}
