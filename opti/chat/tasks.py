from uuid import UUID

from celery import Celery
import asyncio
from sqlalchemy import update, or_, and_

from opti.core.config import CELERY_BROKER, logger
from opti.core.database import async_session_maker
from opti.chat.models import Message
from opti.core.redis import init_redis_pool, get_redis

celery = Celery('tasks', broker=CELERY_BROKER)
celery.conf.timezone = 'UTC'
celery.conf.beat_schedule = {
    'sync_read_message': {
        'task': 'opti.chat.tasks.sync_read_message',
        'schedule': 5,
    },
}
celery.conf.broker_connection_retry_on_startup = True


async def sync_read_message_():
    await init_redis_pool()
    redis = get_redis()

    p = redis.pipeline()
    p.hgetall("unsync_read_message")
    p.delete("unsync_read_message")
    result = await p.execute()
    read_messages = result[0]
    if not read_messages:
        return

    db_session = async_session_maker()
    query = update(Message).values(is_viewed=True).where(
        or_(
            *(and_(
                Message.id.in_(UUID(i) for i in value.strip(';').split(';')),
                Message.recipient_id == recipient_id
            ) for recipient_id, value in read_messages.items()
            )
        ))
    await db_session.execute(query)
    await db_session.commit()


@celery.task
def sync_read_message():
    asyncio.run(sync_read_message_())
    logger.info("sync read message success")
