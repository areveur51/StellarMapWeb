from datetime import datetime, timezone
from apiApp.models import StellarAccountStageExecution


STAGE_DEFINITIONS = [
    {"stage_number": 1, "cron_name": "cron_make_parent_account_lineage"},
    {"stage_number": 2, "cron_name": "cron_collect_account_horizon_data"},
    {"stage_number": 3, "cron_name": "cron_collect_account_lineage_attributes"},
    {"stage_number": 4, "cron_name": "cron_collect_account_lineage_assets"},
    {"stage_number": 5, "cron_name": "cron_collect_account_lineage_flags"},
    {"stage_number": 6, "cron_name": "cron_collect_account_lineage_se_directory"},
    {"stage_number": 7, "cron_name": "cron_collect_account_lineage_creator"},
    {"stage_number": 8, "cron_name": "cron_make_grandparent_account_lineage"},
]


def initialize_stage_executions(stellar_account, network_name):
    """
    Initialize all 8 stage execution records for a stellar account.
    Creates records with PENDING status if they don't already exist.
    
    Args:
        stellar_account (str): The Stellar account address
        network_name (str): The network ('public' or 'testnet')
    
    Returns:
        int: Number of stages initialized
    """
    created_count = 0
    current_time = datetime.now(timezone.utc)
    
    for stage_def in STAGE_DEFINITIONS:
        existing = StellarAccountStageExecution.objects.filter(
            stellar_account=stellar_account,
            network_name=network_name,
            stage_number=stage_def["stage_number"]
        ).first()
        
        if not existing:
            StellarAccountStageExecution.create(
                stellar_account=stellar_account,
                network_name=network_name,
                stage_number=stage_def["stage_number"],
                cron_name=stage_def["cron_name"],
                status="PENDING",
                execution_time_ms=0,
                error_message="",
                created_at=current_time
            )
            created_count += 1
    
    return created_count


def update_stage_execution(stellar_account, network_name, stage_number, status, execution_time_ms, error_message=""):
    """
    Update an existing stage execution record or create if doesn't exist.
    
    Args:
        stellar_account (str): The Stellar account address
        network_name (str): The network ('public' or 'testnet')
        stage_number (int): Stage number (1-8)
        status (str): Status ('PENDING', 'IN_PROGRESS', 'SUCCESS', 'FAILED', 'ERROR', 'TIMEOUT')
        execution_time_ms (int): Execution time in milliseconds
        error_message (str): Error message if any
    
    Returns:
        StellarAccountStageExecution: The updated or created record
    """
    current_time = datetime.now(timezone.utc)
    
    existing = StellarAccountStageExecution.objects.filter(
        stellar_account=stellar_account,
        network_name=network_name,
        stage_number=stage_number
    ).first()
    
    if existing:
        existing.status = status
        existing.execution_time_ms = execution_time_ms
        existing.error_message = error_message
        existing.updated_at = current_time
        existing.save()
        return existing
    else:
        cron_name = next((s["cron_name"] for s in STAGE_DEFINITIONS if s["stage_number"] == stage_number), f"stage_{stage_number}")
        
        return StellarAccountStageExecution.create(
            stellar_account=stellar_account,
            network_name=network_name,
            stage_number=stage_number,
            cron_name=cron_name,
            status=status,
            execution_time_ms=execution_time_ms,
            error_message=error_message,
            created_at=current_time
        )
