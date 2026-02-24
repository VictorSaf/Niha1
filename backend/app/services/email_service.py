import asyncio
import logging
import os
import re
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urlunparse

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..core.config import settings

logger = logging.getLogger(__name__)


def _strip_path(url: str) -> str:
    """Strip path from a URL, keeping only scheme://host:port."""
    parsed = urlparse(url.strip().rstrip("/"))
    return urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))


def _inline_css(html: str) -> str:
    """Inline <style> block CSS into element style= attributes for email client compatibility.

    Handles the subset of CSS used in _base.html (simple selectors: tag, .class, tag.class).
    Falls back to returning the original HTML if anything goes wrong.
    """
    try:
        # Extract <style> content
        style_match = re.search(r"<style[^>]*>(.*?)</style>", html, re.DOTALL)
        if not style_match:
            return html

        css_text = style_match.group(1)

        # Parse CSS rules into a list of (selector, declarations)
        rules: list[tuple[str, str]] = []
        for match in re.finditer(
            r"([^{]+)\{([^}]+)\}", css_text
        ):
            selector = match.group(1).strip()
            declarations = match.group(2).strip()
            # Skip @keyframes, @media, etc.
            if selector.startswith("@") or selector.startswith("*"):
                continue
            rules.append((selector, declarations))

        # Convert selectors to regex-based replacements on the HTML
        for selector, declarations in rules:
            decl = declarations.replace("\n", " ").strip().rstrip(";")

            # Compound selectors (e.g. ".callout.info .callout-title") — skip complex ones
            if " " in selector and "." in selector.split(" ", 1)[1]:
                # e.g. ".callout.info .callout-title" — too complex for simple inlining, skip
                pass

            # .parent .child (descendant)
            elif " " in selector:
                # Skip descendant selectors for simplicity
                pass

            # tag.class (e.g. "p.text-muted" or "div.logo")
            elif "." in selector and not selector.startswith("."):
                tag, cls = selector.split(".", 1)
                # Multi-class: .a.b
                classes = cls.split(".")
                pattern = rf'(<{tag}\b[^>]*class="[^"]*\b{re.escape(classes[0])}\b[^"]*"[^>]*)>'
                html = re.sub(
                    pattern,
                    lambda m: _merge_style(m.group(1), decl) + ">",
                    html,
                )

            # Multi-class selector (e.g. ".callout.success")
            elif selector.startswith(".") and "." in selector[1:]:
                classes = selector[1:].split(".")
                # Match elements that have ALL of these classes
                first_cls = classes[0]
                pattern = rf'(<[a-zA-Z][a-zA-Z0-9]*\b[^>]*class="[^"]*\b{re.escape(first_cls)}\b[^"]*"[^>]*)>'
                def _multi_class_replacer(m, cls_list=classes, d=decl):
                    tag_str = m.group(1)
                    cls_match = re.search(r'class="([^"]*)"', tag_str)
                    if cls_match:
                        tag_classes = cls_match.group(1).split()
                        if all(c in tag_classes for c in cls_list):
                            return _merge_style(tag_str, d) + ">"
                    return m.group(0)
                html = re.sub(pattern, _multi_class_replacer, html)

            # Single class (e.g. ".btn-primary")
            elif selector.startswith("."):
                cls = selector[1:]
                pattern = rf'(<[a-zA-Z][a-zA-Z0-9]*\b[^>]*class="[^"]*\b{re.escape(cls)}\b[^"]*"[^>]*)>'
                html = re.sub(
                    pattern,
                    lambda m, d=decl: _merge_style(m.group(1), d) + ">",
                    html,
                )

            # Tag selector (e.g. "body", "h1", "p")
            elif re.match(r"^[a-zA-Z][a-zA-Z0-9]*$", selector):
                pattern = rf"(<{selector}\b[^>]*)>"
                html = re.sub(
                    pattern,
                    lambda m, d=decl: _merge_style(m.group(1), d) + ">",
                    html,
                )

        return html
    except Exception:
        logger.debug("CSS inlining failed, returning original HTML", exc_info=True)
        return html


def _merge_style(tag_str: str, new_decl: str) -> str:
    """Merge new CSS declarations into an element's existing style attribute."""
    existing = re.search(r'style="([^"]*)"', tag_str)
    if existing:
        combined = existing.group(1).rstrip(";") + "; " + new_decl
        return re.sub(r'style="[^"]*"', f'style="{combined}"', tag_str)
    return tag_str + f' style="{new_decl}"'

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "templates", "emails")

