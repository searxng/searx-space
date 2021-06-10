from sqlalchemy import Table, Column, Integer, String, ForeignKey, create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, relationship

from .config import DATABASE_URL


Base = declarative_base()
fork_commit_table = Table(
    'fork_commit',
    Base.metadata,
    Column('fork_id', Integer, ForeignKey('fork.id')),
    Column('commit_id', Integer, ForeignKey('vcs_commit.id'))
)
commit_content_table = Table(
    'commit_content',
    Base.metadata,
    Column('commit_id', Integer, ForeignKey('vcs_commit.id')),
    Column('content_id', Integer, ForeignKey('content.id'))
)


class Content(Base):
    __tablename__ = 'content'

    id = Column(Integer, primary_key=True)
    sha = Column(String, nullable=False)
    commits = relationship("Commit",
                           secondary=commit_content_table,
                           back_populates="contents",
                           cascade="all",
                           innerjoin=True)


class Commit(Base):
    __tablename__ = 'vcs_commit'

    id = Column(Integer, primary_key=True)
    sha = Column(String, nullable=False)
    contents = relationship("Content",
                            secondary=commit_content_table,
                            back_populates="commits",
                            cascade="all",
                            innerjoin=True)
    forks = relationship("Fork",
                         secondary=fork_commit_table,
                         back_populates="commits",
                         cascade="all",
                         innerjoin=True)


class Fork(Base):
    __tablename__ = 'fork'

    id = Column(Integer, primary_key=True)
    git_url = Column(String, nullable=False)
    commits = relationship("Commit",
                           secondary=fork_commit_table,
                           back_populates="forks",
                           cascade="all",
                           innerjoin=True)


engine = create_engine(DATABASE_URL, future=True)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine, future=True)
