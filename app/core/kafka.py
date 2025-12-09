"""
Kafka Producer and Consumer for Compliance Service.

Uses confluent-kafka library for reliable message handling.
Implements graceful startup, shutdown, and error handling.
"""

import json
import threading
from typing import Any, Callable, Optional
from uuid import uuid4

from confluent_kafka import Consumer, KafkaError, KafkaException, Producer
from confluent_kafka.admin import AdminClient, NewTopic

from app.core.config import settings
from app.core.events import EventEnvelope
from app.core.logging import get_logger

logger = get_logger(__name__)


class KafkaProducerService:
    """
    Kafka producer service using confluent-kafka.
    Handles event publishing with delivery confirmation.
    """

    _instance: Optional["KafkaProducerService"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "KafkaProducerService":
        """Singleton pattern for producer."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._producer: Optional[Producer] = None
        self._initialized = True

    def _get_producer_config(self) -> dict[str, Any]:
        """Get producer configuration."""
        return {
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            "client.id": f"compliance-service-producer-{uuid4().hex[:8]}",
            "acks": "all",
            "enable.idempotence": True,
            "retries": 5,
            "retry.backoff.ms": 100,
            "max.in.flight.requests.per.connection": 5,
            "compression.type": "snappy",
            "linger.ms": 5,
            "batch.size": 16384,
        }

    def connect(self) -> None:
        """Initialize the Kafka producer connection."""
        if self._producer is not None:
            return

        try:
            config = self._get_producer_config()
            self._producer = Producer(config)
            logger.info(
                f"Kafka producer connected to {settings.KAFKA_BOOTSTRAP_SERVERS}"
            )
        except Exception as e:
            logger.error(f"Failed to connect Kafka producer: {e}")
            raise

    def disconnect(self) -> None:
        """Flush and close the producer."""
        if self._producer is not None:
            try:
                remaining = self._producer.flush(timeout=10)
                if remaining > 0:
                    logger.warning(
                        f"Producer flush timed out, {remaining} messages still in queue"
                    )
                self._producer = None
                logger.info("Kafka producer disconnected")
            except Exception as e:
                logger.error(f"Error disconnecting producer: {e}")

    def _delivery_callback(self, err: Optional[KafkaError], msg) -> None:
        """Callback for message delivery confirmation."""
        if err is not None:
            logger.error(
                f"Message delivery failed: {err}, topic: {msg.topic()}, key: {msg.key()}"
            )
        else:
            logger.debug(
                f"Message delivered to {msg.topic()}[{msg.partition()}] at offset {msg.offset()}"
            )

    def publish_event(
        self,
        topic: str,
        event: EventEnvelope,
        key: Optional[str] = None,
    ) -> bool:
        """
        Publish an event to a Kafka topic.

        Args:
            topic: Target topic name
            event: Event envelope to publish
            key: Optional message key for partitioning

        Returns:
            True if message was queued successfully
        """
        if self._producer is None:
            self.connect()

        try:
            message_key = (key or event.event_id).encode("utf-8")
            message_value = event.model_dump_json().encode("utf-8")

            self._producer.produce(
                topic=topic,
                key=message_key,
                value=message_value,
                callback=self._delivery_callback,
                headers={
                    "event_type": event.event_type,
                    "event_id": event.event_id,
                    "source_service": event.metadata.source_service,
                    "correlation_id": event.metadata.correlation_id,
                },
            )

            # Trigger delivery callbacks
            self._producer.poll(0)

            logger.info(f"Event {event.event_id} queued to topic {topic}")
            return True

        except BufferError:
            logger.error(f"Producer buffer full, failed to queue event to {topic}")
            return False
        except Exception as e:
            logger.error(f"Failed to publish event to {topic}: {e}")
            return False

    def publish_event_sync(
        self,
        topic: str,
        event: EventEnvelope,
        key: Optional[str] = None,
        timeout: float = 10.0,
    ) -> bool:
        """
        Publish an event and wait for delivery confirmation.

        Args:
            topic: Target topic name
            event: Event envelope to publish
            key: Optional message key
            timeout: Timeout in seconds

        Returns:
            True if message was delivered successfully
        """
        if not self.publish_event(topic, event, key):
            return False

        # Flush to ensure delivery
        remaining = self._producer.flush(timeout=timeout)
        return remaining == 0

    def flush(self, timeout: float = 10.0) -> int:
        """
        Flush pending messages.

        Args:
            timeout: Timeout in seconds

        Returns:
            Number of messages still in queue
        """
        if self._producer is None:
            return 0
        return self._producer.flush(timeout=timeout)


class KafkaConsumerService:
    """
    Kafka consumer service using confluent-kafka.
    Handles event consumption with graceful shutdown.
    """

    def __init__(
        self,
        topics: list[str],
        group_id: str = "compliance-service-consumer",
    ):
        self._topics = topics
        self._group_id = group_id
        self._consumer: Optional[Consumer] = None
        self._running = False
        self._handlers: dict[str, Callable] = {}
        self._consumer_thread: Optional[threading.Thread] = None

    def _get_consumer_config(self) -> dict[str, Any]:
        """Get consumer configuration."""
        return {
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            "group.id": self._group_id,
            "client.id": f"compliance-service-consumer-{uuid4().hex[:8]}",
            "auto.offset.reset": settings.KAFKA_AUTO_OFFSET_RESET,
            "enable.auto.commit": settings.KAFKA_ENABLE_AUTO_COMMIT,
            "max.poll.interval.ms": settings.KAFKA_MAX_POLL_INTERVAL_MS,
            "session.timeout.ms": settings.KAFKA_SESSION_TIMEOUT_MS,
            "heartbeat.interval.ms": settings.KAFKA_HEARTBEAT_INTERVAL_MS,
        }

    def register_handler(
        self,
        topic: str,
        handler: Callable[[dict[str, Any], str], None],
    ) -> None:
        """
        Register a handler for a specific topic.

        Args:
            topic: Topic name
            handler: Callable that receives (event_data, topic)
        """
        self._handlers[topic] = handler
        logger.info(f"Registered handler for topic: {topic}")

    def connect(self) -> None:
        """Initialize the Kafka consumer connection."""
        if self._consumer is not None:
            return

        try:
            config = self._get_consumer_config()
            self._consumer = Consumer(config)
            self._consumer.subscribe(self._topics)
            logger.info(
                f"Kafka consumer connected, subscribed to {len(self._topics)} topics"
            )
        except Exception as e:
            logger.error(f"Failed to connect Kafka consumer: {e}")
            raise

    def disconnect(self) -> None:
        """Close the consumer."""
        self._running = False

        if self._consumer_thread is not None:
            self._consumer_thread.join(timeout=10)
            self._consumer_thread = None

        if self._consumer is not None:
            try:
                self._consumer.close()
                self._consumer = None
                logger.info("Kafka consumer disconnected")
            except Exception as e:
                logger.error(f"Error disconnecting consumer: {e}")

    def _process_message(self, msg) -> None:
        """Process a single message."""
        topic = msg.topic()

        try:
            value = msg.value().decode("utf-8")
            event_data = json.loads(value)

            handler = self._handlers.get(topic)
            if handler:
                handler(event_data, topic)
            else:
                logger.warning(f"No handler registered for topic: {topic}")

            # Commit offset after successful processing
            if not settings.KAFKA_ENABLE_AUTO_COMMIT:
                self._consumer.commit(asynchronous=False)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message from {topic}: {e}")
            if not settings.KAFKA_ENABLE_AUTO_COMMIT:
                self._consumer.commit(asynchronous=False)
        except Exception as e:
            logger.error(f"Error processing message from {topic}: {e}")
            # Don't commit on processing error - will be retried

    def _consume_loop(self) -> None:
        """Main consumption loop."""
        logger.info("Starting Kafka consumer loop")

        while self._running:
            try:
                msg = self._consumer.poll(timeout=1.0)

                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        logger.debug(
                            f"Reached end of partition {msg.topic()}[{msg.partition()}]"
                        )
                    else:
                        logger.error(f"Consumer error: {msg.error()}")
                    continue

                self._process_message(msg)

            except KafkaException as e:
                logger.error(f"Kafka exception in consumer loop: {e}")
                if not self._running:
                    break
            except Exception as e:
                logger.error(f"Unexpected error in consumer loop: {e}")

        logger.info("Kafka consumer loop stopped")

    def start(self) -> None:
        """Start consuming messages in a background thread."""
        if self._running:
            return

        self.connect()
        self._running = True
        self._consumer_thread = threading.Thread(
            target=self._consume_loop,
            daemon=True,
            name="kafka-consumer-compliance",
        )
        self._consumer_thread.start()
        logger.info("Kafka consumer started in background thread")

    def stop(self) -> None:
        """Stop consuming messages."""
        self.disconnect()


class KafkaAdminService:
    """Service for Kafka administrative operations."""

    def __init__(self):
        self._admin: Optional[AdminClient] = None

    def connect(self) -> None:
        """Initialize the admin client."""
        if self._admin is not None:
            return

        config = {"bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS}
        self._admin = AdminClient(config)
        logger.info("Kafka admin client connected")

    def create_topics(
        self,
        topics: list[str],
        num_partitions: int = 3,
        replication_factor: int = 1,
    ) -> None:
        """
        Create Kafka topics if they don't exist.

        Args:
            topics: List of topic names
            num_partitions: Number of partitions per topic
            replication_factor: Replication factor
        """
        if self._admin is None:
            self.connect()

        new_topics = [
            NewTopic(
                topic,
                num_partitions=num_partitions,
                replication_factor=replication_factor,
            )
            for topic in topics
        ]

        futures = self._admin.create_topics(new_topics)

        for topic, future in futures.items():
            try:
                future.result()
                logger.info(f"Created topic: {topic}")
            except Exception as e:
                if "TOPIC_ALREADY_EXISTS" in str(e):
                    logger.debug(f"Topic already exists: {topic}")
                else:
                    logger.error(f"Failed to create topic {topic}: {e}")


# Global instances
_producer: Optional[KafkaProducerService] = None
_consumer: Optional[KafkaConsumerService] = None


def get_producer() -> KafkaProducerService:
    """Get the global Kafka producer instance."""
    global _producer
    if _producer is None:
        _producer = KafkaProducerService()
    return _producer


def get_consumer(
    topics: Optional[list[str]] = None,
    group_id: Optional[str] = None,
) -> KafkaConsumerService:
    """Get or create a Kafka consumer instance."""
    global _consumer
    if _consumer is None:
        from app.core.topics import KafkaTopics

        if topics is None:
            topics = KafkaTopics.all_subscribed_topics()
        if group_id is None:
            group_id = settings.KAFKA_CONSUMER_GROUP_ID
        _consumer = KafkaConsumerService(topics=topics, group_id=group_id)
    return _consumer


def publish_compliance_event(
    topic: str,
    event: EventEnvelope,
    key: Optional[str] = None,
) -> bool:
    """
    Convenience function to publish a compliance event.

    Args:
        topic: Target topic name
        event: Event envelope to publish
        key: Optional message key

    Returns:
        True if message was queued successfully
    """
    producer = get_producer()
    return producer.publish_event(topic, event, key)


def health_check() -> dict[str, Any]:
    """
    Check Kafka connectivity health.

    Returns:
        Health status dictionary
    """
    status = {
        "producer_initialized": _producer is not None,
        "consumer_initialized": _consumer is not None,
        "consumer_running": _consumer._running if _consumer else False,
        "bootstrap_servers": settings.KAFKA_BOOTSTRAP_SERVERS,
        "consumer_group": settings.KAFKA_CONSUMER_GROUP_ID,
    }

    if _consumer:
        status["subscribed_topics_count"] = len(_consumer._topics)

    return status
