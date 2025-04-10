from sqlalchemy import Column, ForeignKey, String, Text, UniqueConstraint, DateTime, Boolean

from app.api.v1.models.base import BaseTableModel


class EndPoint(BaseTableModel):
    __tablename__ = "endpoints"

    path = Column(String(512), nullable=False)
    method = Column(String(10), nullable=False)
    description = Column(Text, nullable=True)
    file_hash = Column(String, nullable=False)
    project_id = Column(
        String, ForeignKey("project.id", ondelete="CASCADE"), nullable=False
    )
    # Fields for soft delete
    is_deleted = Column(Boolean, default=False, nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    

    # Composite unique constraint for path + method + project_id
    __table_args__ = (
        UniqueConstraint(
            "path", "method", "project_id", name="unique_path_method_project"
        ),
    )

    def __repr__(self):
        return f"EndPoint {self.method} {self.path}"
