from unittest import IsolatedAsyncioTestCase
from datetime import datetime, timezone, timedelta

from src.notifications.email import get_email_sender
from src.database.models.accounts import (
    UserModel,
    UserGroupModel,
    UserGroupEnum,
    ActivationTokenModel,
    PasswordResetTokenModel,
    RefreshTokenModel,
)
from src.database.postgresql import async_session
from sqlalchemy import text, select
from httpx import AsyncClient, ASGITransport
from src.main import app
from unittest.mock import MagicMock
import sys
import asyncio
from src.config.settings import settings

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class TestUserRegistration(IsolatedAsyncioTestCase):

    async def async_mock(self, *args, **kwargs):
        return None

    async def asyncSetUp(self):
        if not settings.TESTING:
            print("Error variable TESTING=False.")
            sys.exit(1)
        if "_test" not in settings.database_url:
            print("The database is not intended for testing.")
            sys.exit(1)
        self.session = async_session()
        await self.session.execute(
            text(
                "TRUNCATE TABLE user_groups, users, activation_tokens, refresh_tokens, user_profiles RESTART IDENTITY CASCADE"
            )
        )
        await self.session.commit()

        user_group = UserGroupModel(name=UserGroupEnum.USER)
        self.session.add(user_group)
        await self.session.commit()
        await self.session.refresh(user_group)
        self.user_group_id = user_group.id

        self.mock_email_sender = MagicMock()

        self.mock_email_sender.send_activation_email = MagicMock(
            side_effect=self.async_mock
        )
        self.mock_email_sender.send_activation_complete_email = MagicMock(
            side_effect=self.async_mock
        )
        app.dependency_overrides[get_email_sender] = lambda: self.mock_email_sender

        self.client = AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        )

    async def asyncTearDown(self):
        app.dependency_overrides.clear()
        await self.session.close()

    async def test_register_success(self):
        payload = {
            "email": "test@gmail.com",
            "password": "Password123!",
        }
        response = await self.client.post("/accounts/register/", json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["email"], payload["email"])
        self.assertIn("id", data)
        result = await self.session.execute(
            select(UserModel).where(UserModel.email == payload["email"])
        )
        user_in_db = result.scalar_one_or_none()
        self.assertIsNotNone(user_in_db)
        assert user_in_db is not None
        self.assertEqual(user_in_db.email, payload["email"])
        self.mock_email_sender.send_activation_email.assert_called_once()

    async def test_register_invalid_email(self):
        payload = {
            "email": "testtttttttttttt",
            "password": "Password123!",
        }
        response = await self.client.post("/accounts/register/", json=payload)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.mock_email_sender.send_activation_email.call_count, 0)

    async def test_register_duplicate_email(self):
        payload = {
            "email": "test@gmail.com",
            "password": "Password123!",
        }
        await self.client.post("/accounts/register/", json=payload)
        response = await self.client.post("/accounts/register/", json=payload)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["detail"],
            f"A user with this email {payload["email"]} already exists.",
        )
        self.assertEqual(self.mock_email_sender.send_activation_email.call_count, 1)

    async def test_activation_success(self):
        new_user = UserModel.create(
            email="test@gmail.com",
            raw_password="Password123!",
            group_id=self.user_group_id,
        )
        self.session.add(new_user)
        await self.session.flush()
        activation_token = ActivationTokenModel(user_id=new_user.id)
        self.session.add(activation_token)
        await self.session.commit()

        token = activation_token.token
        response = await self.client.get(
            "/accounts/activate/", params={"token": token, "email": new_user.email}
        )
        self.assertEqual(response.status_code, 200)
        await self.session.refresh(new_user)
        self.assertTrue(new_user.is_active)
        token_result = await self.session.execute(
            select(ActivationTokenModel).where(ActivationTokenModel.token == token)
        )
        self.assertIsNone(token_result.scalar_one_or_none())

    async def test_activation_invalid_token(self):
        new_user = UserModel.create(
            email="bad_token@gmail.com",
            raw_password="Password123!",
            group_id=self.user_group_id,
        )
        self.session.add(new_user)
        await self.session.commit()

        response = await self.client.get(
            "/accounts/activate/",
            params={"token": "wrong-token-123", "email": new_user.email},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"], "Invalid or expired activation token."
        )

        await self.session.refresh(new_user)
        self.assertFalse(new_user.is_active)

    async def test_activation_token_mismatch(self):
        user_a = UserModel.create(
            email="user_a@test.com",
            raw_password="Password!123",
            group_id=self.user_group_id,
        )
        self.session.add(user_a)
        await self.session.flush()
        token_a = ActivationTokenModel(user_id=user_a.id)
        self.session.add(token_a)

        user_b = UserModel.create(
            email="user_b@test.com",
            raw_password="Password!123",
            group_id=self.user_group_id,
        )
        self.session.add(user_b)
        await self.session.commit()

        response = await self.client.get(
            "/accounts/activate/",
            params={"token": token_a.token, "email": user_b.email},
        )

        self.assertEqual(response.status_code, 400)
        await self.session.refresh(user_b)
        self.assertFalse(user_b.is_active)

    async def test_activation_token_expired(self):
        new_user = UserModel.create(
            email="expired@gmail.com",
            raw_password="Password123!",
            group_id=self.user_group_id,
        )
        self.session.add(new_user)
        await self.session.flush()

        activation_token = ActivationTokenModel(user_id=new_user.id)
        self.session.add(activation_token)
        activation_token.expires_at = datetime.now(timezone.utc) - timedelta(days=2)
        await self.session.commit()

        response = await self.client.get(
            "/accounts/activate/",
            params={"token": activation_token.token, "email": new_user.email},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"], "Invalid or expired activation token."
        )

        await self.session.refresh(new_user)
        self.assertFalse(new_user.is_active)

    async def test_login_success(self):
        email = "login_test@gmail.com"
        password = "Password123!"
        user = UserModel.create(
            email=email,
            raw_password=password,
            group_id=self.user_group_id,
        )
        user.is_active = True
        self.session.add(user)
        await self.session.commit()

        payload = {
            "email": email,
            "password": password,
        }
        response = await self.client.post("/accounts/login/", json=payload)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("access_token", data)
        self.assertIn("refresh_token", data)
        self.assertEqual(data["token_type"], "bearer")

    async def test_login_inactive_user(self):
        email = "not_active@gmail.com"
        password = "Password123!"
        user = UserModel.create(
            email=email,
            raw_password=password,
            group_id=self.user_group_id,
        )
        self.session.add(user)
        await self.session.commit()

        payload = {"email": email, "password": password}
        response = await self.client.post("/accounts/login/", json=payload)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "User account is not activated.")

    async def test_refresh_token_success(self):
        email = "refresh@test.com"
        password = "Password123!"
        user = UserModel.create(
            email=email, raw_password=password, group_id=self.user_group_id
        )
        user.is_active = True
        self.session.add(user)
        await self.session.commit()

        login_resp = await self.client.post(
            "/accounts/login/", json={"email": email, "password": password}
        )
        tokens = login_resp.json()
        old_access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]

        await asyncio.sleep(1)

        refresh_payload = {"refresh_token": refresh_token}
        response = await self.client.post("/accounts/refresh/", json=refresh_payload)

        self.assertEqual(response.status_code, 200)
        new_tokens = response.json()

        self.assertIn("access_token", new_tokens)
        self.assertNotEqual(new_tokens["access_token"], old_access_token)
        self.assertEqual(new_tokens["token_type"], "bearer")

    async def test_refresh_token_invalid_format(self):
        response = await self.client.post(
            "/accounts/refresh/", json={"refresh_token": "not-a-jwt-token"}
        )
        self.assertEqual(response.status_code, 400)

    async def test_refresh_token_not_in_db(self):
        response = await self.client.post(
            "/accounts/refresh/", json={"refresh_token": "fake-token-123"}
        )
        self.assertEqual(response.status_code, 400)


