from sqlalchemy.exc import IntegrityError
from src.db import Database, HistoricalProject, User, ProjectEntry
import unittest
import os


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.db = Database(os.environ['SQL_TEST_URI'], drop_before_load=True)

    def test_create_users(self):
        with self.assertRaises(
            IntegrityError, msg="Username/password hash are non-optional"
        ):
            self.db.users.create(username=None, password_hash=None)
        self.db.users.create(username="TestUser", password_hash="TestPassword")
        with self.assertRaises(
            IntegrityError, msg="Usernames cannot be repeated"
        ):
            self.db.users.create(
                username="TestUser", password_hash="TestPassword"
            )
        self.db.users.create(
            username="TestUser1", password_hash="TestPassword"
        )
        users = self.db.users.get_all()
        self.assertTrue(len(users) == 2)

    def test_create_project(self):
        user1 = self.db.users.create(
            username="TestUser1", password_hash="TestPassword"
        )
        user2 = self.db.users.create(
            username="TestUser2", password_hash="TestPassword"
        )
        with self.assertRaises(
            IntegrityError, msg="Project cannot contain duplicate users"
        ):
            proj1 = self.db.create_project(owner_id=user1, users=[user1])
        with self.assertRaises(
            IntegrityError, msg="Project cannot contain duplicate users"
        ):
            proj1 = self.db.create_project(
                owner_id=user1, users=[user2, user2]
            )
        proj1 = self.db.create_project(owner_id=user1, users=[user2])
        self.assertEqual(proj1.owner_id, user1)

    def test_update_project(self):
        user1 = self.db.users.create(
            username="TestUser1", password_hash="TestPassword"
        )
        user2 = self.db.users.create(
            username="TestUser2", password_hash="TestPassword"
        )
        proj1 = self.db.create_project(owner_id=user1, urgency="TestUrgency1")
        proj1.update(users=[user2], updated_by=user1)
        proj1.update(urgency="TestUrgency2", updated_by=user1)
        proj1.update(users=[], updated_by=user1)
        self.assertEqual(
            [*map(lambda p: len(proj1.get_users(p)), proj1.get_history())],
            [1, 2, 2, 1]
        )
        self.assertEqual(
            proj1.get_history()[2].urgency, "TestUrgency2"
        )

    def test_delete_revision(self):
        user1 = self.db.users.create(
            username="TestUser1", password_hash="TestPassword"
        )
        user2 = self.db.users.create(
            username="TestUser2", password_hash="TestPassword"
        )
        proj1 = self.db.create_project(owner_id=user1, urgency="TestUrgency1")
        proj1.update(urgency="TestUrgency2", updated_by=user1)
        proj1.update(urgency="TestUrgency3", users=[], updated_by=user1)
        self.assertEqual(proj1.get_latest().urgency, "TestUrgency3")
        proj1.remove(HistoricalProject.id == proj1.get_latest().id)
        self.assertEqual(proj1.get_latest().urgency, "TestUrgency2")
        proj1.remove(HistoricalProject.id == proj1.get_latest().id)
        self.assertEqual(proj1.get_latest().urgency, "TestUrgency1")
        with self.assertRaises(
            ValueError, msg="Can't remove the last project revision"
        ):
            proj1.remove(HistoricalProject.id == proj1.get_latest().id)

    def test_get_user(self):
        user = self.db.users.create(username="TestUser", password_hash="TestHash")
        retrieved_user = self.db.users.get(User.id == user)
        self.assertEqual(retrieved_user.username, "TestUser")

    def test_update_user(self):
        user = self.db.users.create(username="TestUser", password_hash="TestHash")
        self.db.users.update(user, full_name="Test Full Name")
        updated_user = self.db.users.get(User.id == user)
        self.assertEqual(updated_user.full_name, "Test Full Name")

    def test_get_project(self):
        user = self.db.users.create(username="TestUser", password_hash="TestHash")
        project = self.db.create_project(owner_id=user, urgency="High")
        retrieved_project = self.db.get_project(ProjectEntry.id == project.id)
        self.assertEqual(retrieved_project.get_latest().urgency, "High")

    def test_get_project_users(self):
        user1 = self.db.users.create(username="User1", password_hash="Hash1")
        user2 = self.db.users.create(username="User2", password_hash="Hash2")
        project = self.db.create_project(owner_id=user1, users=[user2])
        project_users = project.get_users()
        self.assertEqual(len(project_users), 2)
        self.assertIn(user1, [u.id for u in project_users])
        self.assertIn(user2, [u.id for u in project_users])

    def test_get_non_existent_project(self):
        with self.assertRaises(IndexError):
            self.db.get_project(ProjectEntry.id == 9999)

