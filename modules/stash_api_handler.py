import logging
import base64
from pathlib import Path

from stashapi.stashapp import StashInterface


class StashAPIHandler:
    def __init__(self, api_key, scheme, host, port):
        self.api_key = api_key
        self.scheme = scheme
        self.host = host
        self.port = port
        self.stash = None
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

    def get_unorganized_of_model_images(self,performer):
        try:
            # Newly scanned images will not have a performer attached, so we use
            # the file path since OF puts files in a model directory
            images = self.stash.find_images(
                f={
                    "path": {"value": performer, "modifier": "INCLUDES"},
                    "organized": False
                }
            )
        except Exception as e:
            logging.error(f'Error getting images: {e}')
            return None
        return images

    def get_unorganized_of_model_scenes(self,performer):
        try:
            # Newly scanned scenes will not have a performer attached, so we use
            # the file path since OF puts files in a model directory
            scenes = self.stash.find_scenes(
                f={
                    "path": {"value": performer, "modifier": "INCLUDES"},
                    "organized": False
                }
            )
        except Exception as e:
            logging.error(f'Error getting scenes: {e}')
            return None
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
                    "aliases": {"value": username, "modifier": "INCLUDES"},
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
                logging.info(f"Updated scene with id: {input_data['id']}")
            except Exception as e:
                logging.error(f"Error updating scene: {e}")
        else:
            logging.error("Not connected to Stash API")

    def update_image(self, input_data):
        if self.stash:
            try:
                self.stash.update_image(input_data)
                logging.info(f"Updated image with id: {input_data['id']}")
            except Exception as e:
                logging.error(f"Error updating image: {e}")
        else:
            logging.error("Not connected to Stash API")

    def metadata_scan(self):
        """
        {operationName: "MetadataScan",…}
        operationName: "MetadataScan"
        query: "mutation MetadataScan($input: ScanMetadataInput!) {\n  metadataScan(input: $input)\n}"
        variables: {input: {scanGenerateCovers: true, scanGeneratePreviews: true, scanGenerateImagePreviews: true,…}}
        paths: ["/data/OnlyFans"]
        scanGenerateClipPreviews: true
        scanGenerateCovers: true
        scanGenerateImagePreviews: true
        scanGeneratePhashes: true
        scanGeneratePreviews: true
        scanGenerateSprites: true
        scanGenerateThumbnails: true 
        """