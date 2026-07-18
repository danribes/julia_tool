import html
from julia_tool.models import Classification


def _esc(value) -> str:
    return html.escape(str(value), quote=True)


class Alerter:
    def __init__(self, graph, session, responsible_email: str):
        self.graph = graph
        self.session = session
        self.to = responsible_email

    def send_urgent(self, rfc: str, client_name: str, cls: Classification,
                    pdf: tuple[str, bytes] | None) -> str:
        subject = f"[{cls.urgency}][{rfc}] {cls.act_type}"
        deadline = cls.deadline or "no detectado"
        terminos = ", ".join(cls.matched) or "—"
        body = (
            f"<h2>Notificacion SAT — {_esc(cls.urgency)}</h2>"
            f"<p><b>Cliente:</b> {_esc(client_name)} ({_esc(rfc)})</p>"
            f"<p><b>Tipo de acto:</b> {_esc(cls.act_type)}</p>"
            f"<p><b>Plazo:</b> {_esc(deadline)}</p>"
            f"<p><b>Terminos detectados:</b> {_esc(terminos)}</p>"
        )
        atts = [pdf] if pdf else None
        self.graph.send_mail(self.session, self.to, subject, body, atts)
        return subject

    def send_quarantine(self, msg_subject: str, from_address: str, reason: str) -> str:
        subject = f"[CUARENTENA] correo sospechoso: {msg_subject}"
        body = (
            "<h2>Correo bloqueado por verificacion anti-phishing</h2>"
            f"<p><b>Remitente:</b> {_esc(from_address)}</p>"
            f"<p><b>Motivo:</b> fallo de verificacion '{_esc(reason)}'</p>"
            "<p>No se accedio a ninguna credencial. Revise manualmente.</p>"
        )
        self.graph.send_mail(self.session, self.to, subject, body, None)
        return subject

    def send_unknown_client(self, msg_subject: str) -> str:
        subject = f"[SIN CLIENTE] notificacion sin RFC reconocido: {msg_subject}"
        body = (
            "<h2>Notificacion SAT sin cliente identificado</h2>"
            "<p>No se encontro un RFC registrado en el correo. Revise manualmente.</p>"
        )
        self.graph.send_mail(self.session, self.to, subject, body, None)
        return subject

    def send_fetch_failed(self, rfc: str, client_name: str, manual_url: str) -> str:
        subject = f"[FALLO DESCARGA][{rfc}] revision manual requerida"
        url = _esc(manual_url)
        body = (
            "<h2>No se pudo descargar el documento del portal SAT</h2>"
            f"<p><b>Cliente:</b> {_esc(client_name)} ({_esc(rfc)})</p>"
            f'<p>Ingrese manualmente al Buzon: <a href="{url}">{url}</a></p>'
        )
        self.graph.send_mail(self.session, self.to, subject, body, None)
        return subject
