from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from inspirations_app.models import Inspiration
from PIL import Image
from io import BytesIO


class Command(BaseCommand):
    help = "Import films from Letterboxd Top 100 list"

    def handle(self, *_args, **_options):
        # All 100 films from the Letterboxd list
        letterboxd_films = [
            "The Insider",
            "Kids",
            "The Silence of the Lambs",
            "Lost in Translation",
            "Crumb",
            "Sexy Beast",
            "The September Issue",
            "Magnolia",
            "There Will Be Blood",
            "A Single Man",
            "Lovely & Amazing",
            "Clueless",
            "2001: A Space Odyssey",
            "Fight Club",
            "American Beauty",
            "Tiny Furniture",
            "Indie Game: The Movie",
            "Ghost World",
            "Bully",
            "Dig!",
            "The Great Happiness Space: Tale of an Osaka Love Thief",
            "I ♥ Huckabees",
            "The Dreamers",
            "Dazed and Confused",
            "Sabrina",
            "Tombstone",
            "Rounders",
            "Lorenzo's Oil",
            "The Object of My Affection",
            "Shame",
            "The 400 Blows",
            "Wayne's World",
            "Spirited Away",
            "Almost Famous",
            "Good Will Hunting",
            "Hedwig and the Angry Inch",
            "Donnie Darko",
            "Punch-Drunk Love",
            "Boogie Nights",
            "Capturing the Friedmans",
            "The Squid and the Whale",
            "A.I. Artificial Intelligence",
            "Startup.com",
            "Igby Goes Down",
            "Rachel Getting Married",
            "Z Channel: A Magnificent Obsession",
            "A Serious Man",
            "Adventureland",
            "Beats Rhymes & Life: The Travels of A Tribe Called Quest",
            "Bill Cunningham New York",
            "Jiro Dreams of Sushi",
            "Paradise Lost: The Child Murders at Robin Hood Hills",
            "Superbad",
            "Dont Look Back",
            "Casino",
            "Enron: The Smartest Guys in the Room",
            "Se7en",
            "Auto Focus",
            "Being John Malkovich",
            "Romeo + Juliet",
            "Moulin Rouge!",
            "Exit Through the Gift Shop",
            "He Got Game",
            "One Hundred and One Dalmatians",
            "Wonder Boys",
            "Manhattan",
            "A Clockwork Orange",
            "Once Upon a Time in America",
            "Jackie Brown",
            "Lolita",
            "Point Break",
            "Eyes Wide Shut",
            "The Cell",
            "The Exorcist",
            "Boiler Room",
            "The Royal Tenenbaums",
            "My Father the Hero",
            "One Fine Day",
            "The Craft",
            "Father of the Bride",
            "Bye Bye Love",
            "Cruel Intentions",
            "South Park: Bigger, Longer & Uncut",
            "Top Gun",
            "Empire Records",
            "Fear",
            "Bend It Like Beckham",
            "True Lies",
            "The Blair Witch Project",
            "Who Framed Roger Rabbit",
            "Friday",
            "24 Hour Party People",
            "The Shining",
            "Natural Born Killers",
            "Gosford Park",
            "Pulp Fiction",
            "Inglourious Basterds",
            "Zodiac",
            "Vicky Cristina Barcelona",
            "Mallrats",
        ]

        # Get existing film inspirations (case-insensitive check)
        existing_films = set(Inspiration.objects.filter(type="Film").values_list("title", flat=True))
        existing_films_lower = {title.lower() for title in existing_films}

        # Create a simple gray placeholder image (256x362)
        placeholder_img = Image.new("RGB", (256, 362), color="#cccccc")
        img_buffer = BytesIO()
        placeholder_img.save(img_buffer, format="JPEG", quality=85)
        img_buffer.seek(0)

        created_count = 0
        skipped_count = 0

        for film_title in letterboxd_films:
            # Check if already exists (case-insensitive)
            if film_title.lower() in existing_films_lower:
                self.stdout.write(f'Skipping "{film_title}" - already exists')
                skipped_count += 1
                continue

            # Create the inspiration with placeholder image
            try:
                # Reset buffer position for each iteration
                img_buffer.seek(0)
                image_file = ContentFile(img_buffer.read(), name=f'{film_title.replace(" ", "_").lower()}.jpg')

                Inspiration.objects.create(title=film_title, type="Film", image=image_file)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Created inspiration for "{film_title}" (placeholder image - update via settings)'
                    )
                )
                created_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error creating "{film_title}": {str(e)}'))

        self.stdout.write(
            self.style.SUCCESS(f"\nDone! Created {created_count} inspirations, skipped {skipped_count} existing ones.")
        )
