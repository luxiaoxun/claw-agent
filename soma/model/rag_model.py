# model/rag_model.py
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime

# Import Base at runtime to avoid circular import issues
import soma.model.db_model as db_model_module


class KnowledgeCollectionModel(db_model_module.Base):
    """知识库集合表"""
    __tablename__ = 'tb_knowledge_collection'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    chunk_size = Column(Integer, default=500)
    chunk_overlap = Column(Integer, default=50)
    metadata_ = Column(Text, nullable=True)
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    documents = relationship("RagDocumentModel", back_populates="collection", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "metadata": self.metadata_,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }


class RagDocumentModel(db_model_module.Base):
    """文档表"""
    __tablename__ = 'tb_rag_document'

    id = Column(Integer, primary_key=True, autoincrement=True)
    collection_id = Column(Integer, ForeignKey('tb_knowledge_collection.id', ondelete='CASCADE'))
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_size = Column(Integer, nullable=True)
    markdown_content = Column(Text, nullable=True)
    token_count = Column(Integer, nullable=True)
    metadata_ = Column(Text, nullable=True)
    create_time = Column(DateTime, default=datetime.now)

    collection = relationship("KnowledgeCollectionModel", back_populates="documents")
    chunks = relationship("RagChunkModel", back_populates="document", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "collection_id": self.collection_id,
            "file_name": self.file_name,
            "file_path": self.file_path,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "token_count": self.token_count,
            "metadata": self.metadata_,
            "create_time": self.create_time.isoformat() if self.create_time else None,
        }


class RagChunkModel(db_model_module.Base):
    """文档块表"""
    __tablename__ = 'tb_rag_chunk'

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey('tb_rag_document.id', ondelete='CASCADE'))
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False)
    token_count = Column(Integer, nullable=True)
    metadata_ = Column(Text, nullable=True)
    create_time = Column(DateTime, default=datetime.now)

    document = relationship("RagDocumentModel", back_populates="chunks")

    def to_dict(self):
        return {
            "id": self.id,
            "document_id": self.document_id,
            "chunk_index": self.chunk_index,
            "content": self.content,
            "token_count": self.token_count,
            "metadata": self.metadata_,
            "create_time": self.create_time.isoformat() if self.create_time else None,
        }


Index('idx_collection_name', KnowledgeCollectionModel.name)
Index('idx_document_collection', RagDocumentModel.collection_id)
Index('idx_chunk_document', RagChunkModel.document_id)
Index('idx_chunk_hash', RagChunkModel.content_hash)