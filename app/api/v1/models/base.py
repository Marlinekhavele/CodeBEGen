"""This is the Base Model Class"""

import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, String
from uuid6 import uuid7

from app.api.db.database import Base


class BaseTableModel(Base):
    """This model creates helper methods for all models"""

    __abstract__ = True

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid7()))
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        """Convert model instance to dictionary, handling enum values."""
        return {
            c.name: (
                getattr(self, c.name).value
                if isinstance(getattr(self, c.name), enum.Enum)
                else getattr(self, c.name)
            )
            for c in self.__table__.columns
        }

    @classmethod
    def get_all(cls, session):
        """Retrieve all instances of the model."""
        return session.query(cls).all()

    @classmethod
    def get_by_id(cls, id, session):
        """Retrieve an instance by ID."""
        return session.query(cls).filter(cls.id == id).first()
