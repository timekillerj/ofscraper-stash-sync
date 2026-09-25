import logging
import base64
from pathlib import Path

import requests
import ofscraper.runner.manager as manager
import ofscraper.utils.constants as constants

from stashapi.stashapp import StashInterface

class StashAPIHandler:
    def __init__(self, api_key, scheme, host, port):
        self.api_key = api_key
        self.scheme = scheme
        self.host = host
        self.port = port
        self.stash = None

        # Unorganized media indexes.
        # Key = OF username
        # Value = list of Stash images/scenes
        self.unorganized_images_by_model = {}
        self.unorganized_scenes_by_model = {}

        self.connect()

    def connect(self):
        try:
            self.stash = StashInterface({
                "scheme": self.scheme,
                "host": self.host,
                "port": self.port,
                "ApiKey": self.api_key,
                "logger": logging
            })
            logging.info("Connected to Stash API")
        except Exception as e:
            logging.error(f"Error connecting to Stash API: {e}")
            self.stash = None

    def build_unorganized_media_index(self, stash_of_library_path):
        """
        Load unorganized OnlyFans images/scenes from Stash once and
        index them by model directory.

        stash_of_library_path must be the path as seen by Stash/Docker.

        Example:
            /data/studios/OnlyFans

        Expected media path:
            /data/studios/OnlyFans/<username>/...
        """

        self.unorganized_images_by_model = {}
        self.unorganized_scenes_by_model = {}

        logging.info("Loading all unorganized images from Stash")

        try:
            images = self.stash.find_images(
                f={
                    "path": {
                        "value": stash_of_library_path,
                        "modifier": "INCLUDES"
                    },
                    "organized": False
                },
                filter={
                    "per_page": -1
                }
            ) or []
        except Exception as e:
            logging.error(f"Error loading unorganized images: {e}")
            return False

        logging.info(f"Found {len(images)} total unorganized images")

        #if images:
        #    logging.info(f"SAMPLE IMAGE OBJECT: {images[0]}")

        logging.info("Loading all unorganized scenes from Stash")

        try:
            scenes = self.stash.find_scenes(
                f={
                    "path": {
                        "value": stash_of_library_path,
                        "modifier": "INCLUDES"
                    },
                    "organized": False
                },
                filter={
                    "per_page": -1
                }
            ) or []
        except Exception as e:
            logging.error(f"Error loading unorganized scenes: {e}")
            return False

        logging.info(f"Found {len(scenes)} total unorganized scenes")

        #if scenes:
        #    logging.info(f"SAMPLE SCENE OBJECT: {scenes[0]}")

        for image in images:
            username = self._get_model_from_media(
                image,
                stash_of_library_path
            )

            if username:
                self.unorganized_images_by_model.setdefault(
                    username.lower(), []
                ).append(image)

        for scene in scenes:
            username = self._get_model_from_media(
                scene,
                stash_of_library_path
            )

            if username:
                self.unorganized_scenes_by_model.setdefault(
                    username.lower(), []
                ).append(scene)

        model_count = len(
            set(self.unorganized_images_by_model)
            | set(self.unorganized_scenes_by_model)
        )

        logging.info(
            f"Indexed unorganized media for {model_count} models"
        )

        return True

    def _get_model_from_media(self, media, stash_of_library_path):
        """
        Extract the OF username from the first directory underneath
        the OnlyFans library path as seen by Stash.

        Example:

            Stash base:
                /data/studios/OnlyFans

            Media:
                /data/studios/OnlyFans/ana_lingus/Posts/foo.jpg

            Returns:
                ana_lingus
        """

        files = media.get("visual_files") or media.get("files") or []

        if not files:
            logging.debug(
                f"Media {media.get('id')} has no files"
            )
            return None

        file_path = files[0].get("path")

        if not file_path:
            logging.debug(
                f"Media {media.get('id')} has no file path"
            )
            return None

        try:
            relative_path = Path(file_path).relative_to(
                Path(stash_of_library_path)
            )
        except ValueError:
            logging.debug(
                f"Media path is outside Stash OF library: {file_path}"
            )
            return None

        if not relative_path.parts:
            return None

        return relative_path.parts[0]

    def get_studio_id_by_name(self,name):
        if self.stash:
            try:
                studio = self.stash.find_studio(name)
            except Exception as e:
                logging.error("Error getting OnlyFans studio id")
                return None
        else:
            logging.error("Not Connected to Stash API")
            return None
        if not studio:
            return None
        return studio.get("id")

    def get_tag_id_by_name(self, name):
        if self.stash:
            try:
                tag = self.stash.find_tag(name)
            except Exception as e:
                logging.error(f"Error getting tag: {e}")
                return None
        else:
            logging.error("Not Connected to Stash API")
            return None
        if not tag:
            return None
        return tag.get("id")

    def get_onlyfans_avatar(self, username):
        """
        Get a performer's avatar directly from OnlyFans using ofscraper's
        authenticated/signed session.

        Returns the avatar URL if available, otherwise None.
        """

        try:
            # Initialize the minimal manager needed for OFSessionManager.
            if manager.Manager is None:
                manager.Manager = manager.mainManager()

            url = constants.getattr("profileEP").format(username)

            with manager.Manager.get_ofsession(backend="httpx") as c:
                with c.requests(url) as r:

                    if r.status == 404:
                        logging.info(
                            f"OnlyFans profile @{username} does not exist"
                        )
                        return None

                    if r.status != 200:
                        logging.warning(
                            f"Unable to retrieve OnlyFans profile @{username}: "
                            f"HTTP {r.status}"
                        )
                        return None

                    data = r.json()
                    avatar_url = data.get("avatar")

                    if not avatar_url:
                        logging.info(
                            f"OnlyFans profile @{username} has no avatar"
                        )
                        return None

                    logging.info(
                        f"Found OnlyFans avatar for @{username}"
                    )

                    return avatar_url

        except Exception as e:
            logging.warning(
                f"Unable to retrieve OnlyFans avatar for @{username}: {e}"
            )
            return None

    def create_performer(self, name):
        performer_data = {
            "name": name,
            "urls": [
                f"https://onlyfans.com/{name}"
            ]
        }

        # TODO: add config option to create performer with OF avatar if available
        avatar_url = self.get_onlyfans_avatar(name)

        if avatar_url:
            performer_data["image"] = avatar_url

        try:
            performer = self.stash.create_performer(performer_data)
        except Exception as e:
            logging.error(
                f"Error creating Stash performer {name}: {e}"
            )
            return None

        if not performer:
            logging.error(f"Failed to create Stash performer {name}")
            return None

        logging.info(
            f"Created Stash performer {performer['name']} "
            f"(ID: {performer['id']})"
            + (" with OnlyFans avatar" if avatar_url else "")
        )

        return performer

    def create_of_user_studio(self,username, of_studio_id):
        parent_dir = Path(__file__).resolve().parent.parent
        image_path = parent_dir / "onlyfans.png"

        of_image = None
        if image_path.exists() and image_path.is_file():
            with image_path.open("rb") as f:
                of_image = base64.b64encode(f.read()).decode("utf-8")

        studio_data = {
            "aliases": [],
            "details": "Sub Studio for OnlyFans content creator",
            "ignore_auto_tag": False,
            "name": f"{username} (OnlyFans)",
            "parent_id": of_studio_id,
            "stash_ids": [],
            "tag_ids": [],
            "url": f"https://www.onlyfans.com/{username}"
        }
        if of_image:
            studio_data['image'] = f"data:image/png;base64,{of_image}"
        try:
            studio = self.stash.create_studio(studio_data)
        except Exception as e:
            logging.error(f"Error creating studio: {e}")
            return None
        return studio

    def get_unorganized_of_model_images(self, performer):
        images = self.unorganized_images_by_model.get(
            performer.lower(), []
        )

        logging.debug(
            f"Found {len(images)} indexed unorganized images "
            f"for {performer}"
        )

        return images


    def get_unorganized_of_model_scenes(self, performer):
        scenes = self.unorganized_scenes_by_model.get(
            performer.lower(), []
        )

        logging.debug(
            f"Found {len(scenes)} indexed unorganized scenes "
            f"for {performer}"
        )

        return scenes

    def get_all_of_model_images(self,performer):
        try:
            # Newly scanned images will not have a performer attached, so we use
            # the file path since OF puts files in a model directory
            images = self.stash.find_images(
                f={
                    "path": {"value": performer, "modifier": "INCLUDES"},
                }
            )
        except Exception as e:
            logging.error(f'Error getting images: {e}')
            return None
        return images

    def get_all_of_model_scenes(self,performer):
        try:
            # Newly scanned scenes will not have a performer attached, so we use
            # the file path since OF puts files in a model directory
            scenes = self.stash.find_scenes(
                f={
                    "path": {"value": performer, "modifier": "INCLUDES"},
                }
            )
        except Exception as e:
            logging.error(f'Error getting scenes: {e}')
            return None
        return scenes

    def get_stash_performers_by_name(self,username):
        try:
            performers = self.stash.find_performers(
                f={
                    "name": {"value": username, "modifier": "EQUALS"},
                }
            )
                
            alias_performers = self.stash.find_performers(
                f={
                    "aliases": {"value": username, "modifier": "EQUALS"},
                }
            )
        except Exception as e:
            logging.error(f'Error getting performers: {e}')
            return None

        all_performers = performers + alias_performers
        matched_performers = []
        performer_matched = False
        for performer in all_performers:
            if performer['name'].lower() == username.lower():
                performer_matched = True

            for alias in performer['alias_list']:
                if alias.lower() == username.lower():
                    performer_matched = True
            if performer_matched:
                matched_performers.append(performer)
        if not matched_performers:
            logging.debug(f'Performer not found: {username}')
        logging.debug(matched_performers)
        return matched_performers

    def update_scene(self, input_data):
        if self.stash:
            try:
                self.stash.update_scene(input_data)
                logging.debug(f"Updated scene with id: {input_data['id']}")
            except Exception as e:
                logging.error(f"Error updating scene: {e}")
        else:
            logging.error("Not connected to Stash API")

    def update_image(self, input_data):
        if self.stash:
            try:
                self.stash.update_image(input_data)
                logging.debug(f"Updated image with id: {input_data['id']}")
            except Exception as e:
                logging.error(f"Error updating image: {e}")
        else:
            logging.error("Not connected to Stash API")

    def metadata_scan(self, path):
        f = {
            "scanGenerateClipPreviews": True,
            "scanGenerateCovers": True,
            "scanGenerateImagePreviews": True,
            "scanGeneratePhashes": True,
            "scanGeneratePreviews": True,
            "scanGenerateSprites": True,
            "scanGenerateThumbnails": True
        }
        try:
            job_id = self.stash.metadata_scan([path], f)
        except Exception as e:
            logging.error(f"Error scanning library: {e}")
        return job_id

    def get_job_by_id(self,job_id):
        job = None
        if self.stash:
            try:
                job = self.stash.find_job(job_id)
            except Exception as e:
                logging.error(f'Error finding job with id {job_id}: {e}')
        else:
            logging.error("Not connected to Stash API")
        return job
