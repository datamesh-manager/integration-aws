# Data Mesh Manager - AWS Integration

This repository contains a complete setup, which allows you to integrate the [Data Mesh Manager](https://www.datamesh-manager.com/) into  an AWS account.
It uses only serverless AWS functionality like Lambda, CloudWatch, S3, Secretsmanager and SQS.
The infrastructure is set up by using Terraform.

## Limitations
- We do not handle deleted data contracts. So make sure to deactivate data contracts before deleting them. Otherwise, permissions will be kept existent.
- Not all kinds of output ports are supported at this point. Currently, we support the following:
  - S3 Buckets

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
│     │    poll_feed    │     write     │ dmm_events │  │    trigger    │ process_events  │     │
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

### Architecture Decision Records
- [adr-001-terraform-and-serverless.md](adr%2Fadr-001-terraform-and-serverless.md)
- [adr-002-idempotent-event-processing.md](adr%2Fadr-002-idempotent-event-processing.md)
- [adr-003-prefer-inline-policies-for-aws-iam.md](adr%2Fadr-003-prefer-inline-policies-for-aws-iam.md)
- [adr-004-save-metadata-to-data-mesh-manager.md](adr%2Fadr-004-save-metadata-to-data-mesh-manager.md)
- [adr-005-fifo-queue-in-sqs.md](adr%2Fadr-005-fifo-queue-in-sqs.md)

## Lambdas
### [Process Feed](src%2Fpoll_feed%2Flambda_handler.py)
- **Execution:** The function runs every minute, scheduled using an AWS Cloud Watch Rule.
- **Reading Events from Data Mesh Manager:** It reads all unprocessed [events from the Data Mesh Manager API](https://docs.datamesh-manager.com/events). 
- **Sending Events to SQS:** These events are then sent to an SQS queue for further processing. 
- **Tracking Last Event ID:** To ensure proper resumption of processing, the function remembers the last event ID by storing it in an S3 object. This allows subsequent executions of the function to start processing from the correct feed position.

### [Process Events](src%2Fprocess_events%2Flambda_handler.py)
- **Execution:** The function is triggered by new events in the SQS queue.
- **Filtering Relevant Events:** The function selectively processes events based on their type. It focuses on events of the type `DataContractActivatedEvent` and `DataContractDeactivatedEvent`.
- **DataContractActivatedEvent:** When a `DataContractActivatedEvent` occurs, the function creates IAM policies. These policies allow access from a producing data product's output port to a consuming data product.
- **DataContractDeactivatedEvent:** When a `DataContractDeactivatedEvent` occurs, the function removes the permissions from the consuming data product to access the output port of the producing data product. This will skip events, if no corresponding policy ist found.
- **Extra Information:** To effectively process the events, the function may retrieve additional information from the Data Mesh Manager API. This information includes details about the data contract, data products involved, and the teams associated with them.

## Usage
### Prerequisites
- [Terraform](https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli)
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- [Python3.10](https://www.python.org/downloads/release/python-3100/)

### Prepare your data products
To allow the integration to work, your data products in Data Mesh manager must contain some metadata in their [custom fields](https://docs.datamesh-manager.com/dataproducts).

A consuming data product requires information about its AWS IAM role (we use the notation of the [data product specification](https://github.com/datamesh-architecture/dataproduct-specification) here).
```yaml
custom:
  aws-role-name: <PLACEHOLDER>
```

A providing data product requires information about AWS ARNs of its output ports. Which ARNs are required depends on the type of the output port.

#### S3 Bucket
```yaml
outputPorts:
  - custom:
      aws-s3-bucket-arn: <PLACEHOLDER>
```

### Deployment 
- **Setup Terraform Variables:** An example of a minimum configuration can be found [here](terraform%2Fterraform.tfvars.template). Copy this file and name the copy `terraform.tfvars`. Set your credentials.
- **Login Into AWS:** Login into your AWS account [through the cli](https://docs.aws.amazon.com/signin/latest/userguide/command-line-sign-in.html)
- **Run The CICD Script:** [This script](cicd.sh) is an example of what a CICD pipeline would look like to run this on AWS. This script requires you to set a version for the lambda source code. E.g. `./cicd.sh v0.0.1`
