from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch, MagicMock
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text

from src.main import app
from src.security.token import get_jwt_manager
from src.database.postgresql import async_session
from src.database.models.accounts import UserModel, UserGroupModel, UserGroupEnum
from src.database.models.movies import MovieModel, CertificationModel
from src.database.models.payments import OrderModel, OrderStatus, OrderItemModel
import sys
import asyncio
from src.config.settings import settings

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class TestPaymentService(IsolatedAsyncioTestCase):

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
                "TRUNCATE TABLE user_groups, certifications, users, movies, order_items, payments RESTART IDENTITY CASCADE"
            )
        )
        await self.session.commit()

        self.patcher = patch("src.routes.payments.stripe.checkout.Session.create")
        self.mock_create_session = self.patcher.start()

        mock_response = MagicMock()
        mock_response.id = "sess_723"
        mock_response.url = "https://stripe.test/pay_link"
        self.mock_create_session.return_value = mock_response

        group = UserGroupModel(name=UserGroupEnum.USER)
        cert = CertificationModel(name="PG-13")
        self.session.add_all([group, cert])
        await self.session.commit()
        await self.session.refresh(cert)
        await self.session.refresh(group)

        self.user = UserModel(
            email="testuser@gmail.com", group_id=group.id, is_active=True
        )
        self.user.password = "SafePassword123!"

        self.movie = MovieModel(
            name="Inception",
            year=2010,
            time=148,
            imdb=8.8,
            votes=5000,
            description="Testing payments",
            price=Decimal("500.00"),
            certification_id=cert.id,
        )
        self.session.add_all([self.user, self.movie])
        await self.session.commit()

        await self.session.refresh(self.user)
        await self.session.refresh(self.movie)

        jwt_manager = get_jwt_manager()
        access_token = jwt_manager.create_access_token(data={"user_id": self.user.id})

        self.headers = {"Authorization": f"Bearer {access_token}"}
        self.client = AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        )

    async def asyncTearDown(self):
        self.patcher.stop()
        await self.session.close()

    async def test_stripe_foreign_order(self):
        another_user = UserModel(
            email="another@gmail.com",
            group_id=self.user.group_id,
            is_active=True,
        )
        another_user.password = "Password1234!"
        self.session.add(another_user)
        await self.session.commit()
        await self.session.refresh(another_user)

        order = OrderModel(
            user_id=another_user.id,
            total_amount=Decimal("500.00"),
            status=OrderStatus.PENDING,
        )
        self.session.add(order)
        await self.session.commit()
        response = await self.client.post(
            f"/payments/orders/{order.id}/pay/", headers=self.headers
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Order not found")

    async def test_step_1_create_order(self):
        response = await self.client.post(
            f"/payments/orders/checkout/{self.movie.id}/", headers=self.headers
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["user_id"], self.user.id)
        self.assertEqual(data["status"], "pending")

    async def test_step_2_get_payment_url(self):
        order = OrderModel(
            user_id=self.user.id,
            total_amount=Decimal("500.00"),
            status=OrderStatus.PENDING,
        )
        self.session.add(order)
        await self.session.commit()

        response = await self.client.post(
            f"/payments/orders/{order.id}/pay/", headers=self.headers
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["checkout_url"], "https://stripe.test/pay_link"
        )

    async def test_stripe_api_error(self):
        order = OrderModel(
            user_id=self.user.id,
            total_amount=Decimal("500.00"),
            status=OrderStatus.PENDING,
        )
        self.session.add(order)
        await self.session.commit()

        self.mock_create_session.side_effect = Exception("Connection error")

        response = await self.client.post(
            f"/payments/orders/{order.id}/pay/", headers=self.headers
        )
        self.assertEqual(response.status_code, 500)

    async def test_already_owned_movie(self):
        order = OrderModel(
            user_id=self.user.id,
            total_amount=Decimal("500.00"),
            status=OrderStatus.PAID,
        )
        self.session.add(order)
        await self.session.commit()

        from src.database.models.payments import OrderItemModel

        item = OrderItemModel(
            order_id=order.id, movie_id=self.movie.id, price_at_order=Decimal("500.00")
        )
        self.session.add(item)
        await self.session.commit()

        response = await self.client.post(
            f"/payments/orders/checkout/{self.movie.id}/", headers=self.headers
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "You have a movie.")

    async def test_stripe_webhook_success(self):
        order = OrderModel(
            user_id=self.user.id,
            total_amount=Decimal("500.00"),
            status=OrderStatus.PENDING,
        )
        self.session.add(order)
        await self.session.commit()

        webhook_payload = {
            "type": "checkout.session.completed",
            "data": {
                "object": {"id": "cs_test_123", "metadata": {"order_id": str(order.id)}}
            },
        }

        with patch(
            "src.routes.payments.stripe.Webhook.construct_event",
            return_value=webhook_payload,
        ):
            response = await self.client.post(
                "/payments/webhook/",
                json=webhook_payload,
                headers={"stripe-signature": "fake_sig"},
            )

        self.assertEqual(response.status_code, 200)

        await self.session.refresh(order)
        self.assertEqual(order.status, OrderStatus.PAID)

    async def test_get_my_library(self):
        order = OrderModel(
            user_id=self.user.id, total_amount=self.movie.price, status=OrderStatus.PAID
        )
        self.session.add(order)
        await self.session.commit()
        await self.session.refresh(order)

        item = OrderItemModel(
            order_id=order.id,
            movie_id=self.movie.id,
            price_at_order=self.movie.price,
        )
        self.session.add(item)
        await self.session.commit()

        response = await self.client.get("/payments/me/library/", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("items", data)
        self.assertEqual(data["total_items"], 1)
        self.assertEqual(len(data["items"]), 1)

        movie = data["items"][0]
        self.assertEqual(movie["name"], self.movie.name)
        self.assertEqual(movie["id"], self.movie.id)

    async def test_library_empty_for_new_user(self):
        response = await self.client.get("/payments/me/library/", headers=self.headers)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json()["detail"], "Library is empty or no movies found"
        )

    async def test_library_excludes_pending_orders(self):
        order = OrderModel(
            user_id=self.user.id,
            total_amount=self.movie.price,
            status=OrderStatus.PENDING,
        )
        self.session.add(order)
        await self.session.commit()

        item = OrderItemModel(
            order_id=order.id,
            movie_id=self.movie.id,
            price_at_order=self.movie.price,
        )
        self.session.add(item)
        await self.session.commit()

        response = await self.client.get("/payments/me/library/", headers=self.headers)

        self.assertEqual(response.status_code, 404)

    async def test_payment_success_endpoint(self):
        response = await self.client.get("/payments/success/?session_id=sess_123")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["session_id"], "sess_123")

    async def test_payment_cancel_endpoint(self):
        response = await self.client.get("/payments/cancel/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "Payment is not successful.")
