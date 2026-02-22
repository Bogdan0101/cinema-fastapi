from src.tests.cinema.base import BaseCinemaTestCase
import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class MoviesTestCase(BaseCinemaTestCase):
    async def test_pagination_logic(self):
        response = await self.client.get("/cinema/movies/")
        data = response.json()
        self.assertEqual(len(data["items"]), 2)
        self.assertIsNone(data["prev_page"])
        self.assertIsNone(data["next_page"])
        self.assertEqual(data["total_pages"], 1)
        self.assertEqual(data["total_items"], 2)
        response = await self.client.get("/cinema/movies/?page=1&per_page=1")
        data = response.json()
        self.assertEqual(len(data["items"]), 1)
        self.assertIsNone(data["prev_page"])
        self.assertIsNotNone(data["next_page"])
        self.assertEqual(data["total_pages"], 2)
        self.assertEqual(data["total_items"], 2)
        response = await self.client.get("/cinema/movies/?page=2&per_page=1")
        data = response.json()
        self.assertEqual(len(data["items"]), 1)
        self.assertIsNotNone(data["prev_page"])
        self.assertIsNone(data["next_page"])
        self.assertEqual(data["total_pages"], 2)
        self.assertEqual(data["total_items"], 2)

    async def test_sorting_logic(self):
        res_price = await self.client.get("/cinema/movies/?sort_by=price_asc")
        self.assertEqual(res_price.json()["items"][0]["name"], "Creed III")

        res_rating = await self.client.get("/cinema/movies/?sort_by=rating_top")
        self.assertEqual(res_rating.json()["items"][0]["name"], "Creed III")

        res_year = await self.client.get("/cinema/movies/?sort_by=year_new")
        self.assertEqual(res_year.json()["items"][0]["name"], "Creed III")

        res_id = await self.client.get("/cinema/movies/?sort_by=id_asc")
        self.assertEqual(res_id.json()["items"][0]["name"], "Inception")

    async def test_filter_logic(self):
        response = await self.client.get("/cinema/movies/?year=2010")
        data = response.json()
        self.assertEqual(data["total_items"], 1)
        self.assertEqual(data["items"][0]["name"], "Inception")

        response = await self.client.get("/cinema/movies/?min_rating=9.0")
        data = response.json()
        self.assertEqual(data["total_items"], 1)
        self.assertEqual(data["items"][0]["name"], "Creed III")

        response = await self.client.get("/cinema/movies/?min_rating=9.1&year=2018")
        data = response.json()
        self.assertEqual(data["total_items"], 1)
        self.assertEqual(data["items"][0]["name"], "Creed III")

        response = await self.client.get("/cinema/movies/?min_rating=9.9&year=2010")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "No movies found")

    async def test_search_logic(self):
        response = await self.client.get("/cinema/movies/?search=III")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["name"], "Creed III")

        response = await self.client.get("/cinema/movies/?search=DiCaprio")
        data = response.json()
        self.assertEqual(data["total_items"], 1)
        self.assertEqual(data["items"][0]["name"], "Inception")

        response = await self.client.get("/cinema/movies/?search=TEST")
        data = response.json()
        self.assertEqual(data["total_items"], 2)

        response = await self.client.get("/cinema/movies/?search=Bob")
        data = response.json()
        self.assertEqual(data["total_items"], 1)
        self.assertEqual(data["items"][0]["name"], "Creed III")

    async def test_get_movie_by_id_logic(self):
        movie_id = self.movie_one.id
        response = await self.client.get(f"/cinema/movies/{movie_id}/")

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["name"], "Inception")
        self.assertEqual(data["imdb"], 8.8)

        self.assertEqual(data["genres"][0]["name"], "Sci-Fi")
        self.assertEqual(data["certification"]["name"], "PG-13")
        self.assertEqual(data["stars"][0]["name"], "Leonardo DiCaprio")
        self.assertEqual(data["directors"][0]["name"], "Christopher Nolan")

        response_404 = await self.client.get("/cinema/movies/99999/")
        self.assertEqual(response_404.status_code, 404)
        self.assertEqual(
            response_404.json()["detail"], "Object with id 99999 is not found"
        )

    async def test_create_movie_logic(self):
        movie_payload = {
            "name": "Interstellar",
            "year": 2014,
            "time": 169,
            "imdb": 8.6,
            "price": 600.0,
            "description": "A team of explorers travel through a wormhole in space...",
            "certification": "PG-13",
            "genres": ["Sci-Fi", "Drama"],
            "stars": ["Matthew McConaughey"],
            "directors": ["Christopher Nolan"],
        }

        response_403 = await self.client.post(
            "/cinema/movies/", json=movie_payload, headers=self.user_headers
        )
        self.assertEqual(response_403.status_code, 403)

        response = await self.client.post(
            "/cinema/movies/", json=movie_payload, headers=self.admin_headers
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["name"], "Interstellar")
        self.assertEqual(len(data["genres"]), 2)

        response = await self.client.post(
            "/cinema/movies/", json=movie_payload, headers=self.admin_headers
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn(
            f"Movie with name: '{movie_payload["name"]}'"
            f" year: '{movie_payload["year"]}'"
            f" time: '{movie_payload["time"]}' already exists.",
            response.json()["detail"],
        )

    async def test_update_movie_logic(self):
        res_403 = await self.client.patch(
            f"/cinema/movies/{self.movie_one.id}/",
            json={"price": 999.99},
            headers=self.user_headers,
        )
        self.assertEqual(res_403.status_code, 403)

        res_200 = await self.client.patch(
            f"/cinema/movies/{self.movie_one.id}/",
            json={"price": 999.99},
            headers=self.admin_headers,
        )
        self.assertEqual(res_200.status_code, 200)
        data = res_200.json()

        self.assertEqual(data["price"], "999.99")
        self.assertEqual(data["name"], "Inception")

        self.assertIsNotNone(data["genres"])
        self.assertEqual(data["genres"][0]["name"], "Sci-Fi")

        res_404 = await self.client.patch(
            "/cinema/movies/99999/", json={"price": 999.99}, headers=self.admin_headers
        )
        self.assertEqual(res_404.status_code, 404)

    async def test_delete_movie_logic(self):
        res_403 = await self.client.delete(
            f"/cinema/movies/{self.movie_one.id}/", headers=self.user_headers
        )
        self.assertEqual(res_403.status_code, 403)

        res_delete = await self.client.delete(
            f"/cinema/movies/{self.movie_one.id}/", headers=self.admin_headers
        )
        self.assertEqual(res_delete.status_code, 204)

        res_delete_no_exist_id = await self.client.delete(
            f"/cinema/movies/{self.movie_one.id}/", headers=self.admin_headers
        )
        self.assertEqual(res_delete_no_exist_id.status_code, 404)

        res_get = await self.client.get(f"/cinema/movies/{self.movie_one.id}/")
        self.assertEqual(res_get.status_code, 404)

    async def test_favorites_full_cycle(self):
        res_add = await self.client.post(
            f"/cinema/movies/{self.movie_one.id}/favorite/", headers=self.user_headers
        )
        self.assertEqual(res_add.status_code, 200)
        self.assertTrue(res_add.json()["is_favorite"])
        self.assertIn(res_add.json()["message"], ["Added to favorites."])

        res_list = await self.client.get(
            "/cinema/favorites/", headers=self.user_headers
        )
        self.assertEqual(res_list.status_code, 200)
        self.assertIsNone(res_list.json()["prev_page"])
        self.assertIsNone(res_list.json()["next_page"])
        self.assertEqual(res_list.json()["total_items"], 1)
        self.assertEqual(res_list.json()["total_pages"], 1)
        self.assertEqual(res_list.json()["items"][0]["name"], "Inception")

        res_removed = await self.client.post(
            f"/cinema/movies/{self.movie_one.id}/favorite/", headers=self.user_headers
        )
        self.assertEqual(res_removed.status_code, 200)
        self.assertFalse(res_removed.json()["is_favorite"])
        self.assertIn(res_removed.json()["message"], ["Removed from favorites."])

        res_toggle_not_exist_id = await self.client.post(
            f"/cinema/movies/99999/favorite/", headers=self.user_headers
        )
        self.assertEqual(res_toggle_not_exist_id.status_code, 404)
        self.assertIn(res_toggle_not_exist_id.json()["detail"], "Movie not found.")

        res_empty = await self.client.get(
            "/cinema/favorites/", headers=self.user_headers
        )
        self.assertEqual(res_empty.status_code, 404)
        self.assertEqual(res_empty.json()["detail"], "Not found.")
