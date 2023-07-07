# Prefer Inline Policies for AWS IAM Access Control

**Date:** 2023-07-06

## Context

In our application, we need to manage AWS Identity and Access Management (IAM) policies to control access to various resources. We have two options for defining these policies: inline policies and customer managed policies. Inline policies are directly attached to individual IAM entities, such as users or roles, while customer managed policies are standalone policies that can be attached to multiple entities. We need to decide which approach to adopt, considering the expected usage patterns and resource consumption.

## Decision

We have decided to prefer inline policies over customer managed policies for IAM access control in our application. This decision is based on the following considerations:

1. **Simplicity and Direct Association:** Inline policies offer a simpler and more direct association between IAM entities and the policies they require. With inline policies, the policy definitions are directly embedded in the IAM entities, making it easier to manage and understand the access control configurations.

2. **Specificity of Access:** We believe that most output ports (the resources we give access to with IAM policies) will only have one consumer (the resource the access is given). By using inline policies, we can directly associate and manage the access control for each specific IAM entity, providing granular control and reducing the complexity of managing multiple policies.

3. **Character Limit Consideration:** The aggregated inline policies associated with an IAM entity have a character limit. Based on our analysis, a limit of 10,240 characters should be sufficient for defining access control policies for a single data product (the consumer). This limit allows us to maintain simplicity and avoid hitting policy size constraints.

## Consequences

- Simplifies IAM access control management by directly associating policies with IAM entities.
- Provides granular and specific access control for each resource, aligning with the expected one-to-one relationship between output ports and consumers.
- Avoids complexity associated with managing multiple customer managed policies.
- May lead to increased duplication of policy definitions if similar policies need to be applied to multiple IAM entities.
- Requires careful monitoring of the aggregated inline policy size to ensure it remains within the character limit.