class TestPasswordManagement(IsolatedAsyncioTestCase):
    async def async_mock(self, *args, **kwargs):
        return None

    async def asyncSetUp(self):
        self.session = async_session()
        await self.session.execute(
            text(
                "TRUNCATE TABLE user_groups, users, activation_tokens, refresh_tokens, user_profiles, password_reset_tokens RESTART IDENTITY CASCADE"
            )
        )
        await self.session.commit()

        user_group = UserGroupModel(name=UserGroupEnum.USER)
        self.session.add(user_group)
        await self.session.commit()
        await self.session.refresh(user_group)
        self.user_group_id = user_group.id

        self.user = UserModel.create(
            email="test@gmail.com",
            raw_password="Password123!",
            group_id=self.user_group_id,
        )
        self.user.is_active = True
        self.session.add(self.user)
        await self.session.commit()

        self.mock_email_sender = MagicMock()

        self.mock_email_sender.send_password_reset_email = MagicMock(
            side_effect=self.async_mock
        )
        self.mock_email_sender.send_password_reset_complete_email = MagicMock(
            side_effect=self.async_mock
        )
        app.dependency_overrides[get_email_sender] = lambda: self.mock_email_sender

        self.client = AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        )

    async def asyncTearDown(self):
        app.dependency_overrides.clear()
        await self.session.close()

    async def test_password_reset_success(self):
        response = await self.client.post(
            "/accounts/password-reset/request/", json={"email": self.user.email}
        )
        self.assertEqual(response.status_code, 200)
        self.mock_email_sender.send_password_reset_email.assert_called_once()

        stmt = select(PasswordResetTokenModel).where(
            PasswordResetTokenModel.user_id == self.user.id
        )
        result = await self.session.execute(stmt)
        token_record = result.scalar_one()
        reset_token = token_record.token

        new_password = "Password123@"
        confirm_payload = {
            "token": reset_token,
            "email": self.user.email,
            "password": new_password,
        }
        confirm_response = await self.client.post(
            "/accounts/password-reset/complete/", json=confirm_payload
        )
        self.assertEqual(confirm_response.status_code, 200)
        self.mock_email_sender.send_password_reset_complete_email.assert_called_once()

        result_after = await self.session.execute(stmt)
        self.assertIsNone(result_after.scalar_one_or_none())

        login_payload = {
            "email": self.user.email,
            "password": new_password,
        }
        login_response = await self.client.post("/accounts/login/", json=login_payload)
        self.assertEqual(login_response.status_code, 200)
        self.assertIn("access_token", login_response.json())
        self.assertIn("refresh_token", login_response.json())

        old_login_payload = {
            "email": self.user.email,
            "password": "Password123!",
        }
        old_login_response = await self.client.post(
            "/accounts/login/", json=old_login_payload
        )
        self.assertEqual(old_login_response.status_code, 401)

    async def test_change_password_authenticated_success(self):
        login_res = await self.client.post(
            "/accounts/login/",
            json={"email": self.user.email, "password": "Password123!"},
        )
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        new_pass = "UpdatedPass777!"
        change_payload = {"old_password": "Password123!", "new_password": new_pass}
        response = await self.client.post(
            "/accounts/password-change/", json=change_payload, headers=headers
        )
        self.assertEqual(response.status_code, 200)

        stmt = select(RefreshTokenModel).where(
            RefreshTokenModel.user_id == self.user.id
        )
        refresh_result = await self.session.execute(stmt)
        self.assertIsNone(refresh_result.scalar_one_or_none())

        login_new = await self.client.post(
            "/accounts/login/", json={"email": self.user.email, "password": new_pass}
        )
        self.assertEqual(login_new.status_code, 200)

    async def test_password_reset_invalid_password_strength(self):
        await self.client.post(
            "/accounts/password-reset/request/", json={"email": self.user.email}
        )

        stmt = select(PasswordResetTokenModel).where(
            PasswordResetTokenModel.user_id == self.user.id
        )
        token_record = (await self.session.execute(stmt)).scalar_one()
        reset_token = token_record.token

        invalid_passwords = [
            "short",
            "onlylowercase1!",
            "ONLYUPPERCASE1!",
            "NoDigits!",
            "NoSpecialChar123",
            "A" * 73,
        ]

        for bad_pass in invalid_passwords:
            payload = {
                "token": reset_token,
                "email": self.user.email,
                "password": bad_pass,
            }
            response = await self.client.post(
                "/accounts/password-reset/complete/", json=payload
            )

            self.assertEqual(response.status_code, 422)


