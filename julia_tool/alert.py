import html
from julia_tool.i18n import t, urgency_label
from julia_tool.models import Classification


def _esc(value) -> str:
    return html.escape(str(value), quote=True)


class Alerter:
    def __init__(self, graph, session, responsible_email: str, lang: str = "es"):
        self.graph = graph
        self.session = session
        self.to = responsible_email
        self.lang = lang

    def send_urgent(self, rfc: str, client_name: str, cls: Classification,
                    pdf: tuple[str, bytes] | None) -> str:
        lang = self.lang
        ulabel = urgency_label(cls.urgency, lang)
        subject = t("alert.urgent.subject", lang,
                    urgency=ulabel, rfc=rfc, act_type=cls.act_type)
        deadline = cls.deadline or t("value.deadline_none", lang)
        terminos = ", ".join(cls.matched) or "—"
        body = (
            f"<h2>{t('alert.urgent.heading', lang, urgency=ulabel)}</h2>"
            f"<p><b>{t('label.client', lang)}:</b> {_esc(client_name)} ({_esc(rfc)})</p>"
            f"<p><b>{t('label.act_type', lang)}:</b> {_esc(cls.act_type)}</p>"
            f"<p><b>{t('label.deadline', lang)}:</b> {_esc(deadline)}</p>"
            f"<p><b>{t('label.terms', lang)}:</b> {_esc(terminos)}</p>"
        )
        atts = [pdf] if pdf else None
        self.graph.send_mail(self.session, self.to, subject, body, atts)
        return subject

    def send_quarantine(self, msg_subject: str, from_address: str, reason: str) -> str:
        lang = self.lang
        subject = t("alert.quarantine.subject", lang, subject=msg_subject)
        body = (
            f"<h2>{t('alert.quarantine.heading', lang)}</h2>"
            f"<p><b>{t('label.sender', lang)}:</b> {_esc(from_address)}</p>"
            f"<p>{t('alert.quarantine.reason', lang, reason=_esc(reason))}</p>"
            f"<p>{t('alert.quarantine.note', lang)}</p>"
        )
        self.graph.send_mail(self.session, self.to, subject, body, None)
        return subject

    def send_unknown_client(self, msg_subject: str) -> str:
        lang = self.lang
        subject = t("alert.unknown.subject", lang, subject=msg_subject)
        body = (
            f"<h2>{t('alert.unknown.heading', lang)}</h2>"
            f"<p>{t('alert.unknown.body', lang)}</p>"
        )
        self.graph.send_mail(self.session, self.to, subject, body, None)
        return subject

    def send_fetch_failed(self, rfc: str, client_name: str, manual_url: str) -> str:
        lang = self.lang
        subject = t("alert.fetch_failed.subject", lang, rfc=rfc)
        url = _esc(manual_url)
        body = (
            f"<h2>{t('alert.fetch_failed.heading', lang)}</h2>"
            f"<p><b>{t('label.client', lang)}:</b> {_esc(client_name)} ({_esc(rfc)})</p>"
            f'<p>{t("alert.fetch_failed.link", lang)}: <a href="{url}">{url}</a></p>'
        )
        self.graph.send_mail(self.session, self.to, subject, body, None)
        return subject
