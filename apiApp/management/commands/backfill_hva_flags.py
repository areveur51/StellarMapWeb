from django.core.management.base import BaseCommand
from apiApp.models import StellarCreatorAccountLineage, BigQueryPipelineConfig
import sentry_sdk


class Command(BaseCommand):
    help = 'Backfill is_hva flags and HVA tags based on admin-configured threshold'

    def add_arguments(self, parser):
        parser.add_argument(
            '--network',
            type=str,
            default='public',
            help='Network name (public or testnet, default: public)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes'
        )

    def handle(self, *args, **options):
        network_name = options['network']
        dry_run = options['dry_run']
        
        self.stdout.write(self.style.SUCCESS(
            f"\n{'='*60}\n"
            f"Backfilling HVA Flags and Tags\n"
            f"{'='*60}\n"
        ))
        
        # Get admin-configured threshold
        try:
            config = BigQueryPipelineConfig.objects.filter(config_id='default').first()
            hva_threshold = config.hva_threshold_xlm if config else 100000.0
        except Exception as e:
            hva_threshold = 100000.0
            self.stdout.write(self.style.WARNING(
                f"Could not load admin config, using default threshold: {e}"
            ))
        
        self.stdout.write(
            f"Network: {network_name}\n"
            f"HVA Threshold: {hva_threshold:,.0f} XLM\n"
            f"Dry Run: {dry_run}\n"
            f"{'='*60}\n"
        )
        
        # Get all accounts for the network
        try:
            self.stdout.write("Fetching all accounts...")
            all_accounts = list(StellarCreatorAccountLineage.objects.filter(
                network_name=network_name
            ).all())
            
            self.stdout.write(self.style.SUCCESS(
                f"✓ Found {len(all_accounts)} total accounts\n"
            ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error fetching accounts: {e}"))
            sentry_sdk.capture_exception(e)
            return
        
        # Track statistics
        stats = {
            'total': len(all_accounts),
            'already_correct': 0,
            'set_hva': 0,
            'cleared_hva': 0,
            'errors': 0,
        }
        
        # Process each account
        for idx, account in enumerate(all_accounts, 1):
            try:
                balance = account.xlm_balance or 0.0
                should_be_hva = balance >= hva_threshold
                currently_is_hva = account.is_hva
                
                # Check if HVA tag is present
                tags_list = [tag.strip() for tag in account.tags.split(',')] if account.tags else []
                has_hva_tag = 'HVA' in tags_list
                
                # Determine if update is needed
                needs_update = (should_be_hva != currently_is_hva) or (should_be_hva != has_hva_tag)
                
                if not needs_update:
                    stats['already_correct'] += 1
                    continue
                
                # Show progress every 100 accounts
                if idx % 100 == 0:
                    self.stdout.write(f"Progress: {idx}/{len(all_accounts)} accounts processed...")
                
                # Prepare update description
                if should_be_hva and not currently_is_hva:
                    action = "SET HVA"
                    stats['set_hva'] += 1
                elif not should_be_hva and currently_is_hva:
                    action = "CLEAR HVA"
                    stats['cleared_hva'] += 1
                else:
                    action = "FIX TAG"
                    if should_be_hva:
                        stats['set_hva'] += 1
                    else:
                        stats['cleared_hva'] += 1
                
                # Log the change
                self.stdout.write(
                    f"  {action}: {account.stellar_account[:20]}... "
                    f"({balance:,.2f} XLM, was_hva={currently_is_hva}, "
                    f"had_tag={has_hva_tag})"
                )
                
                if not dry_run:
                    # Update the flag and tag
                    account.is_hva = should_be_hva
                    
                    if should_be_hva:
                        # Add HVA tag
                        if 'HVA' not in tags_list:
                            tags_list.append('HVA')
                    else:
                        # Remove HVA tag
                        tags_list = [tag for tag in tags_list if tag != 'HVA']
                    
                    account.tags = ','.join(tags_list) if tags_list else ''
                    
                    # Save without triggering the auto-tag logic (direct update)
                    account.save()
                
            except Exception as e:
                stats['errors'] += 1
                self.stdout.write(self.style.ERROR(
                    f"  ✗ Error updating {account.stellar_account}: {e}"
                ))
                sentry_sdk.capture_exception(e)
        
        # Print summary
        self.stdout.write(self.style.SUCCESS(
            f"\n{'='*60}\n"
            f"✅ Backfill Complete!\n"
            f"{'='*60}\n"
            f"Total Accounts: {stats['total']}\n"
            f"Already Correct: {stats['already_correct']}\n"
            f"Set HVA: {stats['set_hva']}\n"
            f"Cleared HVA: {stats['cleared_hva']}\n"
            f"Errors: {stats['errors']}\n"
            f"{'='*60}\n"
        ))
        
        if dry_run:
            self.stdout.write(self.style.WARNING(
                "\n⚠ DRY RUN MODE - No changes were made.\n"
                "Run without --dry-run to apply changes.\n"
            ))
