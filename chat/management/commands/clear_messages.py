from django.core.management.base import BaseCommand
from chat.models import Message

class Command(BaseCommand):
    help = 'Clear all messages from the database'

    def handle(self, *args, **options):
        # Count messages before deletion
        count = Message.objects.count()
        
        self.stdout.write(f'Found {count} messages in database')
        
        if count == 0:
            self.stdout.write(self.style.WARNING('No messages to delete'))
            return
        
        # Ask for confirmation
        confirm = input(f'Are you sure you want to delete all {count} messages? (yes/no): ')
        
        if confirm.lower() == 'yes':
            # Delete all messages
            Message.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f'Successfully deleted {count} messages'))
        else:
            self.stdout.write(self.style.WARNING('Operation cancelled'))
