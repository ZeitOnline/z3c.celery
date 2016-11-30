from celery import shared_task
import zope.security.management


@shared_task
def get_principal_title_task():
    """Task returning the principal's title used to run it."""
    interaction = zope.security.management.getInteraction()
    return interaction.participations[0].principal.title
