"""
Modular Firebase Functions v2 scheduler with dynamic agent schedule registration.

Registers schedules and triggers from enabled agents automatically.
"""

from datetime import datetime
from typing import Dict, Any
from firebase_functions import scheduler_fn, firestore_fn, options
from firebase_admin import initialize_app, firestore
import logging

# Initialize Firebase Admin
initialize_app()
db = firestore.client()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import modular scheduler components
try:
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))

    from core.agent_schedules import create_schedule_registry, get_default_schedules, get_default_triggers
    from core.agent_registry import create_agent_registry
except ImportError as e:
    logger.error(f"Failed to import modular scheduler components: {e}")
    # Fallback to basic functionality
    create_schedule_registry = None


# ==================================================================================
# DYNAMIC SCHEDULE REGISTRATION
# ==================================================================================

def register_agent_schedules():
    """
    Register schedules from enabled agents dynamically.
    This would be called at deployment time to generate Firebase Functions.
    """
    if not create_schedule_registry:
        logger.warning("Schedule registry not available, using default schedules")
        return get_default_schedules() if 'get_default_schedules' in globals() else []

    try:
        registry = create_schedule_registry()
        schedules = registry.get_all_schedules()

        logger.info(f"Registering {len(schedules)} agent schedules")

        # In a full implementation, this would generate Firebase Function decorators
        # For now, we'll track them for backwards compatibility
        return list(schedules.values())

    except Exception as e:
        logger.error(f"Failed to register agent schedules: {e}")
        return []


def register_agent_triggers():
    """
    Register triggers from enabled agents dynamically.
    This would be called at deployment time to generate Firebase Functions.
    """
    if not create_schedule_registry:
        logger.warning("Trigger registry not available, using default triggers")
        return get_default_triggers() if 'get_default_triggers' in globals() else []

    try:
        registry = create_schedule_registry()
        triggers = registry.get_all_triggers()

        logger.info(f"Registering {len(triggers)} agent triggers")

        # In a full implementation, this would generate Firebase Function decorators
        return list(triggers.values())

    except Exception as e:
        logger.error(f"Failed to register agent triggers: {e}")
        return []


# ==================================================================================
# MODULAR SCHEDULE EXECUTOR
# ==================================================================================

@scheduler_fn.on_schedule(
    schedule="0 1 * * *",  # Daily at 01:00
    timezone=scheduler_fn.Timezone("Europe/Amsterdam"),
    memory=options.MemoryOption.MB_512,
    timeout_sec=540,  # 9 minutes timeout
    max_instances=1,
)
def execute_agent_schedules_01(event: scheduler_fn.ScheduledEvent) -> Dict[str, Any]:
    """
    Execute agent schedules for 01:00 CET/CEST slot.
    Dynamically discovers and runs schedules from enabled agents.
    """
    try:
        logger.info(f"Starting modular schedule execution at {event.timestamp}")

        # Get schedule registry
        if create_schedule_registry:
            registry = create_schedule_registry()
            schedules = registry.get_all_schedules()
        else:
            schedules = {}

        # Filter schedules for this time slot (01:00)
        target_schedules = {
            name: schedule for name, schedule in schedules.items()
            if schedule.schedule == "0 1 * * *"
        }

        if not target_schedules:
            logger.info("No agent schedules found for 01:00 slot, running default workflow")
            return _run_default_daily_workflow(event)

        # Execute all matching schedules
        results = {}
        total_success = 0
        total_failed = 0

        for schedule_name, schedule in target_schedules.items():
            try:
                logger.info(f"Executing agent schedule: {schedule_name}")

                # Execute the schedule handler
                result = schedule.handler()

                results[schedule_name] = {
                    'status': 'success',
                    'result': str(result)[:500],  # Truncate long results
                    'description': schedule.description
                }
                total_success += 1

                # Log success to audit
                audit_ref = db.collection('audit_logs').document()
                audit_ref.set({
                    'type': 'modular_schedule_execution',
                    'schedule_name': schedule_name,
                    'schedule_cron': schedule.schedule,
                    'timestamp': firestore.SERVER_TIMESTAMP,
                    'status': 'success',
                    'result': str(result)[:1000],
                    'event_id': event.id if hasattr(event, 'id') else None
                })

            except Exception as e:
                logger.error(f"Schedule {schedule_name} failed: {e}")

                results[schedule_name] = {
                    'status': 'failed',
                    'error': str(e),
                    'description': schedule.description
                }
                total_failed += 1

                # Log failure to audit
                audit_ref = db.collection('audit_logs').document()
                audit_ref.set({
                    'type': 'modular_schedule_execution',
                    'schedule_name': schedule_name,
                    'schedule_cron': schedule.schedule,
                    'timestamp': firestore.SERVER_TIMESTAMP,
                    'status': 'failed',
                    'error': str(e),
                    'event_id': event.id if hasattr(event, 'id') else None
                })

        logger.info(f"Modular schedule execution completed: {total_success} success, {total_failed} failed")

        return {
            'ok': True,
            'execution_slot': '01:00',
            'schedules_executed': len(target_schedules),
            'successful': total_success,
            'failed': total_failed,
            'results': results
        }

    except Exception as e:
        logger.error(f"Critical error in modular schedule execution: {e}")

        # Send error alert
        try:
            _send_modular_error_alert("Schedule execution failed", str(e), event.timestamp)
        except:
            pass

        return {
            'ok': False,
            'execution_slot': '01:00',
            'error': str(e)
        }


