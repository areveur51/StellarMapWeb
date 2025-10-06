#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'StellarMapWeb.settings')
django.setup()

from apiApp.models import StellarAccountSearchCache, PENDING_MAKE_PARENT_LINEAGE, IN_PROGRESS_MAKE_PARENT_LINEAGE, RE_INQUIRY

print("Checking for pending accounts...")
print(f"PENDING status constant: {PENDING_MAKE_PARENT_LINEAGE}")
print(f"IN_PROGRESS status constant: {IN_PROGRESS_MAKE_PARENT_LINEAGE}")
print(f"RE_INQUIRY status constant: {RE_INQUIRY}")
print()

# Try to get all records
all_records = StellarAccountSearchCache.objects.all()[:10]
print(f"Total records (first 10): {len(list(all_records))}")
for record in all_records:
    print(f"  - {record.stellar_account[:20]}... | {record.network_name} | {record.status}")

print()

# Try filtering with IN
pending_statuses = [PENDING_MAKE_PARENT_LINEAGE, IN_PROGRESS_MAKE_PARENT_LINEAGE, RE_INQUIRY]
print(f"Searching for statuses: {pending_statuses}")
pending_records = StellarAccountSearchCache.objects.filter(
    status__in=pending_statuses
).all()

print(f"Found {len(list(pending_records))} pending records")
for record in pending_records:
    print(f"  - Account: {record.stellar_account}")
    print(f"    Network: {record.network_name}")
    print(f"    Status: {record.status}")
    print(f"    Created: {record.created_at}")
    print()