class TestUserProfiles(IsolatedAsyncioTestCase):
    async def async_mock(self, *args, **kwargs):
        return None

    async def asyncSetUp(self):
        self.session = async_session()
        await self.session.execute(
            text(
                "TRUNCATE TABLE user_groups, users, activation_tokens, refresh_tokens, user_profiles, password_reset_tokens RESTART IDENTITY CASCADE"
            )
        )
        await self.session.commit()

        user_group = UserGroupModel(name=UserGroupEnum.USER)
        self.session.add(user_group)
        await self.session.commit()
        await self.session.refresh(user_group)
        self.user_group_id = user_group.id

        self.user = UserModel.create(
            email="test@gmail.com",
            raw_password="Password123!",
            group_id=self.user_group_id,
        )
        self.user.is_active = True
        self.session.add(self.user)
        await self.session.commit()

        self.mock_email_sender = MagicMock()

        self.mock_email_sender.send_password_reset_email = MagicMock(
            side_effect=self.async_mock
        )
        self.mock_email_sender.send_password_reset_complete_email = MagicMock(
            side_effect=self.async_mock
        )
        app.dependency_overrides[get_email_sender] = lambda: self.mock_email_sender

        self.client = AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        )

    async def asyncTearDown(self):
        app.dependency_overrides.clear()
        await self.session.close()

    async def test_get_me_after_registration_and_activation(self):
        assert self.user is not None
        login_response = await self.client.post(
            "/accounts/login/",
            json={"email": self.user.email, "password": "Password123!"},
        )
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = await self.client.get("/accounts/me/", headers=headers)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["email"], self.user.email)
        self.assertEqual(data["id"], self.user.id)
        self.assertTrue(data["is_active"])
        self.assertEqual(data["group_name"], "user")
        self.assertIn("profile", data)

    async def test_update_profile_success(self):
        login_res = await self.client.post(
            "/accounts/login/",
            json={"email": self.user.email, "password": "Password123!"},
        )
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        update_payload = {"first_name": "John", "last_name": "Smith", "gender": "man"}

        response = await self.client.patch(
            "/accounts/me/profile/", json=update_payload, headers=headers
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["first_name"], "John")
        self.assertEqual(data["last_name"], "Smith")
        self.assertEqual(data["gender"], "man")
        self.assertIsNone(data["info"])

        await self.session.refresh(self.user.profile)
        assert self.user.profile is not None
        self.assertEqual(self.user.profile.first_name, "John")

    async def test_logout_success(self):
        login_res = await self.client.post(
            "/accounts/login/",
            json={"email": self.user.email, "password": "Password123!"},
        )
        login_data = login_res.json()
        access_token = login_data["access_token"]
        refresh_token = login_data["refresh_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        stmt = select(RefreshTokenModel).where(RefreshTokenModel.token == refresh_token)
        result = await self.session.execute(stmt)
        self.assertIsNotNone(result.scalar_one_or_none())

        response = await self.client.post(
            f"/accounts/logout/?refresh_token={refresh_token}", headers=headers
        )

        self.assertEqual(response.status_code, 204)

        result_after = await self.session.execute(stmt)
        self.assertIsNone(result_after.scalar_one_or_none())

    async def test_logout_other_user_token_fail(self):
        login_res = await self.client.post(
            "/accounts/login/",
            json={"email": self.user.email, "password": "Password123!"},
        )
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        fake_token = "some-other-guys-token"
        response = await self.client.post(
            f"/accounts/logout/?refresh_token={fake_token}", headers=headers
        )

        self.assertEqual(response.status_code, 404)


class TestAdminActions(IsolatedAsyncioTestCase):
    async def async_mock(self, *args, **kwargs):
        return None

    async def asyncSetUp(self):
        self.session = async_session()
        await self.session.execute(
            text(
                "TRUNCATE TABLE user_groups, users, activation_tokens, refresh_tokens, user_profiles, password_reset_tokens RESTART IDENTITY CASCADE"
            )
        )
        await self.session.commit()

        user_group = UserGroupModel(name=UserGroupEnum.USER)
        moderator_group = UserGroupModel(name=UserGroupEnum.MODERATOR)
        admin_group = UserGroupModel(name=UserGroupEnum.ADMIN)
        self.session.add_all([user_group, moderator_group, admin_group])
        await self.session.commit()
        await self.session.refresh(user_group)
        await self.session.refresh(moderator_group)
        await self.session.refresh(admin_group)
        self.user_group_id = user_group.id
        self.moderator_group_id = moderator_group.id
        self.admin_group_id = admin_group.id

        self.user = UserModel.create(
            email="user@gmail.com",
            raw_password="Password123!",
            group_id=self.user_group_id,
        )
        self.admin = UserModel.create(
            email="admin@gmail.com",
            raw_password="Password123!",
            group_id=self.admin_group_id,
        )
        self.user.is_active = True
        self.admin.is_active = True
        self.session.add_all([self.user, self.admin])
        await self.session.commit()

        self.client = AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        )

    async def asyncTearDown(self):
        await self.session.close()

    async def test_admin_change_user_group_success(self):
        login_res = await self.client.post(
            "/accounts/login/",
            json={"email": "admin@gmail.com", "password": "Password123!"},
        )
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        response = await self.client.patch(
            f"/accounts/users/{self.user.id}/group/?new_group={UserGroupEnum.MODERATOR.value}",
            headers=headers,
        )

        self.assertEqual(response.status_code, 200)

        await self.session.refresh(self.user)
        self.assertEqual(self.user.group_id, self.moderator_group_id)

    async def test_user_cannot_change_group_forbidden(self):
        login_res = await self.client.post(
            "/accounts/login/",
            json={"email": "user@gmail.com", "password": "Password123!"},
        )
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        response = await self.client.patch(
            f"/accounts/users/{self.user.id}/group/?new_group={UserGroupEnum.ADMIN.value}",
            headers=headers,
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Only for admin")

    async def test_admin_ban_user_and_clear_tokens(self):
        user_refresh = RefreshTokenModel.create(
            user_id=self.user.id, days_valid=1, token="fake_token"
        )
        self.session.add(user_refresh)
        await self.session.commit()

        login_res = await self.client.post(
            "/accounts/login/",
            json={"email": "admin@gmail.com", "password": "Password123!"},
        )
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        response = await self.client.patch(
            f"/accounts/users/{self.user.id}/status/?is_active=false", headers=headers
        )
        self.assertEqual(response.status_code, 200)

        await self.session.refresh(self.user)
        self.assertFalse(self.user.is_active)

        stmt = select(RefreshTokenModel).where(
            RefreshTokenModel.user_id == self.user.id
        )
        token_check = (await self.session.execute(stmt)).scalar_one_or_none()
        self.assertIsNone(token_check)

    async def test_admin_cannot_ban_himself(self):
        login_res = await self.client.post(
            "/accounts/login/",
            json={"email": "admin@gmail.com", "password": "Password123!"},
        )
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        response = await self.client.patch(
            f"/accounts/users/{self.admin.id}/status/?is_active=false", headers=headers
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "You cannot ban yourself, bro.")

    async def test_admin_change_group_not_found(self):
        login_res = await self.client.post(
            "/accounts/login/",
            json={"email": "admin@gmail.com", "password": "Password123!"},
        )
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        response = await self.client.patch(
            f"/accounts/users/{self.user.id}/group/?new_group=SUPER_ADMIN",
            headers=headers,
        )

        self.assertEqual(response.status_code, 422)

    async def test_admin_change_status_user_not_found(self):
        login_res = await self.client.post(
            "/accounts/login/",
            json={"email": "admin@gmail.com", "password": "Password123!"},
        )
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        invalid_user_id = 9999
        response = await self.client.patch(
            f"/accounts/users/{invalid_user_id}/status/?is_active=false",
            headers=headers,
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "User not found.")

    async def test_admin_unban_user_success(self):
        self.user.is_active = False
        self.session.add(self.user)
        await self.session.commit()

        login_res = await self.client.post(
            "/accounts/login/",
            json={"email": "admin@gmail.com", "password": "Password123!"},
        )
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        response = await self.client.patch(
            f"/accounts/users/{self.user.id}/status/?is_active=true", headers=headers
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.json()["message"], "User status update is successful."
        )

        await self.session.refresh(self.user)
        self.assertTrue(self.user.is_active)
