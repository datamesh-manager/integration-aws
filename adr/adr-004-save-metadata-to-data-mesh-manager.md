# Saving Metadata to Data Mesh Manager

**Date:** 2023-07-06

## Context

In our system, we need to store metadata associated with various objects. The metadata provides a complete state of the objects and is essential for proper functioning of the system. We have considered different options for storing this metadata, including dedicated databases or external systems. We need to decide whether to save the metadata to the Data Mesh Manager, taking into account factors such as data completeness, availability of the API, auditing capabilities, the need for a dedicated database, and the user experience during integration.

## Decision

We have decided to save the metadata to the Data Mesh Manager. This decision is based on the following considerations:

1. **Complete State of Objects:** Storing metadata in the Data Mesh Manager allows us to have a centralized location for maintaining the complete state of objects. This ensures that all relevant metadata is easily accessible and up to date, enabling efficient processing and analysis.

2. **API Availability for Event Processing:** As events come in over the same API, the Data Mesh Manager's API is expected to be reachable when we want to process events. This ensures that the metadata updates can be performed in real-time, providing accurate and up-to-date information.

3. **Audit Logging:** The Data Mesh Manager can provide audit logging capabilities, allowing us to track any malicious changes or unauthorized access to the metadata. This enhances security and accountability, providing a trail of actions performed on the metadata.

4. **Elimination of Dedicated Database:** Storing the metadata in the Data Mesh Manager eliminates the need for a dedicated database solely for metadata storage. This simplifies the architecture, reduces operational complexity, and avoids the potential overhead of managing and scaling a separate database.

5. **Tagging for Better Integration Experience:** The Data Mesh Manager supports tagging functionality, which allows users to categorize and label the metadata entries. By leveraging tags, users can have a better feeling of integration and organization within the Data Mesh Manager, enhancing their overall experience.

## Consequences

- Ensures a complete state of objects by storing metadata in the Data Mesh Manager.
- Facilitates auditing of metadata changes for enhanced security and accountability.
- Eliminates the need for a dedicated database, simplifying the architecture.
- Provides tagging functionality for better integration experience and organization.
- Relies on the expected availability of the Data Mesh Manager's API for event processing.
- May introduce dependencies on the Data Mesh Manager for metadata storage and access.
- Requires careful design and implementation to ensure scalability and performance of the Data Mesh Manager.