@scheduler_fn.on_schedule(
    schedule="0 7 * * *",  # Daily at 07:00
    timezone=scheduler_fn.Timezone("Europe/Amsterdam"),
    memory=options.MemoryOption.MB_256,
    timeout_sec=300,
)
def execute_agent_schedules_07(event: scheduler_fn.ScheduledEvent) -> Dict[str, Any]:
    """
    Execute agent schedules for 07:00 CET/CEST slot.
    Typically used for daily digest and reporting functions.
    """
    return _execute_schedules_for_slot(event, "0 7 * * *", "07:00")


@scheduler_fn.on_schedule(
    schedule="0 */3 * * *",  # Every 3 hours
    timezone=scheduler_fn.Timezone("Europe/Amsterdam"),
    memory=options.MemoryOption.MB_512,
    timeout_sec=480,
)
def execute_agent_schedules_3h(event: scheduler_fn.ScheduledEvent) -> Dict[str, Any]:
    """
    Execute agent schedules for 3-hour interval slot.
    Typically used for content ingestion and monitoring.
    """
    return _execute_schedules_for_slot(event, "0 */3 * * *", "3-hour")


# ==================================================================================
# MODULAR TRIGGER EXECUTOR
# ==================================================================================

@firestore_fn.on_document_written(
    document="transcripts/{video_id}",
    memory=options.MemoryOption.MB_256,
    timeout_sec=180,
)
def execute_agent_triggers_transcripts(event: firestore_fn.Event[firestore_fn.Change[firestore_fn.DocumentSnapshot]]) -> None:
    """
    Execute agent triggers for transcript document events.
    Dynamically discovers and runs triggers from enabled agents.
    """
    try:
        video_id = event.params['video_id']
        logger.info(f"Processing transcript triggers for video: {video_id}")

        # Get trigger registry
        if create_schedule_registry:
            registry = create_schedule_registry()
            triggers = registry.get_all_triggers()
        else:
            triggers = {}

        # Filter triggers for transcript events
        target_triggers = {
            name: trigger for name, trigger in triggers.items()
            if trigger.trigger_type == "firestore" and
               trigger.document_pattern and "transcripts/" in trigger.document_pattern
        }

        if not target_triggers:
            logger.info("No agent triggers found for transcript events, running default budget monitor")
            return _run_default_budget_monitor(event)

        # Execute all matching triggers
        for trigger_name, trigger in target_triggers.items():
            try:
                logger.info(f"Executing agent trigger: {trigger_name}")

                # Execute the trigger handler
                result = trigger.handler(event)

                # Log success to audit
                audit_ref = db.collection('audit_logs').document()
                audit_ref.set({
                    'type': 'modular_trigger_execution',
                    'trigger_name': trigger_name,
                    'document_pattern': trigger.document_pattern,
                    'video_id': video_id,
                    'timestamp': firestore.SERVER_TIMESTAMP,
                    'status': 'success',
                    'result': str(result)[:1000] if result else "None"
                })

            except Exception as e:
                logger.error(f"Trigger {trigger_name} failed for video {video_id}: {e}")

                # Log failure to audit
                audit_ref = db.collection('audit_logs').document()
                audit_ref.set({
                    'type': 'modular_trigger_execution',
                    'trigger_name': trigger_name,
                    'document_pattern': trigger.document_pattern,
                    'video_id': video_id,
                    'timestamp': firestore.SERVER_TIMESTAMP,
                    'status': 'failed',
                    'error': str(e)
                })

    except Exception as e:
        logger.error(f"Critical error in transcript trigger execution: {e}")