# Sample data for admin preview — one entry per template
TEMPLATE_SAMPLE_DATA: Dict[str, Dict[str, Any]] = {
    "magic_link.html": {"magic_link_url": "https://app.nihaogroup.com/auth/verify?token=abc123"},
    "trade_confirmation.html": {
        "trade_type": "BUY",
        "certificate_type": "CEA",
        "quantity": "1,500.00",
        "price": "8.50",
        "total": "12,750.00",
    },
    "swap_match.html": {
        "from_type": "CEA",
        "to_type": "EUA",
        "quantity": "1,000",
        "to_quantity": "118",
        "rate": "0.1177",
    },
    "invitation.html": {"name": "John Doe", "setup_url": "https://app.nihaogroup.com/setup-password?token=abc123"},
    "account_approved.html": {"name": "John Doe"},
    "kyc_rejected.html": {"name": "John Doe", "reason": "Documents were not legible. Please re-upload."},
    "deposit_announced.html": {"name": "John Doe", "amount": "50,000.00", "currency": "EUR", "reference": "NIHA-DEP-20260101"},
    "deposit_on_hold.html": {"name": "John Doe", "amount": "50,000.00", "currency": "EUR", "hold_until": "2026-02-15"},
    "deposit_cleared.html": {"name": "John Doe", "amount": "50,000.00", "currency": "EUR"},
    "deposit_rejected.html": {
        "name": "John Doe",
        "amount": "50,000.00",
        "currency": "EUR",
        "reason": "Wire transfer not received within expected timeframe",
    },
    "account_funded.html": {"name": "John Doe"},
    "contact_followup.html": {"entity_name": "Acme Corp"},
    "settlement_created.html": {
        "name": "John Doe",
        "batch_reference": "STL-20260101-001",
        "certificate_type": "CEA",
        "quantity": "2,000.00",
        "expected_date": "2026-02-04",
    },
    "settlement_status_update.html": {
        "name": "John Doe",
        "batch_reference": "STL-20260101-001",
        "certificate_type": "CEA",
        "quantity": "2,000.00",
        "old_status": "Pending",
        "status_emoji": "\U0001F680",
        "status_color": "#3b82f6",
        "status_bg": "#dbeafe",
        "status_label": "Transfer Initiated",
    },
    "settlement_completed.html": {
        "name": "John Doe",
        "batch_reference": "STL-20260101-001",
        "certificate_type": "CEA",
        "quantity": "2,000.00",
        "new_balance": "5,000.00",
    },
    "settlement_failed.html": {
        "name": "John Doe",
        "batch_reference": "STL-20260101-001",
        "certificate_type": "CEA",
        "quantity": "2,000.00",
        "reason": "Registry timeout during transfer",
    },
    "admin_overdue_settlement.html": {
        "batch_reference": "STL-20260101-001",
        "entity_name": "Acme Corp",
        "certificate_type": "CEA",
        "quantity": "2,000.00",
        "expected_date": "2026-01-28",
        "days_overdue": 5,
        "current_status": "In Transit",
    },
    "withdrawal_requested.html": {"name": "John Doe", "amount": "10,000.00", "currency": "EUR"},
    "withdrawal_approved.html": {"name": "John Doe", "amount": "10,000.00", "currency": "EUR"},
    "withdrawal_completed.html": {"name": "John Doe", "amount": "10,000.00", "currency": "EUR", "wire_reference": "WIRE-2026-00123"},
    "withdrawal_rejected.html": {"name": "John Doe", "amount": "10,000.00", "currency": "EUR", "reason": "Insufficient verified funds"},
    "welcome_activated.html": {"name": "John Doe"},
    "aml_review_started.html": {"name": "John Doe", "amount": "50,000.00", "currency": "EUR"},
    "trading_activated.html": {"name": "John Doe", "amount": "50,000.00", "currency": "EUR"},
    "test_email.html": {"provider": "SMTP"},
    "introducer_nda_invitation.html": {
        "name": "Jane Smith",
        "setup_url": "https://app.nihaogroup.com/setup-password?token=abc123",
        "expiry_days": 14,
    },
    "introducer_approved.html": {
        "name": "Jane Smith",
        "dashboard_url": "https://app.nihaogroup.com/introducer/dashboard",
    },
    "referral_invitation.html": {
        "introducer_name": "Jane Smith",
        "invited_name": "John",
        "personal_note": "I think NIHA would be a great fit for your carbon compliance needs.",
        "invitation_url": "https://app.nihaogroup.com/contact?invite=abc123&ref=REF-JANE",
        "expiry_days": 7,
    },
}


