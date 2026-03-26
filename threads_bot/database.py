from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.orm import DeclarativeBase, Session
from .config import DB_PATH


class Base(DeclarativeBase):
    pass


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True)
    content = Column(Text, nullable=False)
    threads_post_id = Column(String, nullable=True)
    status = Column(String, default="pending")  # pending / published / failed
    scheduled_at = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)
    topic = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    error_message = Column(Text, nullable=True)


class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"

    id = Column(Integer, primary_key=True)
    job_id = Column(String, unique=True, nullable=False)
    topic = Column(String, nullable=False)
    cron_expr = Column(String, nullable=False)  # e.g. "0 9 * * *"
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
Base.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)
