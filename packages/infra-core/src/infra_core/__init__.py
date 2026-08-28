"""infra-core: platform infrastructure abstractions with local fakes.

Phase 01 scope: Queue/DLQ, Object Store, Secret Resolver, Clock, and layered
configuration. Real bindings arrive via protected DEV pipelines in later
subphases; nothing here talks to remote services.
"""

from infra_core.clock import Clock, FakeClock, SystemClock
from infra_core.config import (
    AppConfig,
    CapabilityConfig,
    ConfigError,
    ObjectStoreConfig,
    QueueConfig,
    load_config,
)
from infra_core.objectstore import (
    FakeObjectStore,
    MalwareRejectedError,
    ObjectKey,
    ObjectLimits,
    ObjectStore,
    ObjectStoreError,
    OverwriteError,
    StoredObject,
    ValidationError,
)
from infra_core.queue import (
    DeadMessage,
    FakeQueueClient,
    LeaseExpiredError,
    Message,
    QueueClient,
    QueueError,
    RetryPolicy,
)
from infra_core.secrets import (
    FakeSecretResolver,
    SecretError,
    SecretNotFoundError,
    SecretRef,
    SecretRefFormatError,
    SecretResolver,
    SecretValue,
)

__all__ = [
    "AppConfig",
    "CapabilityConfig",
    "Clock",
    "ConfigError",
    "DeadMessage",
    "FakeClock",
    "FakeObjectStore",
    "FakeQueueClient",
    "FakeSecretResolver",
    "LeaseExpiredError",
    "MalwareRejectedError",
    "Message",
    "ObjectKey",
    "ObjectLimits",
    "ObjectStore",
    "ObjectStoreConfig",
    "ObjectStoreError",
    "OverwriteError",
    "QueueClient",
    "QueueConfig",
    "QueueError",
    "RetryPolicy",
    "SecretError",
    "SecretNotFoundError",
    "SecretRef",
    "SecretRefFormatError",
    "SecretResolver",
    "SecretValue",
    "StoredObject",
    "SystemClock",
    "ValidationError",
    "load_config",
]
