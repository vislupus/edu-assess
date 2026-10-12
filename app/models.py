"""ORM модели."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def gen_code(n: int = 6) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(n))


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(16), index=True)  # teacher | student
    subject: Mapped[str | None] = mapped_column(String(120))  # за учители
    grade_label: Mapped[str | None] = mapped_column(String(16))  # за ученици, напр. "7а"
    avatar_color: Mapped[str] = mapped_column(String(16), default="#4f46e5")
    external_id: Mapped[str | None] = mapped_column(String(128), unique=True)  # за бъдещо SSO
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    @property
    def initials(self) -> str:
        parts = self.full_name.split()
        return "".join(p[0] for p in parts[:2]).upper()

    @property
    def is_teacher(self) -> bool:
        return self.role == "teacher"


class Curriculum(Base):
    __tablename__ = "curricula"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    subject: Mapped[str] = mapped_column(String(160))
    grade: Mapped[int] = mapped_column(Integer)
    grade_label: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(255))
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    @property
    def topics(self) -> list[dict]:
        return list(self.data.get("topics") or [])


class Classroom(Base):
    __tablename__ = "classrooms"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    subject: Mapped[str | None] = mapped_column(String(120))
    curriculum_id: Mapped[int | None] = mapped_column(ForeignKey("curricula.id"))
    join_code: Mapped[str] = mapped_column(String(12), unique=True, default=gen_code)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    teacher: Mapped[User] = relationship()
    curriculum: Mapped[Curriculum | None] = relationship()
    members: Mapped[list[ClassroomStudent]] = relationship(
        back_populates="classroom", cascade="all, delete-orphan"
    )


class ClassroomStudent(Base):
    __tablename__ = "classroom_students"

    classroom_id: Mapped[int] = mapped_column(
        ForeignKey("classrooms.id", ondelete="CASCADE"), primary_key=True
    )
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    classroom: Mapped[Classroom] = relationship(back_populates="members")
    student: Mapped[User] = relationship()


Index("ix_classroom_students_student", ClassroomStudent.student_id)


class Test(Base):
    __tablename__ = "tests"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    subject: Mapped[str | None] = mapped_column(String(120))
    grade_label: Mapped[str | None] = mapped_column(String(32))
    curriculum_id: Mapped[int | None] = mapped_column(ForeignKey("curricula.id"))
    # Контейнери (секции) на теста: [{key,title,type,count,difficulty,topics,points,source,instructions}]
    sections: Mapped[list] = mapped_column(JSON, default=list)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft | ready
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    owner: Mapped[User] = relationship()
    curriculum: Mapped[Curriculum | None] = relationship()
    questions: Mapped[list[Question]] = relationship(
        back_populates="test", cascade="all, delete-orphan", order_by="Question.position"
    )


class Question(Base):
    """Въпрос. Ако test_id е NULL – въпросът е в банката на учителя, иначе е част от тест."""

    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    test_id: Mapped[int | None] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"))
    section_key: Mapped[str | None] = mapped_column(String(32))
    position: Mapped[int] = mapped_column(Integer, default=0)
    source_question_id: Mapped[int | None] = mapped_column(Integer)

    type: Mapped[str] = mapped_column(String(32), index=True)
    stem: Mapped[str] = mapped_column(Text, default="")  # HTML (Quill)
    data: Mapped[dict] = mapped_column(JSON, default=dict)  # специфично за типа
    difficulty: Mapped[int] = mapped_column(Integer, default=2)  # 1 ниска, 2 средна, 3 висока
    points: Mapped[float] = mapped_column(Float, default=1.0)
    curriculum_id: Mapped[int | None] = mapped_column(ForeignKey("curricula.id"))
    topic: Mapped[str | None] = mapped_column(String(255))
    tags: Mapped[str] = mapped_column(String(255), default="")
    source: Mapped[str] = mapped_column(String(16), default="manual")  # manual | ai | bank
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    test: Mapped[Test | None] = relationship(back_populates="questions")


Index("ix_questions_test_pos", Question.test_id, Question.position)
Index("ix_questions_bank", Question.owner_id, Question.test_id)


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    test_id: Mapped[int] = mapped_column(ForeignKey("tests.id"), index=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    mode: Mapped[str] = mapped_column(String(16), default="practice")  # practice | exam
    start_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    end_at: Mapped[datetime | None] = mapped_column(DateTime)
    time_limit_min: Mapped[int | None] = mapped_column(Integer)
    attempts_allowed: Mapped[int] = mapped_column(Integer, default=1)  # 0 = неограничено
    shuffle_questions: Mapped[bool] = mapped_column(Boolean, default=False)
    shuffle_options: Mapped[bool] = mapped_column(Boolean, default=False)
    variants: Mapped[int] = mapped_column(Integer, default=1)
    show_results: Mapped[str] = mapped_column(
        String(16), default="immediately"
    )  # immediately|after_end|never
    max_warnings: Mapped[int] = mapped_column(Integer, default=3)
    grade_scale: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | closed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    test: Mapped[Test] = relationship()
    teacher: Mapped[User] = relationship()
    classrooms: Mapped[list[AssignmentClassroom]] = relationship(
        back_populates="assignment", cascade="all, delete-orphan"
    )

    @property
    def is_exam(self) -> bool:
        return self.mode == "exam"


class AssignmentClassroom(Base):
    __tablename__ = "assignment_classrooms"

    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE"), primary_key=True
    )
    classroom_id: Mapped[int] = mapped_column(
        ForeignKey("classrooms.id", ondelete="CASCADE"), primary_key=True
    )

    assignment: Mapped[Assignment] = relationship(back_populates="classrooms")
    classroom: Mapped[Classroom] = relationship()


Index("ix_assignment_classrooms_class", AssignmentClassroom.classroom_id)


class Attempt(Base):
    __tablename__ = "attempts"
    __table_args__ = (UniqueConstraint("assignment_id", "student_id", "attempt_no"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    attempt_no: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default="in_progress")  # in_progress|submitted|annulled
    variant: Mapped[int] = mapped_column(Integer, default=1)
    layout: Mapped[dict] = mapped_column(JSON, default=dict)  # {"order":[qid...], "options":{qid:[ids]}}
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    max_score: Mapped[float] = mapped_column(Float, default=0.0)
    percent: Mapped[float] = mapped_column(Float, default=0.0)
    grade: Mapped[float | None] = mapped_column(Float)
    warnings: Mapped[int] = mapped_column(Integer, default=0)
    needs_manual: Mapped[bool] = mapped_column(Boolean, default=False)
    graded_at: Mapped[datetime | None] = mapped_column(DateTime)
    teacher_feedback: Mapped[str] = mapped_column(Text, default="")
    last_violation_at: Mapped[datetime | None] = mapped_column(DateTime)

    assignment: Mapped[Assignment] = relationship()
    student: Mapped[User] = relationship()
    answers: Mapped[list[Answer]] = relationship(back_populates="attempt", cascade="all, delete-orphan")
    events: Mapped[list[AttemptEvent]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan", order_by="AttemptEvent.created_at"
    )


Index("ix_attempts_assignment_student", Attempt.assignment_id, Attempt.student_id)


class Answer(Base):
    __tablename__ = "answers"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("attempts.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    response: Mapped[dict | list | str | None] = mapped_column(JSON)
    auto_score: Mapped[float | None] = mapped_column(Float)  # в точки
    manual_score: Mapped[float | None] = mapped_column(Float)  # в точки
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    needs_manual: Mapped[bool] = mapped_column(Boolean, default=False)
    feedback: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    attempt: Mapped[Attempt] = relationship(back_populates="answers")
    question: Mapped[Question] = relationship()

    @property
    def final_score(self) -> float:
        if self.manual_score is not None:
            return self.manual_score
        return self.auto_score or 0.0


class AttemptEvent(Base):
    __tablename__ = "attempt_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("attempts.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32))  # start|violation|warning|annulled|submit|autosubmit
    detail: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    attempt: Mapped[Attempt] = relationship(back_populates="events")


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(64), unique=True)
    mime: Mapped[str] = mapped_column(String(120))
    size: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
