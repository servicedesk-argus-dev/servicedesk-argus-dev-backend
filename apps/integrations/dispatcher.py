import requests
import logging

logger = logging.getLogger(__name__)

def dispatch_to_webhook(url, payload):
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Webhook dispatch failed: {str(e)}")
        return False

def dispatch_to_slack(webhook_url, message):
    return dispatch_to_webhook(webhook_url, {"text": message})

def dispatch_to_teams(webhook_url, message):
    return dispatch_to_webhook(webhook_url, {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "type": "AdaptiveCard",
                "body": [{"type": "TextBlock", "text": message}],
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "version": "1.0"
            }
        }]
    })
