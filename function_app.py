import logging

import azure.functions as func

from shared.pipeline import run_course_reports


app = func.FunctionApp()


@app.timer_trigger(
    schedule="%DISCUSSION_REPORT_SCHEDULE%",
    arg_name="timer",
    run_on_startup=False,
    use_monitor=True,
)
def main(timer: func.TimerRequest) -> None:
    if timer.past_due:
        logging.warning("The discussion engagement timer trigger is running late.")

    logging.info("Starting Canvas discussion engagement report job.")
    results = run_course_reports()
    logging.info("Completed Canvas discussion engagement report job for %s course(s).", len(results))
