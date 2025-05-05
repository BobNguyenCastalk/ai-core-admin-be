from datetime import date

MEDIA_MAX_WIDTH = 1920
MEDIA_MAX_HEIGHT = 1080

def is_date_in_future(given_date):
    """Return true when the date is in the future."""
    return given_date > date.today()
