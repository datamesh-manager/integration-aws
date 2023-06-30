# Data Mesh Manager - AWS Integration

This repository contains a complete setup, which allows you to integrate the [Data Mesh Manager](https://www.datamesh-manager.com/) into  an AWS account.
It uses only serverless AWS functionality like Lambda, CloudWatch, S3, Secretsmanager and SQS.
The infrastructure is set up by using [Terraform](https://www.terraform.io/).

## Architecture
For a better understanding of how the integration works, see this simple architecture diagram. Arrows show access direction.

```
                                       ┌─────────────────┐
                                       │                 │
                                       │Data Mesh Manager│
                                       │                 │
                                       └─────────────────┘
                                          ▲           ▲
                                          │           │
                                          │           │
┌─────────────────────────────────────────┼───────────┼─────────────────────────────────────────┐
│                                         │           │                                         │
│                                         │           │                                         │
│                     pull events         │           │ read contract information               │
│              ┌──────────────────────────┘           └──────────────────────────┐              │
│              │                                                                 │              │
│              │                                                                 │              │
│              │                                                                 │              │
│     ┌────────┴────────┐                ──────────── ──                ┌────────┴────────┐     │
│     │  process_feed   │     write     │ dmm_events │  │    trigger    │ process_events  │     │
│     │                 ├──────────────►│            │  ├──────────────►│                 │     │
│     │[Lambda Function]│               │ [SQS Queue]│  │               │[Lambda Function]│     │
│     └─────────────────┘                ──────────── ──                └────────┬────────┘     │
│                                                                                │              │
│                                                                                │manage        │
│                                                                                │              │
│                                                                                ▼              │
│                                                                        ┌────────────────┐     │
│                                                                        │                │     │
│                                                                        │  IAM Policies  │     │
│                                                                        │                │     │
│                                                                        └────────────────┘     │
│                                                                                               │
│                                                                                               │
│                                                                              [AWS Integration]│
└───────────────────────────────────────────────────────────────────────────────────────────────┘
```

## Lambdas
### [Process Feed](src%2Fprocess_feed%2Flambda_handler.py)
- **Execution:** The function runs every minute, scheduled using an AWS Cloud Watch Rule.
- **Reading Events from Data Mesh Manager:** It reads all unprocessed [events from the Data Mesh Manager API](https://docs.datamesh-manager.com/events). 
- **Sending Events to SQS:** These events are then sent to an SQS queue for further processing. 
- **Tracking Last Event ID:** To ensure proper resumption of processing, the function remembers the last event ID by storing it in an S3 object. This allows subsequent executions of the function to start processing from the correct feed position.

### [Process Events](src%2Fprocess_events%2Flambda_handler.py)
*This implementation is not fully functional yet!*

*TBD: Information about mandatory (custom) fields inside the data contract* 

- **Execution:** The function is triggered by new events in the SQS queue.
- **Filtering Relevant Events:** The function selectively processes events based on their type. It focuses on events of the type `DataContractActivatedEvent` and `DataContractDeactivatedEvent`.
- **DataContractActivatedEvent:** When a `DataContractActivatedEvent` occurs, the function creates IAM policies. These policies allow access from a producing data product's output port to a consuming data product.
- **DataContractDeactivatedEvent:** When a `DataContractDeactivatedEvent` occurs, the function removes the permissions from the consuming data product to access the output port of the producing data product.
- **Extra Information:** To effectively process the events, the function retrieves additional information from the Data Mesh Manager API. This information includes details about the data contract, data products involved, and the teams associated with them.

## Usage
### Prerequisites
- [Terraform](https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli)
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- [Python3.10](https://www.python.org/downloads/release/python-3100/)

### Deployment
- **Setup Terraform Variables:** An example of a minimum configuration can be found [here](terraform%2Fterraform.tfvars.template). Copy this file and name the copy `terraform.tfvars`. Set your credentials.
- **Login Into AWS:** Login into your AWS account [through the cli](https://docs.aws.amazon.com/signin/latest/userguide/command-line-sign-in.html)
- **Run The CICD Script:** [This script](cicd.sh) is an example of what a CICD pipeline would look like to run this on AWS. This script requires you to set a version for the lambda source code. E.g. `./cicd.sh v0.0.1`