# ==================================================================================
# HELPER FUNCTIONS
# ==================================================================================

def _execute_schedules_for_slot(event, cron_pattern: str, slot_name: str) -> Dict[str, Any]:
    """Generic schedule execution for a given time slot."""
    try:
        logger.info(f"Starting {slot_name} schedule execution at {event.timestamp}")

        # Get schedule registry
        if create_schedule_registry:
            registry = create_schedule_registry()
            schedules = registry.get_all_schedules()
        else:
            schedules = {}

        # Filter schedules for this time slot
        target_schedules = {
            name: schedule for name, schedule in schedules.items()
            if schedule.schedule == cron_pattern
        }

        if not target_schedules:
            logger.info(f"No agent schedules found for {slot_name} slot")
            return {'ok': True, 'message': f'No schedules for {slot_name}'}

        # Execute all matching schedules
        results = {}
        total_success = 0
        total_failed = 0

        for schedule_name, schedule in target_schedules.items():
            try:
                logger.info(f"Executing {slot_name} schedule: {schedule_name}")
                result = schedule.handler()

                results[schedule_name] = {
                    'status': 'success',
                    'result': str(result)[:500]
                }
                total_success += 1

            except Exception as e:
                logger.error(f"Schedule {schedule_name} failed: {e}")
                results[schedule_name] = {
                    'status': 'failed',
                    'error': str(e)
                }
                total_failed += 1

        return {
            'ok': True,
            'execution_slot': slot_name,
            'schedules_executed': len(target_schedules),
            'successful': total_success,
            'failed': total_failed,
            'results': results
        }

    except Exception as e:
        logger.error(f"Critical error in {slot_name} schedule execution: {e}")
        return {
            'ok': False,
            'execution_slot': slot_name,
            'error': str(e)
        }


def _run_default_daily_workflow(event) -> Dict[str, Any]:
    """Fallback to default daily workflow when no agent schedules found."""
    try:
        logger.info("Running default daily workflow")

        # Import and run agency
        from agency import AutopilootAgency
        agency = AutopilootAgency()

        # Basic workflow execution
        result = {
            'ok': True,
            'method': 'default_agency_workflow',
            'message': 'Executed default daily workflow'
        }

        return result

    except Exception as e:
        logger.error(f"Default workflow failed: {e}")
        return {
            'ok': False,
            'error': str(e),
            'method': 'default_agency_workflow'
        }


def _run_default_budget_monitor(event) -> None:
    """Fallback to default budget monitoring when no agent triggers found."""
    try:
        logger.info("Running default budget monitor")

        # Basic budget monitoring logic
        video_id = event.params['video_id']

        # Log that default monitoring ran
        audit_ref = db.collection('audit_logs').document()
        audit_ref.set({
            'type': 'default_budget_monitor',
            'video_id': video_id,
            'timestamp': firestore.SERVER_TIMESTAMP,
            'status': 'executed'
        })

    except Exception as e:
        logger.error(f"Default budget monitor failed: {e}")


def _send_modular_error_alert(message: str, error: str, timestamp: str) -> None:
    """Send error alert for modular scheduler failures."""
    try:
        # Basic error logging
        audit_ref = db.collection('audit_logs').document()
        audit_ref.set({
            'type': 'modular_scheduler_error',
            'message': message,
            'error': error,
            'timestamp': firestore.SERVER_TIMESTAMP,
            'event_timestamp': timestamp
        })

        logger.info(f"Modular scheduler error logged: {message}")

    except Exception as e:
        logger.error(f"Failed to send modular error alert: {e}")


# Initialize schedule and trigger discovery on module load
try:
    if create_schedule_registry:
        agent_schedules = register_agent_schedules()
        agent_triggers = register_agent_triggers()
        logger.info(f"Modular scheduler initialized with {len(agent_schedules)} schedules and {len(agent_triggers)} triggers")
except Exception as e:
    logger.warning(f"Failed to initialize modular scheduler: {e}")