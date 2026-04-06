"""
MercadoPago subscription management.

Uses the Preapproval API (no associated plan) to create monthly subscriptions
with a 7-day free trial. The payer enters their card once and MP auto-debits.
"""

import logging
import os
from datetime import datetime, timedelta

import mercadopago
import pytz

import db

logger = logging.getLogger(__name__)

_BA = pytz.timezone("America/Argentina/Buenos_Aires")

MP_ACCESS_TOKEN = os.environ.get("MP_ACCESS_TOKEN", "")
APP_URL = os.environ.get("APP_URL", "https://coachkai-production.up.railway.app")

# Monthly price in ARS — adjust as needed
SUBSCRIPTION_PRICE = float(os.environ.get("SUBSCRIPTION_PRICE", "9999.00"))

sdk = mercadopago.SDK(MP_ACCESS_TOKEN) if MP_ACCESS_TOKEN else None


def create_preapproval(telegram_id: int, payer_email: str) -> dict | None:
    """
    Create a MercadoPago preapproval (recurring subscription) with 7-day free trial.
    Returns the full MP response including init_point (checkout URL).
    """
    if not sdk:
        logger.error("[payments] MP_ACCESS_TOKEN not configured")
        return None

    now = datetime.now(_BA)
    start_date = (now + timedelta(days=7)).isoformat()

    preapproval_data = {
        "reason": "CoachKai - Plan Mensual",
        "external_reference": str(telegram_id),
        "payer_email": payer_email,
        "auto_recurring": {
            "frequency": 1,
            "frequency_type": "months",
            "transaction_amount": SUBSCRIPTION_PRICE,
            "currency_id": "ARS",
            "start_date": start_date,
            "end_date": (now + timedelta(days=365)).isoformat(),
        },
        "back_url": f"{APP_URL}/subscription/success?tid={telegram_id}",
        "status": "pending",
    }

    try:
        result = sdk.preapproval().create(preapproval_data)
        response = result.get("response", {})
        status_code = result.get("status")

        if status_code in (200, 201):
            mp_id = response.get("id", "")
            db.update_subscription(
                telegram_id,
                mp_preapproval_id=mp_id,
                mp_payer_email=payer_email,
            )
            logger.info(f"[payments] Preapproval created for tid={telegram_id}: {mp_id}")
            return response
        else:
            logger.error(f"[payments] MP preapproval error: status={status_code}, response={response}")
            return None
    except Exception as e:
        logger.error(f"[payments] Exception creating preapproval: {e}", exc_info=True)
        return None


def get_checkout_url(telegram_id: int, payer_email: str) -> str | None:
    """Create a preapproval and return the checkout URL (init_point)."""
    response = create_preapproval(telegram_id, payer_email)
    if response:
        return response.get("init_point")
    return None


def handle_webhook(data: dict) -> bool:
    """
    Process MercadoPago IPN webhook notification.
    Updates subscription status in DB based on preapproval state.
    Returns True if processed successfully.
    """
    if not sdk:
        return False

    topic = data.get("type") or data.get("topic", "")
    resource_id = data.get("data", {}).get("id") or data.get("id", "")

    if topic not in ("subscription_preapproval", "preapproval"):
        logger.debug(f"[payments] Ignoring webhook topic: {topic}")
        return False

    if not resource_id:
        logger.warning("[payments] Webhook missing resource id")
        return False

    try:
        result = sdk.preapproval().get(resource_id)
        response = result.get("response", {})
        mp_status = response.get("status", "")
        external_ref = response.get("external_reference", "")

        if not external_ref:
            logger.warning(f"[payments] No external_reference in preapproval {resource_id}")
            return False

        try:
            telegram_id = int(external_ref)
        except (ValueError, TypeError):
            logger.error(f"[payments] Invalid external_reference: {external_ref}")
            return False

        now_str = datetime.now(_BA).strftime("%Y-%m-%d %H:%M:%S")

        status_map = {
            "authorized": "active",
            "paused": "past_due",
            "cancelled": "cancelled",
            "pending": "trial",
        }
        new_status = status_map.get(mp_status)

        if new_status:
            update_kwargs = {"status": new_status, "mp_preapproval_id": resource_id}
            if new_status == "active":
                update_kwargs["current_period_start"] = now_str
                # Next billing ~30 days from now
                next_end = (datetime.now(_BA) + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
                update_kwargs["current_period_end"] = next_end
            db.update_subscription(telegram_id, **update_kwargs)
            logger.info(f"[payments] Subscription updated: tid={telegram_id}, mp_status={mp_status} -> {new_status}")
        else:
            logger.info(f"[payments] Unhandled MP status: {mp_status} for tid={telegram_id}")

        return True
    except Exception as e:
        logger.error(f"[payments] Webhook processing error: {e}", exc_info=True)
        return False


def check_preapproval_status(mp_preapproval_id: str) -> dict | None:
    """Query current status of a preapproval in MP (for manual verification)."""
    if not sdk or not mp_preapproval_id:
        return None
    try:
        result = sdk.preapproval().get(mp_preapproval_id)
        return result.get("response")
    except Exception as e:
        logger.error(f"[payments] Error checking preapproval: {e}")
        return None
