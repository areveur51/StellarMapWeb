"""
Near-real-time SDK worker — interest-driven, free Horizon path.

Runs stellar_sdk_pipeline in a tight loop for PENDING accounts only.
Does not enable BigQuery or the full multi-cron suite.

Usage:
  python manage.py run_sdk_near_rt_worker
  python manage.py run_sdk_near_rt_worker --once
  python manage.py run_sdk_near_rt_worker --interval 45 --limit 5 --concurrent 3

Requires write-capable DB (CASSANDRA_READ_ONLY must be 0).
"""
from __future__ import annotations

import logging
import time

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        'Near-RT worker: loop stellar_sdk_pipeline for PENDING accounts '
        '(free Horizon; small batches). Prefer this over STELLARMAP_CRON on NAS.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--once',
            action='store_true',
            help='Run a single pipeline batch and exit',
        )
        parser.add_argument(
            '--interval',
            type=int,
            default=None,
            help='Seconds between batches (default: NEAR_RT_WORKER_INTERVAL_SEC)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Max accounts per batch (default: NEAR_RT_WORKER_LIMIT)',
        )
        parser.add_argument(
            '--concurrent',
            type=int,
            default=None,
            help='Max concurrent SDK jobs (default: NEAR_RT_WORKER_CONCURRENT)',
        )
        parser.add_argument(
            '--network',
            type=str,
            default=None,
            choices=['public', 'testnet'],
            help='Stellar network (default: NEAR_RT_WORKER_NETWORK)',
        )
        parser.add_argument(
            '--max-iterations',
            type=int,
            default=0,
            help='Stop after N iterations (0 = forever; useful for tests)',
        )

    def handle(self, *args, **options):
        if getattr(settings, 'CASSANDRA_READ_ONLY', False):
            self.stderr.write(
                self.style.ERROR(
                    'CASSANDRA_READ_ONLY=1: refusing to run SDK worker '
                    '(writes disabled). Set CASSANDRA_READ_ONLY=0 and use a '
                    'write-capable Astra token for near-RT ingest.'
                )
            )
            return

        interval = options['interval']
        if interval is None:
            interval = int(getattr(settings, 'NEAR_RT_WORKER_INTERVAL_SEC', 45))
        limit = options['limit']
        if limit is None:
            limit = int(getattr(settings, 'NEAR_RT_WORKER_LIMIT', 5))
        concurrent = options['concurrent']
        if concurrent is None:
            concurrent = int(getattr(settings, 'NEAR_RT_WORKER_CONCURRENT', 3))
        network = options['network'] or getattr(
            settings, 'NEAR_RT_WORKER_NETWORK', 'public'
        )
        once = options['once']
        max_iter = int(options['max_iterations'] or 0)

        self.stdout.write(
            self.style.SUCCESS(
                f'Near-RT SDK worker  interval={interval}s limit={limit} '
                f'concurrent={concurrent} network={network} once={once}'
            )
        )

        n = 0
        while True:
            n += 1
            t0 = time.time()
            try:
                call_command(
                    'stellar_sdk_pipeline',
                    limit=limit,
                    concurrent=concurrent,
                    network=network,
                )
            except Exception as e:
                logger.exception('near-rt SDK batch failed: %s', e)
                self.stderr.write(self.style.ERROR(f'batch error: {e}'))
            elapsed = time.time() - t0
            self.stdout.write(
                f'[near-rt] iteration={n} elapsed={elapsed:.1f}s'
            )

            if once or (max_iter and n >= max_iter):
                break

            # Sleep remaining interval (minimum 5s)
            sleep_for = max(5, interval - int(elapsed))
            time.sleep(sleep_for)
