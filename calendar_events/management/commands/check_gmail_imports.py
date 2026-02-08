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
    help = "Check Gmail for calendar export emails and import them"

    def add_arguments(self, parser):
        parser.add_argument(
            "--subject",
            type=str,
            default=None,
            help="Subject line to search for (overrides GMAIL_CALENDAR_SUBJECT env var)",
        )
        parser.add_argument("--dry-run", action="store_true", help="Check for emails but do not import or mark as read")

    def _extract_json_attachment(self, msg):
        """Extract the first valid JSON attachment from an email message."""
        for part in msg.walk():
            content_disposition = part.get("Content-Disposition", "")
            if "attachment" not in content_disposition:
                continue
            filename = part.get_filename()
            if not filename or not filename.endswith(".json"):
                continue
            payload = part.get_payload(decode=True)
            try:
                json_data = json.loads(payload.decode("utf-8"))
                self.stdout.write(f"  Found JSON attachment: {filename}")
                return json_data
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                self.stderr.write(f"  Error parsing {filename}: {e}")
        return None

    def _derive_source_from_subject(self, subject):
        """Derive source string from email subject by stripping brackets."""
        source = subject.strip()
        if source.startswith("[") and source.endswith("]"):
            return source[1:-1]
        return source

    def _import_and_archive_email(self, mail, email_id, json_data, source):
        """Import calendar events from JSON data and archive the email."""
        created, updated, canceled = import_calendar_events(json_data, source=source)
        self.stdout.write(self.style.SUCCESS(f"  Imported: {created} created, {updated} updated, {canceled} canceled"))

        mail.store(email_id, "+FLAGS", "\\Seen")

        try:
            mail.store(email_id, "+X-GM-LABELS", '"Oxy Calendar Imports"')
            self.stdout.write("  Labeled: Oxy Calendar Imports")
        except Exception as label_err:
            self.stdout.write(self.style.WARNING(f"  Could not add label: {label_err}"))

        try:
            mail.store(email_id, "+FLAGS", "\\Deleted")
            mail.expunge()
            self.stdout.write("  Archived (removed from Inbox)")
        except Exception as archive_err:
            self.stdout.write(self.style.WARNING(f"  Could not archive: {archive_err}"))

        return created, updated, canceled

    def _process_single_email(self, mail, email_id, dry_run):
        """Fetch, parse, and process a single email. Returns (created, updated, canceled) or None."""
        status, msg_data = mail.fetch(email_id, "(RFC822)")
        if status != "OK":
            return None

        msg = email.message_from_bytes(msg_data[0][1])

        subject, encoding = decode_header(msg["Subject"])[0]
        if isinstance(subject, bytes):
            subject = subject.decode(encoding or "utf-8")

        self.stdout.write(f'\nProcessing: "{subject}" from {msg["From"]}')

        json_data = self._extract_json_attachment(msg)
        if not json_data:
            self.stdout.write(self.style.WARNING("  No valid JSON attachment found, skipping"))
            return None

        if dry_run:
            self.stdout.write(self.style.WARNING("  [DRY RUN] Would import events from this email"))
            return None

        source = self._derive_source_from_subject(subject)
        try:
            return self._import_and_archive_email(mail, email_id, json_data, source)
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"  Import error: {e}"))
            return None

    def handle(self, *_args, **options):
        gmail_address = getattr(settings, "GMAIL_IMPORT_ADDRESS", None)
        gmail_password = getattr(settings, "GMAIL_IMPORT_APP_PASSWORD", None)
        default_subject = getattr(settings, "GMAIL_CALENDAR_SUBJECT", "[Oxy Calendar Import]")

        if not gmail_address or not gmail_password:
            self.stderr.write(self.style.ERROR("GMAIL_IMPORT_ADDRESS and GMAIL_IMPORT_APP_PASSWORD must be set"))
            return

        subject_filter = options["subject"] or default_subject
        dry_run = options["dry_run"]

        self.stdout.write(f"Connecting to Gmail as {gmail_address}...")
        self.stdout.write(f'Looking for emails with subject containing: "{subject_filter}"')

        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(gmail_address, gmail_password)
            mail.select("INBOX")

            status, message_ids = mail.search(None, f'(UNSEEN SUBJECT "{subject_filter}")')
            if status != "OK":
                self.stderr.write(self.style.ERROR("Failed to search emails"))
                return

            email_ids = message_ids[0].split()
            self.stdout.write(f"Found {len(email_ids)} unread email(s) matching criteria")

            if not email_ids:
                self.stdout.write(self.style.SUCCESS("No new calendar exports to process"))
                mail.logout()
                return

            total_created = 0
            total_updated = 0
            total_canceled = 0
            processed_count = 0

            for email_id in email_ids:
                result = self._process_single_email(mail, email_id, dry_run)
                if result:
                    created, updated, canceled = result
                    total_created += created
                    total_updated += updated
                    total_canceled += canceled
                    processed_count += 1

            mail.logout()

            self.stdout.write("")
            self.stdout.write(
                self.style.SUCCESS(
                    f"Done! Processed {processed_count} email(s): "
                    f"{total_created} created, {total_updated} updated, {total_canceled} canceled"
                )
            )

        except imaplib.IMAP4.error as e:
            self.stderr.write(self.style.ERROR(f"IMAP error: {e}"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error: {e}"))
