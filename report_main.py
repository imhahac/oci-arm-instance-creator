from oracle_arm_manager.logger import setup_logging
from oracle_arm_manager.reporter import send_daily_report

def main() -> None:
    setup_logging()
    send_daily_report()

if __name__ == "__main__":
    main()
