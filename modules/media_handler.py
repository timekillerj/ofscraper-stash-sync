import logging
import re
from datetime import datetime

import html
import emojis

class MediaHandler:
    def __init__(self, max_title_length):
        self.max_title_length = max_title_length

    def remove_html_tags(self, text):
        # Clean up HTML for Stash display

        # Change <br> to newlines
        text = text.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")

        # Get rid of any other tags
        clean = re.compile(r'<[^>]+>')
        text = clean.sub('', text)

        # Also fix html encoding
        text = html.unescape(text)

        return text

    def truncate_title(self, title, max_length):

        # Check if the title is already under max length
        if len(title) <= max_length:
            return title
        last_punctuation_index = -1
        punctuation_chars = {'.', '!', '?', '❤', '☺'}
        punctuation_chars.update(emojis.get(title))
        for c in punctuation_chars:
            last_punctuation_index = max(title.rfind(c, 0, max_length), last_punctuation_index)
        if last_punctuation_index != -1:
            return title[:last_punctuation_index+1]
        # Find the last space character before max length
        last_space_index = title.rfind(" ",0, max_length)
        # truncate at last_space_index if valid, else max_length
        title_end = last_space_index if last_space_index != -1 else max_length
        return title[:title_end]

    def parse_text_for_performers(self, text):
        # Look for '@' mentions in text and return a list
        mentions = re.findall(r"(?:^|\s)@([\w\-\.]+)", text)
        all_tagged_performers = []
        for mention in mentions:
            performer = mention.lower()
            if performer not in all_tagged_performers:
                all_tagged_performers.append(performer)
        return all_tagged_performers

    def get_performer_ids_from_text(self, stash_handler, text):
        # parse text for '@' mentions and try to find corresponding Stash performers
        tagged_performers = self.parse_text_for_performers(text)
        logging.debug(f'Found {len(tagged_performers)} performers mentioned')

        all_performer_ids = []
        # Loop performers
        for tagged_performer in tagged_performers:
            # strip '@' from name
            tagged_performer = tagged_performer.lstrip('@')

            # Look for performer with exact match name or alias
            performers = stash_handler.get_stash_performers_by_name(tagged_performer)
            if not performers:
                continue

            logging.debug(f'Found {len(performers)} matching performers')

            performer_ids = [p['id'] for p in performers]

            for performer_id in performer_ids:
                if performer_id not in all_performer_ids:
                    all_performer_ids.append(performer_id)
        return all_performer_ids

    def process_text(self, text):
        # If there is a line break (<br>), split to title/details
        parts = re.split(r'<br\s*/?>', text, maxsplit=1, flags=re.IGNORECASE)
        title = parts[0]
        details = text
        title = self.remove_html_tags(title)
        details = self.remove_html_tags(details)

        # Truncate very long titles
        if len(title) > self.max_title_length:
            title = self.truncate_title(title, self.max_title_length)

        # If title and details match, drop the redundant details
        if title == details:
            details = ''
        return title,details


    def update_media(self, db_handler, stash_handler, profile, media_item, performer_ids, user_studio_id):
        # Split profile tuple to id and name
        user_id = profile[0]
        username = profile[1]

        # Split media_item tuple to file and id
        filename = media_item[0]
        stash_media_id = media_item[1]

        # Use the username and filename to look in the OF database for metadata
        logging.debug(f'Looking for media for {username} with filename {filename}')
        media_row = db_handler.execute('''
            SELECT media_id, post_id, link, filename, api_type, media_type, posted_at FROM medias WHERE model_id = ? AND filename = ?
        ''', (user_id, filename)).fetchone()
        if not media_row:
            logging.debug(f'No media found for {filename}')
            return
        
        logging.debug(f'Found Media: {media_row}')
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
        post_tables = ['posts','stories','messages']
        text = ''
        price = ''
        paid = ''
        archived = ''
        for table in post_tables:
            metadata_row = db_handler.execute(f'''
                SELECT text, price, paid, archived FROM {table} where post_id = ?
            ''', (post_id, )).fetchone()
            if metadata_row:
                text = metadata_row[0]
                price = metadata_row[1]
                paid = metadata_row[2]
                archived = metadata_row[3]
                break
        if not text:
            # No text found, generate something useful
            text = f'{api_type}: {posted_at_formatted}'
            tagged_performer_ids = []
        else:
            tagged_performer_ids = self.get_performer_ids_from_text(stash_handler, text)
        performer_ids = performer_ids + tagged_performer_ids

        title,details = self.process_text(text)
        logging.debug(f'Title: {title}')
        logging.debug(f'Details: {details}')
        
        tags = []
        if paid == 1 and price > 0:
            paid_tag_id = stash_handler.get_tag_id_by_name('paid')
            if paid_tag_id:
                tags.append(paid_tag_id)
        if archived == 1:
            archived_tag_id = stash_handler.get_tag_id_by_name('archived')
            if archived_tag_id:
                tags.append(archived)

        input = {
            "id": stash_media_id,
            "title": title,
            "code": media_id,
            "date": posted_at_formatted,
            "studio_id": user_studio_id,
            "performer_ids": performer_ids,
            "details": details,
            "tag_ids": tags,
            "organized": True
        }
        if link:
            input["urls"] = [link]

        logging.debug(input)
        # Find media in stash
        logging.debug(f"FILE: {filename}")
        if media_type == 'Videos':
            stash_handler.update_scene(input)
            logging.info(f"Updated: Scene {stash_media_id}: {title}")
        elif media_type == 'Images':
            stash_handler.update_image(input)
            logging.info(f"Updated: Image {stash_media_id}: {title}")
        return
