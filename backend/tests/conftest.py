"""Pytest configuration and shared test fixtures for Knovera."""

from pathlib import Path
import sys
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure repository root is on sys.path so 'backend' package is importable
repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from backend.app.core.auth import create_access_token, hash_password
from backend.app.db.base import Base
from backend.app.db.session import get_db
from backend.app.main import app
import backend.app.models  # noqa: F401
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.storage import get_storage_service
from backend.app.storage.local import LocalStorageService


@pytest.fixture(scope="session")
def client() -> Generator[TestClient, None, None]:
    """TestClient fixture providing an HTTP client bound to the FastAPI app."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """In-memory SQLite test database fixture."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def storage_service(tmp_path: Path) -> LocalStorageService:
    """Isolated local storage service pointing to a temporary test directory."""
    return LocalStorageService(tmp_path / "documents")


@pytest.fixture
def test_client(
    db_session: Session,
    storage_service: LocalStorageService,
) -> Generator[TestClient, None, None]:
    """TestClient with overridden database and storage dependencies."""

    def override_get_db():
        yield db_session

    def override_storage():
        return storage_service

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage_service] = override_storage

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Creates and returns a test user in the database."""
    user = User(
        email="researcher@knovera.ai",
        password_hash=hash_password("SuperSecretPassword123!"),
        display_name="Dr. Jane Doe",
        status="active",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict[str, str]:
    """Returns Authorization header with Bearer token for test_user."""
    token = create_access_token(test_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_user(db_session: Session) -> User:
    """Creates a second test user to test cross-user isolation."""
    user = User(
        email="unauthorized@knovera.ai",
        password_hash=hash_password("AnotherPassword456!"),
        display_name="Other User",
        status="active",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def other_auth_headers(other_user: User) -> dict[str, str]:
    """Returns Authorization header for other_user."""
    token = create_access_token(other_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_workspace(db_session: Session, test_user: User) -> Workspace:
    """Creates and returns a workspace owned by test_user."""
    ws = Workspace(
        owner_user_id=test_user.id,
        name="Quantum Computing Lab",
        description="Quantum circuits and entanglement research",
    )
    db_session.add(ws)
    db_session.commit()
    db_session.refresh(ws)
    return ws


@pytest.fixture(autouse=True)
def setup_rag_test_defaults():
    """Provides fast deterministic fake embeddings, fake reranker, and in-memory Chroma for isolated test runs."""
    from backend.app.db.chroma import set_chroma_client
    from backend.app.rag.embeddings.fake_provider import DeterministicFakeEmbeddingProvider
    from backend.app.rag.embeddings.model_manager import EmbeddingModelManager
    from backend.app.rag.reranker.fake_reranker import FakeCrossEncoder
    from backend.app.rag.reranker.manager import CrossEncoderModelManager
    from backend.app.rag.vector_store.fake_client import InMemoryChromaClient

    fake_chroma = InMemoryChromaClient()
    fake_provider = DeterministicFakeEmbeddingProvider()
    fake_cross_encoder = FakeCrossEncoder()

    set_chroma_client(fake_chroma)
    EmbeddingModelManager.get_instance().set_provider(fake_provider)
    CrossEncoderModelManager.get_instance().set_model(fake_cross_encoder)

    yield fake_chroma, fake_provider, fake_cross_encoder

    set_chroma_client(None)
    EmbeddingModelManager.get_instance().set_provider(None)
    CrossEncoderModelManager.get_instance().set_model(None)
