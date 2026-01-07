import logging
import re
from datetime import datetime

class MediaHandler:
    def __init__(self):
        pass

    def remove_html_tags(self, text):
        text = text.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
        clean = re.compile(r'<[^>]+>')
        return clean.sub('', text)

    def truncate_text(self, text, max_length=255):
        if len(text) <= max_length:
            return text

        truncated_text = text[:max_length]
        last_space_index = truncated_text.rfind(' ')
        if last_space_index != -1:
            return truncated_text[:last_space_index]
        else:
            return truncated_text

    def parse_text_for_performers(self, text):
        mentions = re.findall(r'@\w+[.]?\w+', text)
        all_tagged_performers = []
        for mention in mentions:
            performer = mention.lower()
            if performer not in all_tagged_performers:
                all_tagged_performers.append(performer)
        return all_tagged_performers

    def get_performer_ids_from_text(self, text):
        # parse text for '@' mentions
        tagged_performers = self.parse_text_for_performers(text)
        logging.debug(f'Found {len(tagged_performers)} performers mentioned')

        all_performer_ids = []
        # Loop performers
        for tagged_performer in tagged_performers:
            # strip '@' from name
            tagged_performer = tagged_performer.lstrip('@')

            # Look for performer with exact match name or alias
            performers = db_handler.get_stash_performers_by_name(tagged_performer)
            if not performers:
                continue

            logging.debug(f'Found {len(performers)} matching performers')

            performer_ids = [p['id'] for p in performers]

            for performer_id in performer_ids:
                if performer_id not in all_performer_ids:
                    all_performer_ids.append(performer_id)
        return all_performer_ids


    def update_media(self, db_handler, profile, media_item, performer_ids, of_studio_id):
        user_id = profile[0]
        username = profile[1]

        filename = media_item[0]
        stash_media_id = media_item[1]

        # Get metadata from sqlite db
        media_row = db_handler.execute('''
            SELECT media_id, post_id, link, filename, api_type, media_type, posted_at FROM medias WHERE model_id = ? AND filename = ?
        ''', (user_id, filename)).fetchone()
        if not media_row:
            logging.debug(f'No media found for {filename}')
            return
        
        logging.debug(media_row)
        media_id = media_row[0]
        post_id = media_row[1]
        link = media_row[2]
        filename = media_row[3]
        api_type = media_row[4]
        media_type = media_row[5]
        posted_at = media_row[6]
        posted_at_dt = dt = datetime.fromisoformat(posted_at)
        posted_at_formatted = posted_at_dt.strftime("%Y-%m-%d")

        # Media text could be in several tables, so we go looking for it
        post_tables = ['posts','stories','messages','stories']
        for table in post_tables:
            metadata_row = db_handler.execute(f'''
                SELECT text FROM {table} where post_id = ?
            ''', (post_id, )).fetchone()
            if metadata_row:
                text = metadata_row[0]
                break
        if not text:
            # No text found, generate something useful
            text = f'{api_type}: {posted_at_formatted}'
        else:
            tagged_performer_ids = self.get_performer_ids_from_text(text)
        performer_ids = performer_ids + tagged_performer_ids
        text = self.remove_html_tags(text)
        description = ''

        # truncate long text and add it to the description
        if len(text) > 255:
            details = text
            title = self.truncate_text(text)
        else:
            details = ''
            title = text
        logging.debug(f'Title: {title}')
        logging.debug(f'Details: {details}')

        import pdb
        pdb.set_trace()
        input = {
            "id": stash_media_id,
            "title": text,
            "code": media_id,
            "date": posted_at_formatted,
            "studio_id": of_studio_id,
            "performer_ids": performer_ids,
            "details": description,
            "organized": True
        }
        if link:
            input["urls"] = [link]

        logging.debug(input)
        # Find media in stash
        logging.debug(f"FILE: {filename}")
        if media_type == 'Videos':
            stash.update_scene(input)
            logging.info(f"Updated: Scene {media_id}: {text}")
        elif media_type == 'Images':
            stash.update_image(input)
            logging.info(f"Updated: Image {media_id}: {text}")
        return
