"""
Management command to check Gmail for calendar export emails and import them.

Usage:
    python manage.py check_gmail_imports

Environment variables required:
    GMAIL_IMPORT_ADDRESS - Gmail address
    GMAIL_IMPORT_APP_PASSWORD - Gmail App Password (not regular password)

Optional:
    GMAIL_CALENDAR_SUBJECT - Exact subject line to look for (default: "[Oxy Calendar Import]")

The source field is derived from the subject by removing brackets.
E.g., "[Oxy Calendar Import]" -> source = "Oxy Calendar Import"
"""
import imaplib
import email
from email.header import decode_header
import json

from django.core.management.base import BaseCommand
from django.conf import settings

from calendar_events.views import import_calendar_events


class Command(BaseCommand):
    help = 'Check Gmail for calendar export emails and import them'

    def add_arguments(self, parser):
        parser.add_argument(
            '--subject',
            type=str,
            default=None,
            help='Subject line to search for (overrides GMAIL_CALENDAR_SUBJECT env var)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Check for emails but do not import or mark as read'
        )

    def handle(self, *args, **options):
        # Get Gmail credentials from settings/env
        gmail_address = getattr(settings, 'GMAIL_IMPORT_ADDRESS', None)
        gmail_password = getattr(settings, 'GMAIL_IMPORT_APP_PASSWORD', None)
        default_subject = getattr(settings, 'GMAIL_CALENDAR_SUBJECT', '[Oxy Calendar Import]')

        if not gmail_address or not gmail_password:
            self.stderr.write(self.style.ERROR(
                'GMAIL_IMPORT_ADDRESS and GMAIL_IMPORT_APP_PASSWORD must be set'
            ))
            return

        subject_filter = options['subject'] or default_subject
        dry_run = options['dry_run']

        self.stdout.write(f'Connecting to Gmail as {gmail_address}...')
        self.stdout.write(f'Looking for emails with subject containing: "{subject_filter}"')

        try:
            # Connect to Gmail IMAP
            mail = imaplib.IMAP4_SSL('imap.gmail.com')
            mail.login(gmail_address, gmail_password)
            mail.select('INBOX')

            # Search for unread emails with the specified subject
            search_criteria = f'(UNSEEN SUBJECT "{subject_filter}")'
            status, message_ids = mail.search(None, search_criteria)

            if status != 'OK':
                self.stderr.write(self.style.ERROR('Failed to search emails'))
                return

            email_ids = message_ids[0].split()
            self.stdout.write(f'Found {len(email_ids)} unread email(s) matching criteria')

            if not email_ids:
                self.stdout.write(self.style.SUCCESS('No new calendar exports to process'))
                mail.logout()
                return

            total_created = 0
            total_updated = 0
            processed_count = 0

            for email_id in email_ids:
                # Fetch the email
                status, msg_data = mail.fetch(email_id, '(RFC822)')
                if status != 'OK':
                    continue

                # Parse the email
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                # Decode subject
                subject, encoding = decode_header(msg['Subject'])[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding or 'utf-8')

                sender = msg['From']
                self.stdout.write(f'\nProcessing: "{subject}" from {sender}')

                # Look for JSON attachments
                json_data = None
                attachment_name = None

                for part in msg.walk():
                    content_disposition = part.get('Content-Disposition', '')
                    if 'attachment' in content_disposition:
                        filename = part.get_filename()
                        if filename and filename.endswith('.json'):
                            attachment_name = filename
                            payload = part.get_payload(decode=True)
                            try:
                                json_data = json.loads(payload.decode('utf-8'))
                                self.stdout.write(f'  Found JSON attachment: {filename}')
                                break
                            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                                self.stderr.write(f'  Error parsing {filename}: {e}')

                if not json_data:
                    self.stdout.write(self.style.WARNING('  No valid JSON attachment found, skipping'))
                    continue

                if dry_run:
                    self.stdout.write(self.style.WARNING('  [DRY RUN] Would import events from this email'))
                    continue

                # Derive source from subject by removing brackets
                # E.g., "[Oxy Calendar Import]" -> "Oxy Calendar Import"
                source = subject.strip()
                if source.startswith('[') and source.endswith(']'):
                    source = source[1:-1]

                # Import the calendar events
                try:
                    created, updated = import_calendar_events(json_data, source=source)
                    total_created += created
                    total_updated += updated
                    processed_count += 1
                    self.stdout.write(self.style.SUCCESS(
                        f'  Imported: {created} created, {updated} updated'
                    ))

                    # Mark email as read
                    mail.store(email_id, '+FLAGS', '\\Seen')

                    # Add label "Oxy Calendar Imports" (Gmail-specific)
                    try:
                        mail.store(email_id, '+X-GM-LABELS', '"Oxy Calendar Imports"')
                        self.stdout.write('  Labeled: Oxy Calendar Imports')
                    except Exception as label_err:
                        self.stdout.write(self.style.WARNING(f'  Could not add label: {label_err}'))

                    # Archive (remove from Inbox - Gmail keeps in All Mail)
                    try:
                        # In Gmail, deleting from INBOX moves to All Mail (archives)
                        mail.store(email_id, '+FLAGS', '\\Deleted')
                        mail.expunge()
                        self.stdout.write('  Archived (removed from Inbox)')
                    except Exception as archive_err:
                        self.stdout.write(self.style.WARNING(f'  Could not archive: {archive_err}'))

                except Exception as e:
                    self.stderr.write(self.style.ERROR(f'  Import error: {e}'))

            mail.logout()

            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS(
                f'Done! Processed {processed_count} email(s): '
                f'{total_created} events created, {total_updated} events updated'
            ))

        except imaplib.IMAP4.error as e:
            self.stderr.write(self.style.ERROR(f'IMAP error: {e}'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error: {e}'))
