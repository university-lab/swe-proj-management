from sqlalchemy import (
   create_engine, select, inspect,
   String, Integer, DateTime, ForeignKey, Text, UniqueConstraint
)
from sqlalchemy.orm import (
    sessionmaker, relationship, mapped_column, make_transient,
    DeclarativeBase, Mapped,
)
from sqlalchemy.sql import func
from sqlalchemy_utils import database_exists, create_database, drop_database
from copy import deepcopy


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    full_name: Mapped[str] = mapped_column(String(32), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ProjectEntry(Base):
    __tablename__ = 'project_entries'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        Integer, ForeignKey('users.id'), nullable=False
    )
    changes: Mapped[list["HistoricalProject"]] = relationship(
        "HistoricalProject",
        primaryjoin="ProjectEntry.id == HistoricalProject.project_id"
    )


class HistoricalProject(Base):
    __tablename__ = 'historical_projects'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey('project_entries.id'), nullable=False
    )
    created_by: Mapped[int] = mapped_column(
        Integer, ForeignKey('users.id'), nullable=False
    )
    urgency: Mapped[str] = mapped_column(String(32), nullable=True)
    notes: Mapped[Text] = mapped_column(Text(), nullable=True)
    deadline: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    project_users: Mapped[list["ProjectUser"]] = relationship(
        "ProjectUser",
        primaryjoin="HistoricalProject.id == ProjectUser.project_id",
        lazy="subquery",
        cascade="all, delete-orphan"
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ProjectUser(Base):
    __tablename__ = 'project_users'
    __table_args__ = (
        UniqueConstraint('project_id', 'user_id', name='uq_project_user'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey('historical_projects.id')
    )
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'))


class _Project:
    def __init__(self, engine, id, owner_id):
        self.engine = engine
        self._session_factory = sessionmaker(bind=self.engine)
        self.id = id
        self.owner_id = owner_id

    def has_user(self, id, historical_project=None):
        if historical_project is None:
            historical_project = self.get_latest()
        else:
            historical_project = self.get(historical_project)
        return any(
            project_user.user_id == id
            for project_user in historical_project.project_users
        )
                

    def get(self, id):
        with self._session_factory() as session:
            return session.scalars(
                select(HistoricalProject)
                .where(
                    HistoricalProject.id == id,
                    HistoricalProject.project_id == self.id
                )
            ).one()

    def get_latest(self):
        return self.get_history()[-1]

    def get_history(self):
        with self._session_factory() as session:
            return session.scalars(
                select(HistoricalProject)
                .where(HistoricalProject.project_id == self.id)
            ).all()

    def get_users(self, historical_project=None):
        with self._session_factory() as session:
            if historical_project is None:
                historical_project = self.get_latest()
            stmt = (
                select(User).join(
                    ProjectUser,
                    User.id == ProjectUser.user_id
                ).where(
                    ProjectUser.project_id == historical_project.id
                )
            )
            return session.scalars(stmt).all()

    def update(self, updated_by, **kwargs):
        with self._session_factory() as session:
            latest_version = self.get_latest()
            new_version = HistoricalProject()
            session.add(latest_version)

            for column in inspect(latest_version.__class__).c:
                if any(getattr(column, attr, None) for attr in (
                    "server_default", "onupdate"
                )):
                    continue
                elif column.primary_key and not column.foreign_keys:
                    continue
                setattr(
                    new_version, column.name,
                    kwargs.get(column.name) or getattr(
                        latest_version, column.name
                    )
                )
            new_version.created_by = updated_by
            session.add(new_version)
            session.commit()

            if (users := kwargs.get("users")) is not None:
                kwargs["users"] = [ProjectUser(
                    user_id=user,
                ) for user in set(users) | set([self.owner_id])]

            new_version.project_users = [
                ProjectUser(
                    project_id=new_version.id,
                    user_id=project_user.user_id
                )
                for project_user in kwargs.get(
                    "users", latest_version.project_users
                )
            ]

            session.add_all(new_version.project_users)
            session.commit()

    def remove(self, expr):
        with self._session_factory() as session:
            historical_project = session.scalars(
                select(HistoricalProject).where(expr)
            ).first()
            project_id = historical_project.project_id
            count = session.scalars(
                select(func.count(HistoricalProject.id)).where(
                    HistoricalProject.project_id == project_id
                )
            ).one()
            if count == 1:
                raise ValueError(
                    "Cannot delete the last historical project of a "
                    "project entry"
                )
            session.delete(historical_project)
            session.commit()


class UserDatabase:
    def __init__(self, engine):
        self.engine = engine
        self._session_factory = sessionmaker(bind=self.engine)

    def get_all(self):
        with self._session_factory() as session:
            return [*session.scalars(select(User))]

    def get(self, expr):
        with self._session_factory() as session:
            return session.scalars(select(User).where(expr)).all()[0]

    def create(self, *args, **kwargs):
        with self._session_factory() as session:
            user = User(*args, **kwargs)
            session.add(user)
            session.commit()
            return user.id

    def update(self, id, **kwargs):
        with self._session_factory() as session:
            session.query(User)\
                   .filter(User.id == id)\
                   .update(kwargs)
            session.commit()


class Database:
    def __init__(self, uri, *, drop_before_load=False):
        self.engine = create_engine(uri)
        if not database_exists(self.engine.url):
            create_database(self.engine.url)
        elif drop_before_load:
            drop_database(self.engine.url)
            create_database(self.engine.url)
        self._session_factory = sessionmaker(bind=self.engine)
        self.users = UserDatabase(self.engine)
        Base.metadata.create_all(self.engine)

    def create_project(self, owner_id, users=None, *args, **kwargs):
        users = users or []
        with self._session_factory() as session:
            project_entry = ProjectEntry(
                changes=[
                    historical_project := HistoricalProject(
                        created_by=owner_id,
                        *args, **kwargs
                    )
                ],
                owner_id=owner_id
            )
            session.add(project_entry)
            session.flush()

            users.append(self.users.get(User.id == owner_id))
            for idx, user in enumerate(users):
                if isinstance(user, int):
                    users[idx] = self.users.get(User.id == user)
            converted_users = [ProjectUser(
                project_id=historical_project.id,
                user_id=user.id
            ) for user in users]

            session.add_all(converted_users)
            session.commit()

            return _Project(self.engine, project_entry.id, owner_id)

    def get_project(self, expr):
        with self._session_factory() as session:
            project = session.scalars(
                select(ProjectEntry).where(expr)
            ).all()[0]
            return _Project(self.engine, project.id, project.owner_id)

    def get_projects(self):
        with self._session_factory() as session:
            return [*map(
                lambda p: _Project(self.engine, p.id, p.owner_id),
                session.scalars(select(ProjectEntry)).all()
            )]
