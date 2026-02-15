from src.tests.cinema.base import BaseCinemaTestCase
import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class EntitiesTestCase(BaseCinemaTestCase):
    async def test_entities_universal_lifecycle(self):
        entities = [
            {
                "path": "genres",
                "payload": {"name": "Horror"},
                "update": {"name": "Thriller"},
            },
            {
                "name": "stars",
                "path": "stars",
                "payload": {"name": "Tom Hardy"},
                "update": {"name": "T. Hardy"},
            },
            {
                "name": "directors",
                "path": "directors",
                "payload": {"name": "Ridley Scott"},
                "update": {"name": "R. Scott"},
            },
            {
                "name": "certifications",
                "path": "certifications",
                "payload": {"name": "PG"},
                "update": {"name": "G"},
            },
        ]

        for entity in entities:
            url = f"/cinema/{entity['path']}/"
            bad_url = f"{url}99999/"

            # GET LIST
            res_200_list = await self.client.get(url)
            self.assertEqual(res_200_list.status_code, 200)
            data_list = res_200_list.json()
            self.assertIn("items", data_list)
            self.assertIsNone(data_list["prev_page"])
            self.assertIsNone(data_list["next_page"])
            self.assertEqual(data_list["total_pages"], 1)
            self.assertEqual(data_list["total_items"], 2)
            self.assertTrue(any("movies_count" in item for item in data_list["items"]))

            # POST
            res_403_post = await self.client.post(
                url, json=entity["payload"], headers=self.user_headers
            )
            self.assertEqual(res_403_post.status_code, 403)

            res_422_post = await self.client.post(
                url, json={}, headers=self.admin_headers
            )
            self.assertEqual(res_422_post.status_code, 422)

            res_201_post = await self.client.post(
                url, json=entity["payload"], headers=self.admin_headers
            )
            self.assertEqual(res_201_post.status_code, 201)
            obj_id = res_201_post.json()["id"]
            current_obj_url = f"{url}{obj_id}/"

            res_409_post = await self.client.post(
                url, json=entity["payload"], headers=self.admin_headers
            )
            self.assertEqual(res_409_post.status_code, 409)
            self.assertIn(
                f"Object with name {entity["payload"]["name"]} already exists.",
                res_409_post.json()["detail"],
            )

            # GET DETAIL
            res_404_get = await self.client.get(bad_url)
            self.assertEqual(res_404_get.status_code, 404)

            res_200_get = await self.client.get(current_obj_url)
            self.assertEqual(res_200_get.status_code, 200)
            self.assertEqual(res_200_get.json()["name"], entity["payload"]["name"])
            self.assertIn("movies", res_200_get.json())

            # PATCH
            res_403_patch = await self.client.patch(
                current_obj_url, json=entity["update"], headers=self.user_headers
            )
            self.assertEqual(res_403_patch.status_code, 403)

            res_422_patch = await self.client.patch(
                current_obj_url, json={"name": ""}, headers=self.admin_headers
            )
            self.assertEqual(res_422_patch.status_code, 422)

            res_200_patch = await self.client.patch(
                current_obj_url, json=entity["update"], headers=self.admin_headers
            )
            self.assertEqual(res_200_patch.status_code, 200)
            self.assertEqual(res_200_patch.json()["name"], entity["update"]["name"])

            # DELETE
            res_403_delete = await self.client.delete(
                current_obj_url, headers=self.user_headers
            )
            self.assertEqual(res_403_delete.status_code, 403)

            res_404_delete = await self.client.delete(
                bad_url, headers=self.admin_headers
            )
            self.assertEqual(res_404_delete.status_code, 404)

            res_204_delete = await self.client.delete(
                current_obj_url, headers=self.admin_headers
            )
            self.assertEqual(res_204_delete.status_code, 204)

            # Finally
            res_404_get = await self.client.get(current_obj_url)
            self.assertEqual(res_404_get.status_code, 404)
