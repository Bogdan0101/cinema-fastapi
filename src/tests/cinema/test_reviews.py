from src.tests.cinema.base import BaseCinemaTestCase
import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class MoviesReviewsTestCase(BaseCinemaTestCase):
    async def test_review_success_lifecycle(self):
        """POST -> GET -> DELETE -> GET_ERROR_404"""
        review_data = {"rating": 10, "comment": "Masterpiece!"}

        res_201 = await self.client.post(
            f"/cinema/movies/{self.movie_one.id}/reviews/",
            json=review_data,
            headers=self.user_headers,
        )
        self.assertEqual(res_201.status_code, 201)

        res_400 = await self.client.post(
            f"/cinema/movies/{self.movie_one.id}/reviews/",
            json=review_data,
            headers=self.user_headers,
        )
        self.assertEqual(res_400.status_code, 400)
        self.assertEqual(res_400.json()["detail"], "Review already exists.")

        res_wrong_user = await self.client.delete(
            f"/cinema/movies/{self.movie_one.id}/reviews/", headers=self.admin_headers
        )
        self.assertEqual(res_wrong_user.status_code, 404)
        self.assertEqual(res_wrong_user.json()["detail"], "No review found.")

        res_list = await self.client.get(f"/cinema/movies/{self.movie_one.id}/reviews/")
        self.assertEqual(res_list.status_code, 200)
        self.assertIsNone(res_list.json()["prev_page"])
        self.assertIsNone(res_list.json()["next_page"])
        self.assertEqual(res_list.json()["total_pages"], 1)
        self.assertEqual(res_list.json()["total_items"], 1)
        self.assertEqual(res_list.json()["items"][0]["comment"], "Masterpiece!")
        self.assertEqual(res_list.json()["items"][0]["rating"], 10)

        res_204 = await self.client.delete(
            f"/cinema/movies/{self.movie_one.id}/reviews/", headers=self.user_headers
        )
        self.assertEqual(res_204.status_code, 204)

        res_after = await self.client.get(
            f"/cinema/movies/{self.movie_one.id}/reviews/"
        )
        self.assertEqual(res_after.status_code, 404)

    async def test_reviews_errors(self):
        review_data = {"rating": 10, "comment": "Masterpiece!"}

        res_404_post = await self.client.post(
            f"/cinema/movies/99999/reviews/",
            json=review_data,
            headers=self.user_headers,
        )
        self.assertEqual(res_404_post.status_code, 404)
        self.assertIn(
            res_404_post.json()["detail"], "Object with id 99999 is not found"
        )

        res_404_get = await self.client.get(
            f"/cinema/movies/99999/reviews/", headers=self.user_headers
        )
        self.assertEqual(res_404_get.status_code, 404)
        self.assertIn(res_404_get.json()["detail"], "Object with id 99999 is not found")

        res_404_delete = await self.client.delete(
            f"/cinema/movies/99999/reviews/", headers=self.user_headers
        )
        self.assertEqual(res_404_delete.status_code, 404)
        self.assertIn(
            res_404_delete.json()["detail"], "Object with id 99999 is not found"
        )

        res_422 = await self.client.post(
            f"/cinema/movies/{self.movie_one.id}/reviews/",
            json={"rating": 99, "comment": "Too high"},
            headers=self.user_headers,
        )
        self.assertEqual(res_422.status_code, 422)
