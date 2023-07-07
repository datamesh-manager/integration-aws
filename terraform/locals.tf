locals {
  dmm_api_key_secret_name   = "${var.secrets_manager_prefix}api_key"
  last_event_id_object_name = "poll_feed/last_event_id"
  dmm_base_url              = "https://api.datamesh-manager.com"
}