def _fmt(value: float) -> str:
    """Format a number with commas and 2 decimals (e.g. 1,234.56)."""
    return f"{value:,.2f}"


class EmailService:
    """
    Email service using Resend API.
    Falls back to logging in development mode.
    """

    def __init__(self):
        self.api_key = settings.RESEND_API_KEY
        self.from_email = settings.FROM_EMAIL
        self.enabled = bool(self.api_key)
        self._jinja_env = Environment(
            loader=FileSystemLoader(TEMPLATE_DIR),
            autoescape=select_autoescape(["html"]),
        )

    def _render_template(self, template_name: str, **kwargs: Any) -> str:
        template = self._jinja_env.get_template(template_name)
        return template.render(**kwargs)

    def render_template(self, template_name: str, **kwargs: Any) -> str:
        """Public render for admin preview endpoint."""
        return self._render_template(template_name, **kwargs)

    def list_templates(self) -> List[str]:
        """Return available template filenames (excluding _base.html)."""
        templates = []
        if os.path.isdir(TEMPLATE_DIR):
            for f in sorted(os.listdir(TEMPLATE_DIR)):
                if f.endswith(".html") and not f.startswith("_"):
                    templates.append(f)
        return templates

    # ── send_* methods ─────────────────────────────────────────────

    async def send_magic_link(self, to_email: str, token: str) -> bool:
        """Send magic link authentication email"""
        magic_link_url = f"http://localhost:5173/auth/verify?token={token}"
        subject = "Sign in to Nihao Carbon Trading Platform"
        html = self._render_template("magic_link.html", magic_link_url=magic_link_url)
        return await self._send_email(to_email, subject, html)

    async def send_trade_confirmation(
        self,
        to_email: str,
        trade_type: str,
        certificate_type: str,
        quantity: float,
        price: float,
        total: float,
    ) -> bool:
        """Send trade confirmation email"""
        subject = f"Trade Confirmation - {trade_type.upper()} {quantity} {certificate_type}"
        html = self._render_template(
            "trade_confirmation.html",
            trade_type=trade_type.upper(),
            certificate_type=certificate_type,
            quantity=_fmt(quantity),
            price=_fmt(price),
            total=_fmt(total),
        )
        return await self._send_email(to_email, subject, html)

    async def send_swap_match_notification(
        self, to_email: str, from_type: str, to_type: str, quantity: float, rate: float
    ) -> bool:
        """Send swap match notification"""
        subject = f"Swap Match Found - {from_type} to {to_type}"
        html = self._render_template(
            "swap_match.html",
            from_type=from_type,
            to_type=to_type,
            quantity=f"{quantity:,.0f}",
            to_quantity=f"{quantity * rate:,.0f}",
            rate=f"{rate:.2f}",
        )
        return await self._send_email(to_email, subject, html)

    async def send_invitation(
        self,
        to_email: str,
        first_name: str,
        invitation_token: str,
        mail_config: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Send invitation email to new user with password setup link.

        When mail_config is provided (from DB), use its from_email, subject,
        body, link base URL. Otherwise use env and hardcoded template.
        """
        name = first_name or "there"
        if mail_config:
            raw = (mail_config.get("invitation_link_base_url") or "").strip()
            base_url = _strip_path(raw) if raw else "http://localhost:5173"
            setup_url = f"{base_url}/setup-password?token={invitation_token}"
            subject = (
                mail_config.get("invitation_subject")
                or "Welcome to Nihao Carbon Trading Platform"
            )
            body_html = mail_config.get("invitation_body_html")
            if body_html:
                # DB custom body — use simple string replacement (legacy)
                html_content = body_html.replace("{{setup_url}}", setup_url).replace(
                    "{{first_name}}", name
                )
            else:
                html_content = self._render_template("invitation.html", name=name, setup_url=setup_url)
            from_email = mail_config.get("from_email") or settings.FROM_EMAIL
            return await self._send_email(
                to_email, subject, html_content, from_email=from_email, mail_config=mail_config,
            )
        setup_url = f"http://localhost:5173/setup-password?token={invitation_token}"
        subject = "Welcome to Nihao Carbon Trading Platform"
        html = self._render_template("invitation.html", name=name, setup_url=setup_url)
        return await self._send_email(to_email, subject, html)

    async def send_introducer_nda_invitation(
        self,
        to_email: str,
        first_name: str,
        invitation_token: str,
        nda_pdf_path: str,
        expiry_days: int = 14,
        mail_config: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Send NDA invitation email with attached PDF to introducer."""
        name = first_name or "there"
        raw = (mail_config or {}).get("invitation_link_base_url", "") or ""
        base_url = _strip_path(raw.strip()) if raw.strip() else "http://localhost:5173"
        setup_url = f"{base_url}/setup-password?token={invitation_token}"
        subject = "Introducer Programme - NDA & Account Setup - Nihao Group"
        html = self._render_template(
            "introducer_nda_invitation.html",
            name=name, setup_url=setup_url, expiry_days=expiry_days,
        )
        attachments = None
        try:
            with open(nda_pdf_path, "rb") as f:
                attachments = [{"filename": "Nihao_Group_NDA.pdf", "content": f.read()}]
        except FileNotFoundError:
            logger.error(f"NDA PDF not found at {nda_pdf_path}")
        return await self._send_email(
            to_email, subject, html, mail_config=mail_config, attachments=attachments,
        )

    async def send_troducer_welcome(
        self, to_email: str, first_name: str = "",
        mail_config: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Send welcome email when a TRODUCER account is created by admin with a password."""
        name = first_name or "there"
        raw = (mail_config or {}).get("invitation_link_base_url", "") or ""
        base_url = _strip_path(raw.strip()) if raw.strip() else "http://localhost:5173"
        login_url = f"{base_url}/login"
        subject = "Your Troducer Account is Ready - Nihao Group"
        html = self._render_template("troducer_welcome.html", name=name, login_url=login_url)
        return await self._send_email(to_email, subject, html, mail_config=mail_config)

    async def send_introducer_approved(
        self, to_email: str, first_name: str = "",
        mail_config: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Send confirmation email when introducer NDA is approved."""
        name = first_name or "there"
        raw = (mail_config or {}).get("invitation_link_base_url", "") or ""
        base_url = _strip_path(raw.strip()) if raw.strip() else "http://localhost:5173"
        dashboard_url = f"{base_url}/introducer/dashboard"
        subject = "NDA Approved - Welcome to the Introducer Programme - Nihao Group"
        html = self._render_template(
            "introducer_approved.html", name=name, dashboard_url=dashboard_url,
        )
        return await self._send_email(to_email, subject, html, mail_config=mail_config)

    async def send_pre_nda_invitation(
        self,
        to_email: str,
        first_name: str,
        invitation_token: str,
        nda_pdf_path: str,
        expiry_days: int = 14,
        mail_config: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Send NDA invitation email with attached PDF to a PRE_NDA buyer."""
        name = first_name or "there"
        raw = (mail_config or {}).get("invitation_link_base_url", "") or ""
        base_url = _strip_path(raw.strip()) if raw.strip() else "http://localhost:5173"
        setup_url = f"{base_url}/setup-password?token={invitation_token}"
        subject = "Complete Your Registration - NDA Required - Nihao Group"
        html = self._render_template(
            "pre_nda_invitation.html",
            name=name, setup_url=setup_url, expiry_days=expiry_days,
        )
        attachments = None
        try:
            with open(nda_pdf_path, "rb") as f:
                attachments = [{"filename": "Nihao_Group_NDA.pdf", "content": f.read()}]
        except FileNotFoundError:
            logger.error(f"NDA PDF not found at {nda_pdf_path}")
        return await self._send_email(
            to_email, subject, html, mail_config=mail_config, attachments=attachments,
        )

    async def send_pre_nda_approved(
        self, to_email: str, first_name: str = "",
        mail_config: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Send confirmation email when a PRE_NDA buyer's NDA is approved."""
        name = first_name or "there"
        raw = (mail_config or {}).get("invitation_link_base_url", "") or ""
        base_url = _strip_path(raw.strip()) if raw.strip() else "http://localhost:5173"
        login_url = f"{base_url}/login"
        subject = "NDA Approved - Welcome to Nihao Group"
        html = self._render_template(
            "pre_nda_approved.html", name=name, login_url=login_url,
        )
        return await self._send_email(to_email, subject, html, mail_config=mail_config)

    async def send_referral_invitation(
        self,
        to_email: str,
        introducer_name: str,
        invited_first_name: str | None,
        personal_note: str | None,
        invitation_url: str,
        expiry_days: int = 7,
        mail_config: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Send referral invitation email from an introducer to a potential client."""
        context = {
            "introducer_name": introducer_name,
            "invited_name": invited_first_name or "there",
            "personal_note": personal_note,
            "invitation_url": invitation_url,
            "expiry_days": expiry_days,
        }
        subject = f"{introducer_name} invited you to NIHA — Carbon Credit Trading Platform"
        html = self._render_template("referral_invitation.html", **context)
        return await self._send_email(to_email, subject, html, mail_config=mail_config)

    async def send_account_approved(self, to_email: str, first_name: str) -> bool:
        """Send email when user account is approved"""
        name = first_name or "there"
        subject = "Your account has been verified - Nihao Group"
        html = self._render_template("account_approved.html", name=name)
        return await self._send_email(to_email, subject, html)

    async def send_kyc_rejected(
        self, to_email: str, first_name: str, reason: str = ""
    ) -> bool:
        """Notify user their KYC application was rejected."""
        name = first_name or "there"
        subject = "Account Verification Update - Nihao Group"
        html = self._render_template("kyc_rejected.html", name=name, reason=reason)
        return await self._send_email(to_email, subject, html)

    async def send_deposit_announced(
        self, to_email: str, first_name: str, amount: float, currency: str, reference: str
    ) -> bool:
        """Confirm deposit announcement receipt to user."""
        name = first_name or "there"
        subject = f"Deposit Received - {currency} {_fmt(amount)} - Nihao Group"
        html = self._render_template(
            "deposit_announced.html",
            name=name, amount=_fmt(amount), currency=currency, reference=reference,
        )
        return await self._send_email(to_email, subject, html)

    async def send_deposit_on_hold(
        self, to_email: str, first_name: str, amount: float, currency: str, hold_until: str
    ) -> bool:
        """Notify user their deposit is on AML compliance hold."""
        name = first_name or "there"
        subject = "Deposit Under Review - Nihao Group"
        html = self._render_template(
            "deposit_on_hold.html",
            name=name, amount=_fmt(amount), currency=currency, hold_until=hold_until,
        )
        return await self._send_email(to_email, subject, html)

    async def send_deposit_cleared(
        self, to_email: str, first_name: str, amount: float, currency: str
    ) -> bool:
        """Notify user their deposit cleared AML and funds are available."""
        name = first_name or "there"
        subject = f"Funds Available - {currency} {_fmt(amount)} Cleared - Nihao Group"
        html = self._render_template(
            "deposit_cleared.html", name=name, amount=_fmt(amount), currency=currency,
        )
        return await self._send_email(to_email, subject, html)

    async def send_deposit_rejected(
        self, to_email: str, first_name: str, amount: float, currency: str, reason: str
    ) -> bool:
        """Notify user their deposit was rejected."""
        name = first_name or "there"
        reason_map = {
            "WIRE_NOT_RECEIVED": "Wire transfer not received within expected timeframe",
            "AMOUNT_MISMATCH": "Deposit amount does not match the announced amount",
            "SOURCE_VERIFICATION_FAILED": "Unable to verify the source of funds",
            "AML_FLAG": "Additional compliance documentation required",
            "SANCTIONS_HIT": "Unable to process due to regulatory restrictions",
            "SUSPICIOUS_ACTIVITY": "Additional verification required",
            "OTHER": "Please contact support for details",
        }
        display_reason = reason_map.get(reason, reason or "Please contact support for details")
        subject = "Deposit Update - Action Required - Nihao Group"
        html = self._render_template(
            "deposit_rejected.html",
            name=name, amount=_fmt(amount), currency=currency, reason=display_reason,
        )
        return await self._send_email(to_email, subject, html)

    async def send_account_funded(self, to_email: str, first_name: str) -> bool:
        """Send email when user account is funded and ready for trading"""
        name = first_name or "there"
        subject = "Your account is now active - Start Trading!"
        html = self._render_template("account_funded.html", name=name)
        return await self._send_email(to_email, subject, html)

    async def send_contact_followup(self, to_email: str, entity_name: str) -> bool:
        """Send follow-up email after contact request"""
        subject = "Thank you for your interest - Nihao Group"
        html = self._render_template("contact_followup.html", entity_name=entity_name)
        return await self._send_email(to_email, subject, html)

    async def send_settlement_created(
        self,
        to_email: str,
        first_name: str,
        batch_reference: str,
        certificate_type: str,
        quantity: float,
        expected_date: str,
    ) -> bool:
        """Send settlement created confirmation email"""
        name = first_name or "there"
        subject = f"Settlement Initiated - {batch_reference}"
        html = self._render_template(
            "settlement_created.html",
            name=name, batch_reference=batch_reference,
            certificate_type=certificate_type, quantity=_fmt(quantity),
            expected_date=expected_date,
        )
        return await self._send_email(to_email, subject, html)

    async def send_settlement_status_update(
        self,
        to_email: str,
        first_name: str,
        batch_reference: str,
        old_status: str,
        new_status: str,
        certificate_type: str,
        quantity: float,
    ) -> bool:
        """Send settlement status update email"""
        name = first_name or "there"

        status_config = {
            "TRANSFER_INITIATED": {"emoji": "\U0001F680", "color": "#3b82f6", "bg": "#dbeafe", "label": "Transfer Initiated"},
            "IN_TRANSIT": {"emoji": "\U0001F504", "color": "#8b5cf6", "bg": "#ede9fe", "label": "In Transit"},
            "AT_CUSTODY": {"emoji": "\U0001F3E6", "color": "#06b6d4", "bg": "#cffafe", "label": "At Custody"},
            "SETTLED": {"emoji": "\u2705", "color": "#10b981", "bg": "#d1fae5", "label": "Settled"},
            "FAILED": {"emoji": "\u274C", "color": "#ef4444", "bg": "#fee2e2", "label": "Failed"},
        }
        config = status_config.get(
            new_status,
            {"emoji": "\u23F1\uFE0F", "color": "#f59e0b", "bg": "#fef3c7", "label": new_status},
        )

        subject = f"Settlement Update - {batch_reference} is now {config['label']}"
        html = self._render_template(
            "settlement_status_update.html",
            name=name, batch_reference=batch_reference,
            certificate_type=certificate_type, quantity=_fmt(quantity),
            old_status=old_status.replace("_", " ").title(),
            status_emoji=config["emoji"], status_color=config["color"],
            status_bg=config["bg"], status_label=config["label"],
        )
        return await self._send_email(to_email, subject, html)

    async def send_settlement_completed(
        self,
        to_email: str,
        first_name: str,
        batch_reference: str,
        certificate_type: str,
        quantity: float,
        new_balance: float,
    ) -> bool:
        """Send settlement completion email"""
        name = first_name or "there"
        subject = f"Settlement Complete - {_fmt(quantity)} {certificate_type} Delivered"
        html = self._render_template(
            "settlement_completed.html",
            name=name, batch_reference=batch_reference,
            certificate_type=certificate_type, quantity=_fmt(quantity),
            new_balance=_fmt(new_balance),
        )
        return await self._send_email(to_email, subject, html)

    async def send_settlement_failed(
        self,
        to_email: str,
        first_name: str,
        batch_reference: str,
        certificate_type: str,
        quantity: float,
        reason: Optional[str] = None,
    ) -> bool:
        """Send settlement failure notification email"""
        name = first_name or "there"
        subject = f"Settlement Failed - {batch_reference}"
        html = self._render_template(
            "settlement_failed.html",
            name=name, batch_reference=batch_reference,
            certificate_type=certificate_type, quantity=_fmt(quantity),
            reason=reason or "Technical issue during settlement processing",
        )
        return await self._send_email(to_email, subject, html)

    async def send_admin_overdue_settlement_alert(
        self,
        to_email: str,
        batch_reference: str,
        entity_name: str,
        certificate_type: str,
        quantity: float,
        expected_date: str,
        days_overdue: int,
        current_status: str,
    ) -> bool:
        """Send admin alert for overdue settlement"""
        subject = f"\u26A0\uFE0F ALERT: Settlement {batch_reference} is {days_overdue} days overdue"
        html = self._render_template(
            "admin_overdue_settlement.html",
            batch_reference=batch_reference, entity_name=entity_name,
            certificate_type=certificate_type, quantity=_fmt(quantity),
            expected_date=expected_date, days_overdue=days_overdue,
            current_status=current_status.replace("_", " ").title(),
        )
        return await self._send_email(to_email, subject, html)

    async def send_withdrawal_requested(
        self, to_email: str, first_name: str, amount: float, currency: str = "EUR"
    ) -> bool:
        """Confirm withdrawal request receipt to user."""
        name = first_name or "there"
        subject = f"Withdrawal Request Received - {currency} {_fmt(amount)} - Nihao Group"
        html = self._render_template(
            "withdrawal_requested.html", name=name, amount=_fmt(amount), currency=currency,
        )
        return await self._send_email(to_email, subject, html)

    async def send_withdrawal_approved(
        self, to_email: str, first_name: str, amount: float, currency: str = "EUR"
    ) -> bool:
        """Notify user their withdrawal was approved and is being processed."""
        name = first_name or "there"
        subject = f"Withdrawal Approved - {currency} {_fmt(amount)} - Nihao Group"
        html = self._render_template(
            "withdrawal_approved.html", name=name, amount=_fmt(amount), currency=currency,
        )
        return await self._send_email(to_email, subject, html)

    async def send_withdrawal_completed(
        self, to_email: str, first_name: str, amount: float, currency: str = "EUR",
        wire_reference: str = ""
    ) -> bool:
        """Notify user their withdrawal wire transfer has been sent."""
        name = first_name or "there"
        subject = f"Funds Transferred - {currency} {_fmt(amount)} - Nihao Group"
        html = self._render_template(
            "withdrawal_completed.html",
            name=name, amount=_fmt(amount), currency=currency,
            wire_reference=wire_reference or "See your bank statement",
        )
        return await self._send_email(to_email, subject, html)

    async def send_withdrawal_rejected(
        self, to_email: str, first_name: str, amount: float, currency: str = "EUR",
        reason: str = ""
    ) -> bool:
        """Notify user their withdrawal was rejected and funds refunded to balance."""
        name = first_name or "there"
        subject = "Withdrawal Update - Nihao Group"
        html = self._render_template(
            "withdrawal_rejected.html",
            name=name, amount=_fmt(amount), currency=currency,
            reason=reason or "Please contact support for details",
        )
        return await self._send_email(to_email, subject, html)

    async def send_welcome_activated(self, to_email: str, first_name: str = "", role: str = "") -> bool:
        """Welcome email sent after user sets their password from invitation."""
        name = first_name or "there"
        subject = "Welcome to Nihao Group - Account Activated"
        mail_config = await self._get_db_mail_config()
        raw = (mail_config or {}).get("invitation_link_base_url", "") or ""
        base_url = _strip_path(raw.strip()) if raw.strip() else "http://localhost:5173"
        if role in ("INTRODUCER", "PREINTRODUCER", "TRODUCER"):
            dashboard_url = f"{base_url}/introducer/dashboard"
        else:
            dashboard_url = f"{base_url}/dashboard"
        html = self._render_template("welcome_activated.html", name=name, dashboard_url=dashboard_url)
        return await self._send_email(to_email, subject, html, mail_config=mail_config)

    async def send_aml_review_started(
        self, to_email: str, first_name: str = "", amount: float = 0, currency: str = "EUR"
    ) -> bool:
        """Notify user that their deposit is under AML review (FUNDING -> AML)."""
        name = first_name or "there"
        subject = "Deposit Under Review - Nihao Group"
        html = self._render_template(
            "aml_review_started.html", name=name, amount=_fmt(amount), currency=currency,
        )
        return await self._send_email(to_email, subject, html)

    async def send_trading_activated(
        self, to_email: str, first_name: str = "", amount: float = 0, currency: str = "EUR"
    ) -> bool:
        """Notify user that AML cleared and they can now trade on CEA market (AML -> CEA)."""
        name = first_name or "there"
        subject = "Account Activated for Trading - Nihao Group"
        html = self._render_template(
            "trading_activated.html", name=name, amount=_fmt(amount), currency=currency,
        )
        return await self._send_email(to_email, subject, html)

    async def send_cea_settlement_pending(self, to_email: str, first_name: str = "") -> bool:
        """Notify user that CEA settlement is in progress (CEA -> CEA_SETTLE)."""
        name = first_name or "there"
        subject = "CEA Settlement in Progress - Nihao Group"
        html = self._render_template("cea_settlement_pending.html", name=name)
        return await self._send_email(to_email, subject, html)

    async def send_swap_access_granted(self, to_email: str, first_name: str = "") -> bool:
        """Notify user that swap market is unlocked (CEA_SETTLE -> SWAP)."""
        name = first_name or "there"
        subject = "Swap Market Unlocked - Nihao Group"
        html = self._render_template("swap_access_granted.html", name=name)
        return await self._send_email(to_email, subject, html)

    async def send_eua_settlement_pending(self, to_email: str, first_name: str = "") -> bool:
        """Notify user that EUA settlement is in progress (SWAP -> EUA_SETTLE)."""
        name = first_name or "there"
        subject = "EUA Settlement in Progress - Nihao Group"
        html = self._render_template("eua_settlement_pending.html", name=name)
        return await self._send_email(to_email, subject, html)

    async def send_eua_access_granted(self, to_email: str, first_name: str = "") -> bool:
        """Notify user that full access is activated (EUA_SETTLE -> EUA)."""
        name = first_name or "there"
        subject = "Full Access Activated - Nihao Group"
        html = self._render_template("eua_access_granted.html", name=name)
        return await self._send_email(to_email, subject, html)

    async def send_test_email(
        self, to_email: str, mail_config: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send a test email to verify mail configuration."""
        subject = "Test Email - Nihao Group Mail Configuration"
        provider = (mail_config.get("provider", "env") if mail_config else "env")
        html = self._render_template("test_email.html", provider=provider)
        return await self._send_email(to_email, subject, html, mail_config=mail_config)

    # ── internal plumbing (unchanged) ──────────────────────────────

    async def _get_db_mail_config(self) -> Optional[Dict[str, Any]]:
        """Load current mail config from DB. Returns None if not configured."""
        try:
            from sqlalchemy import select

            from ..core.database import AsyncSessionLocal
            from ..models.models import MailConfig, MailProvider

            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(MailConfig).order_by(MailConfig.updated_at.desc()).limit(1)
                )
                row = result.scalar_one_or_none()
                if not row:
                    return None
                return {
                    "provider": row.provider.value,
                    "use_env_credentials": row.use_env_credentials,
                    "from_email": row.from_email,
                    "resend_api_key": (
                        row.resend_api_key
                        if not row.use_env_credentials
                        and row.provider == MailProvider.RESEND
                        else None
                    ),
                    "smtp_host": row.smtp_host,
                    "smtp_port": row.smtp_port,
                    "smtp_use_tls": row.smtp_use_tls,
                    "smtp_username": row.smtp_username,
                    "smtp_password": row.smtp_password,
                }
        except Exception:
            logger.debug("Could not load mail config from DB, using env defaults")
            return None

    async def _send_email(
        self,
        to: str,
        subject: str,
        html: str,
        from_email: Optional[str] = None,
        mail_config: Optional[Dict[str, Any]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """Send email via Resend, SMTP (from config), or log in dev mode.

        attachments: list of {"filename": str, "content": bytes}
        """
        # Inline CSS for email client compatibility (Gmail etc. strip <style> tags)
        html = _inline_css(html)

        # Auto-load DB mail config if none provided
        if mail_config is None:
            mail_config = await self._get_db_mail_config()

        from_addr = from_email or (mail_config or {}).get("from_email") or self.from_email

        if mail_config and mail_config.get("provider") == "smtp":
            return await self._send_via_smtp(to, subject, html, from_addr, mail_config, attachments)

        api_key = self.api_key
        if mail_config and mail_config.get("provider") == "resend":
            use_env = mail_config.get("use_env_credentials")
            has_key = mail_config.get("resend_api_key")
            if not use_env and has_key:
                api_key = mail_config["resend_api_key"]
            else:
                api_key = settings.RESEND_API_KEY

        if not api_key:
            logger.info(f"[DEV MODE] Email would be sent to {to}")
            return True

        try:
            import resend

            resend.api_key = api_key
            params: Dict[str, Any] = {
                "from": from_addr,
                "to": [to],
                "subject": subject,
                "html": html,
            }
            if attachments:
                import base64

                params["attachments"] = [
                    {"filename": a["filename"], "content": base64.b64encode(a["content"]).decode()}
                    for a in attachments
                ]
            resend.Emails.send(params)
            logger.info(f"Email sent successfully to {to}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    async def _send_via_smtp(
        self,
        to: str,
        subject: str,
        html: str,
        from_addr: str,
        mail_config: Dict[str, Any],
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """Send email via SMTP using config. Runs sync smtplib in thread."""
        host = mail_config.get("smtp_host") or "localhost"
        port = mail_config.get("smtp_port") or 587
        use_tls = mail_config.get("smtp_use_tls", True)
        username = mail_config.get("smtp_username")
        password = mail_config.get("smtp_password")

        def _do_send() -> None:
            msg = MIMEMultipart("mixed")
            msg["Subject"] = subject
            msg["From"] = from_addr
            msg["To"] = to
            msg.attach(MIMEText(html, "html"))
            if attachments:
                for att in attachments:
                    part = MIMEApplication(att["content"], Name=att["filename"])
                    part["Content-Disposition"] = f'attachment; filename="{att["filename"]}"'
                    msg.attach(part)
            if use_tls:
                with smtplib.SMTP(host, port) as server:
                    server.starttls()
                    if username and password:
                        server.login(username, password)
                    server.sendmail(from_addr, [to], msg.as_string())
            else:
                with smtplib.SMTP(host, port) as server:
                    if username and password:
                        server.login(username, password)
                    server.sendmail(from_addr, [to], msg.as_string())

        try:
            await asyncio.to_thread(_do_send)
            logger.info(f"Email sent via SMTP to {to}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email via SMTP: {e}")
            return False


email_service = EmailService()
