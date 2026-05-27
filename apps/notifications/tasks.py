from celery import shared_task
from apps.notifications.models import Notification
import logging

logger = logging.getLogger(__name__)

@shared_task(name="notifications.deliver_notification")
def deliver_notification_task(notification_id):
    """
    Handles actual delivery of a notification via configured channels.
    """
    try:
        notification = Notification.objects.get(id=notification_id)
        logger.info(f"Delivering notification {notification_id} via {notification.channel}")
        
        if notification.channel == Notification.Channel.EMAIL:
            return deliver_email(notification)
        elif notification.channel == Notification.Channel.SLACK:
            return deliver_slack(notification)
        elif notification.channel == Notification.Channel.WEB:
            # Web notifications are usually handled via polling or WebSockets, 
            # so no active delivery needed here other than creating the record.
            return True
            
        return False
        
    except Notification.DoesNotExist:
        logger.error(f"Notification {notification_id} not found")
        return False

def deliver_email(notification):
    from django.core.mail import send_mail
    try:
        send_mail(
            notification.title,
            notification.message,
            None, # Default from
            [notification.user.email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send email notification: {str(e)}")
        return False

def deliver_slack(notification):
    # This would typically use a library like slack-sdk
    # For now, we'll log it as a placeholder
    logger.info(f"SLACK NOTIFICATION to {notification.user.email}: {notification.title}")
    return True

@shared_task(name="notifications.send_email")
def send_email_task(recipient_email, subject, template_name, context):
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string
    from django.utils.html import strip_tags
    
    html_content = render_to_string(template_name, context)
    text_content = strip_tags(html_content)
    
    msg = EmailMultiAlternatives(subject, text_content, None, [recipient_email])
    msg.attach_alternative(html_content, "text/html")
    msg.send()
    return True
