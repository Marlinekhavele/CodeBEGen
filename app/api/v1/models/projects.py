from sqlalchemy import Column, String, Text

from app.api.v1.models.base import BaseTableModel


class Project(BaseTableModel):
    __tablename__ = "project"

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    slug = Column(String(50), nullable=False, unique=True)
    language = Column(String(50), nullable=False)
    framework = Column(String(50), nullable=False)
