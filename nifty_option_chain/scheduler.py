"""
Nifty Option Chain Scheduler
-----------------------------
Runs the option-chain analysis every day at 20:00 IST (8 PM).

Two modes are supported — use whichever suits your environment:

  Mode 1 – APScheduler  (recommended, pip install apscheduler)
      python scheduler.py

  Mode 2 – Plain `schedule` library  (pip install schedule)
      python scheduler.py --simple

Both modes keep the process alive in a loop and execute
nifty_option_chain.run() at the configured time.

IST = UTC+5:30, so 20:00 IST = 14:30 UTC.
The scheduler uses the LOCAL system clock, so make sure the server's
timezone is set to IST, or use the --utc flag to schedule at 14:30 UTC.
"""

import sys
import time
import argparse
import datetime
import logging

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%d-%b-%Y %H:%M:%S",
)
log = logging.getLogger(__name__)


# ─── Job ──────────────────────────────────────────────────────────────────────

def job():
    """The task executed at the scheduled time."""
    log.info("=== Nifty Option Chain Analysis triggered ===")
    try:
        from nifty_option_chain import run
        run()
    except ImportError as e:
        log.error("Could not import nifty_option_chain: %s", e)
    except Exception as e:
        log.exception("Analysis failed: %s", e)


# ─── Mode 1 : APScheduler ─────────────────────────────────────────────────────

def run_apscheduler(hour: int, minute: int, timezone: str):
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        log.error(
            "APScheduler not installed.  Run:  pip install apscheduler\n"
            "Or switch to simple mode:  python scheduler.py --simple"
        )
        sys.exit(1)

    scheduler = BlockingScheduler(timezone=timezone)
    trigger   = CronTrigger(hour=hour, minute=minute, timezone=timezone)
    scheduler.add_job(job, trigger, id="nifty_oc", name="Nifty Option Chain")

    log.info(
        "APScheduler started.  Job fires every day at %02d:%02d (%s).",
        hour, minute, timezone,
    )
    log.info("Press Ctrl+C to stop.")

    # Run immediately on startup so you can verify it works
    log.info("Running initial analysis now …")
    job()

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped.")


# ─── Mode 2 : plain `schedule` library ───────────────────────────────────────

def run_simple_schedule(run_time: str):
    """
    run_time: "HH:MM" string, e.g. "20:00"
    """
    try:
        import schedule
    except ImportError:
        log.error(
            "schedule library not installed.  Run:  pip install schedule\n"
            "Or use APScheduler mode (default):  python scheduler.py"
        )
        sys.exit(1)

    schedule.every().day.at(run_time).do(job)
    log.info("Simple scheduler started.  Job fires every day at %s (local time).", run_time)
    log.info("Press Ctrl+C to stop.")

    # Run immediately on startup
    log.info("Running initial analysis now …")
    job()

    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        log.info("Scheduler stopped.")


# ─── Mode 3 : one-shot run ────────────────────────────────────────────────────

def run_once():
    log.info("One-shot mode: running analysis immediately.")
    job()


# ─── CLI ──────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Nifty Option Chain Scheduler – runs analysis at 8 PM IST daily."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--simple",
        action="store_true",
        help="Use the lightweight `schedule` library instead of APScheduler.",
    )
    group.add_argument(
        "--once",
        action="store_true",
        help="Run the analysis once right now and exit (useful for testing).",
    )
    parser.add_argument(
        "--hour",
        type=int,
        default=20,
        help="Hour to run the job (24-h clock, local time).  Default: 20 (8 PM).",
    )
    parser.add_argument(
        "--minute",
        type=int,
        default=0,
        help="Minute to run the job.  Default: 0.",
    )
    parser.add_argument(
        "--timezone",
        default="Asia/Kolkata",
        help="Timezone for APScheduler (default: Asia/Kolkata i.e. IST).",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    log.info("Nifty Option Chain Scheduler")
    log.info("Scheduled time : %02d:%02d  (%s)", args.hour, args.minute, args.timezone)

    if args.once:
        run_once()
    elif args.simple:
        run_simple_schedule(f"{args.hour:02d}:{args.minute:02d}")
    else:
        run_apscheduler(args.hour, args.minute, args.timezone)


if __name__ == "__main__":
    main()
