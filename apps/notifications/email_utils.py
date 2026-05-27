from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def send_notification_email(recipient_email, subject, template_name, context):
    """
    Renders an HTML email template and sends it to the recipient.
    """
    try:
        # Add common context like BASE_URL if needed
        context.setdefault('base_url', getattr(settings, 'FRONTEND_URL', 'http://localhost:3000'))
        
        html_content = render_to_string(template_name, context)
        text_content = strip_tags(html_content)

        msg = EmailMultiAlternatives(
            subject,
            text_content,
            settings.DEFAULT_FROM_EMAIL,
            [recipient_email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        logger.info(f"Email sent to {recipient_email} with subject: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {recipient_email}: {str(e)}")
        return False
