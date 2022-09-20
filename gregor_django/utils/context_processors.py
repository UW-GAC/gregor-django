from django.conf import settings


def settings_context(_request):
    """Settings available by default to the templates context."""
    # Note: we intentionally do NOT expose the entire settings
    # to prevent accidental leaking of sensitive information
    return {
        "LIVE_SITE": settings.LIVE_SITE,
        "DEBUG": settings.DEBUG,
        "DRUPAL_SITE_URL": settings.DRUPAL_SITE_URL,
        "DCC_CONTACT_EMAIL": settings.DCC_CONTACT_EMAIL,
    }
