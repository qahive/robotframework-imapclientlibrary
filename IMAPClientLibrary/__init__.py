import base64
import email
import quopri
import re
from datetime import datetime
from datetime import timedelta
from time import sleep
from imapclient import IMAPClient
from robot.api import logger
from robot.api.deco import keyword
from robot.utils import DotDict

__version__ = '0.1.1'


class IMAPClientLibrary:
    """
    ImapClientLibrary is an email testing library.

    """

    IMAP_HOST = ''
    IMAP_EMAIL = ''
    IMAP_PASSWORD = ''

    PORT = 143
    PORT_SECURE = 993
    FOLDER = 'INBOX'

    ROBOT_LIBRARY_SCOPE = 'GLOBAL'
    ROBOT_LIBRARY_VERSION = __version__
    ROBOT_LISTENER_API_VERSION = 3

    def __init__(self):
        self._email_index = None
        self._imap = None
        self._mails = []
        self._mp_iter = None
        self._mp_msg = None
        self._part = None

    @keyword
    def init_email_client(self, host, email, password):
        self.IMAP_HOST = host
        self.IMAP_EMAIL = email
        self.IMAP_PASSWORD = password

    @keyword
    def wait_for_email(self, **kwargs):
        """
        Wait for email message to arrived base on any given filter criteria.
        Returns email index of the latest email message received.

        Arguments:
        - ``poll_frequency``: The delay value in seconds to retry the mailbox check. (Default 10)
        - ``timeout``: The maximum value in seconds to wait for email message to arrived.
                       (Default 180)
        - ``recipient``: Email recipient. (Default None)
        - ``sender``: Email sender. (Default None)
        - ``subject``: Email subject. Support regexp (Default None)
        - ``body``: Email body text. Support regexp (Default None)

        Return:
        - ``email``: Email dictionary {messageId: '', recipient: '', sender: '', subject: '', body: ''}

        Examples:
        | Wait For Email | sender=noreply@domain.com |
        | Wait For Email | sender=noreply@domain.com |
        """
        # Poll frequency and timeout
        poll_frequency = 10
        end_time = datetime.now() + timedelta(seconds=int(kwargs.pop('timeout', 180)))

        expect_sender = kwargs.pop('sender', None)
        expect_recipient = kwargs.pop('recipient', None)
        expect_subject = kwargs.pop('subject', None)
        expect_body = kwargs.pop('body', None)
        found_email = None

        while datetime.now() < end_time:
            with IMAPClient(host=self.IMAP_HOST) as client:
                logger.info('Open mail box...')
                client.login(self.IMAP_EMAIL, self.IMAP_PASSWORD)
                client.select_folder('INBOX')
                logger.info('Open mail box success')

                d1 = datetime.now() - timedelta(hours=24)
                messages = client.search([u'UNSEEN', u'SINCE', d1])
                logger.info('%d messages from mail server.' % len(messages))
                logger.info(d1)
                index = 0

                for msgid, data in sorted(client.fetch(messages, ['ENVELOPE', 'BODY[TEXT]', 'RFC822']).items(), reverse=True):
                    envelope = data[b'ENVELOPE']
                    mail_from = str(envelope.from_[0])
                    mail_to = str(envelope.to[0])
                    mail_subject = str(envelope.subject.decode())
                    mail_subject = self._encoded_words_to_text(mail_subject)
                    logger.info('Subject ' + mail_subject)
                    logger.info(envelope)
                    mail_body = data[b'BODY[TEXT]']

                    if expect_sender is not None and (
                        expect_sender.lower() != mail_from.lower() and '<' + expect_sender.lower() + '>' not in mail_from.lower()):
                        continue

                    if expect_recipient is not None and (
                        expect_recipient.lower() != mail_to.lower() and '<' + expect_recipient.lower() + '>' not in mail_to.lower()):
                        continue

                    if expect_subject is not None and (not re.match(expect_subject, mail_subject)):
                        continue

                    if expect_body is not None and not re.search(expect_body, mail_body):
                        continue

                    raw = email.message_from_bytes(data[b'RFC822'])  # Return a message object structure from a bytes-like object[6]
                    mail_attachments = self._get_attachments(raw)  # Runs above function
                    
                    found_email = DotDict({
                        'messageId': msgid,
                        'recipient': mail_to,
                        'sender': mail_from,
                        'subject': mail_subject,
                        'body': mail_body,
                        'attachments': mail_attachments
                    })

                    if found_email is not None:
                        break
                index += 1

                if found_email is not None:
                    return found_email

                if datetime.now() < end_time:
                    sleep(poll_frequency)

            raise Exception('Can\'t find the specific email.')

    @keyword
    def delete_email(self, email_obj):
        with IMAPClient(host=self.IMAP_HOST) as client:
            logger.info('Open test mail box...')
            client.login(self.IMAP_EMAIL, self.IMAP_PASSWORD)
            client.select_folder('INBOX')
            logger.info('Open test mail box success')
            client.delete_messages([email_obj['messageId']])
            logger.info('Delete email success')

    @keyword
    def get_links_from_email(self, email_obj):
        """
        Returns all links found in the email body from given ``email_index``.

        Arguments:
        - ``email_index``: An email index to identity the email message.

        Examples:
        | Get Links From Email | email |
        """
        return re.findall(r'href=[\'"]?([^\'" >]+)', email_obj['body'])

    def _get_attachments(self, msg):
        file_names = []
        # Takes the raw data and breaks it into different 'parts' & python processes it 1 at a time [1]
        for part in msg.walk():
            if part.get_content_maintype() == 'multipart':  # Checks if the email is the correct 'type'.
                        # If it's a 'multipart', then it is incorrect type of email that can possible have an attachment
                continue  # Continue command skips the rest of code and checks the next 'part'

            if part.get('Content-Disposition') is None:  # Checks the 'Content-Disposition' field of the message.
                                # If it's empty, or "None", then we need to leave and go to the next part
                continue  # Continue command skips the rest of code and checks the next 'part'
            # So if the part isn't a 'multipart' type and has a 'Content-Disposition'...
            file_name = part.get_filename()  # Get the filename
            if bool(file_name):  # If bool(file_name) returns True
                with open(file_name, 'wb') as f:  # Opens file, w = creates if it doesn't exist / b = binary mode [2]
                    f.write(part.get_payload(decode=True))  # Returns the part is carrying, or it's payload, and decodes [3]
                file_names.append(file_name)
        return file_names

    def _encoded_words_to_text(self, encoded_words):
        final_word = ''
        for word in encoded_words.split(' '):
            encoded_word_regex = r'=\?{1}(.+)\?{1}([B|Q])\?{1}(.+)\?{1}='
            if re.match(encoded_word_regex, word) is None:
                strings = [final_word, word]
                final_word = ' '.join(filter(None, strings))
                continue
            charset, encoding, encoded_text = re.match(encoded_word_regex, word).groups()
            if encoding is 'B':
                byte_string = base64.b64decode(encoded_text)
            elif encoding is 'Q':
                byte_string = quopri.decodestring(encoded_text)
            else:
                strings = [final_word, word]
                final_word = ' '.join(filter(None, strings))
                continue
            strings = [final_word, byte_string.decode(charset)]
            final_word = ' '.join(filter(None, strings))
        return final_word

    def _decode_base64(self, data):
        """Decode base64, padding being optional.

        :param data: Base64 data as an ASCII byte string
        :returns: The decoded byte string.

        """
        missing_padding = len(data) % 4
        if missing_padding != 0:
            data += b'=' * (4 - missing_padding)
        return base64.decodebytes(data)
