# Health and watchdog

Workers persist:
- pid
- started_at
- last_loop_at
- last_success_at
- queue_backlog
- active_job_id
- active_phase
- restart_count
- recent_failures

Doctor classifies:
- healthy
- idle
- draining
- degraded
- stuck
- crash_loop
- stopped
- unknown
