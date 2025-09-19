# apiApp/models.py
from django.db import models
import uuid

# Constants for choices (secure defaults)
PENDING = 'pending'
IN_PROGRESS = 'in_progress'
COMPLETED = 'completed'
STATUS_CHOICES = ((PENDING, 'Pending'), (IN_PROGRESS, 'In Progress'),
                  (COMPLETED, 'Completed'))

TESTNET = 'testnet'
PUBLIC = 'public'
NETWORK_CHOICES = ((TESTNET, 'testnet'), (PUBLIC, 'public'))

# Note: Cassandra models temporarily commented out to use SQLite
# TODO: Add proper Django models as needed for your API functionality

# Placeholder for API models - add your Django models here as needed
# Example:
# class YourApiModel(models.Model):
#     name = models.CharField(max_length=100)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)