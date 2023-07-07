# 001. Terraform and Serverless Implementation for Simple Installation of an Open Source Product in AWS Accounts

**Date:** 2023-07-06

## Context

Our organization is developing an open source product that needs to be easily installed by other organizations into their AWS accounts. The product's purpose is to manage AWS Identity and Access Management (IAM) policies effectively. We want to leverage Terraform, a popular infrastructure-as-code tool, along with serverless technologies to provide a simple installation process that can be easily replicated across different AWS accounts.

## Decision

We have decided to use Terraform and serverless technologies for the implementation of our open source product's installation process. This decision is based on the following factors:

1. **Simplicity:** Terraform provides a declarative approach to infrastructure provisioning and management, making it easier for organizations to define and maintain the required AWS resources for the product installation. It allows users to specify the desired state of their infrastructure and automatically handles the creation, modification, and deletion of resources.

2. **Portability:** Terraform's configuration files are written in a domain-specific language (DSL) that is agnostic to cloud providers. This allows organizations to define and manage their infrastructure consistently across different AWS accounts without vendor lock-in concerns.

3. **Scalability:** Serverless technologies, such as AWS Lambda, enable automatic scaling based on demand. By utilizing Lambda functions, organizations can ensure that the product's installation process scales seamlessly as the number of users or resources grows.

4. **AWS Integration:** Leveraging serverless technologies in conjunction with Terraform allows us to take advantage of AWS's native support for serverless services, including Lambda and API Gateway. This integration ensures compatibility and access to the latest features and updates provided by AWS.

## Consequences

- Simplified installation process, allowing organizations to quickly and easily deploy the open source product in their AWS accounts.
- Improved scalability and elasticity, as serverless technologies handle automatic scaling based on demand.
- Portability across different AWS accounts, reducing vendor lock-in concerns.
- Leveraging AWS integrations for enhanced functionality and compatibility.
- Organizations installing the open source product need to have familiarity with Terraform and serverless architectures.
- Additional complexity in managing serverless-specific configurations and monitoring.
- Organizations may need to invest time in understanding and adapting the product's installation process to their specific requirements.
