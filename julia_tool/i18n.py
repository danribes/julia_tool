DEFAULT_LANG = "es"
_LANGS = ("es", "en")

URGENCY_LABELS = {
    "es": {"URGENT": "URGENTE", "ATTENTION": "ATENCIÓN", "INFO": "INFO"},
    "en": {"URGENT": "URGENT", "ATTENTION": "ATTENTION", "INFO": "INFO"},
}

MESSAGES = {
    "es": {
        "alert.urgent.subject": "[{urgency}][{rfc}] {act_type}",
        "alert.urgent.heading": "Notificación SAT — {urgency}",
        "alert.quarantine.subject": "[CUARENTENA] correo sospechoso: {subject}",
        "alert.quarantine.heading": "Correo bloqueado por verificación anti-phishing",
        "alert.quarantine.reason": "Motivo: fallo de verificación '{reason}'",
        "alert.quarantine.note": "No se accedió a ninguna credencial. Revise manualmente.",
        "alert.unknown.subject": "[SIN CLIENTE] notificación sin RFC reconocido: {subject}",
        "alert.unknown.heading": "Notificación SAT sin cliente identificado",
        "alert.unknown.body": "No se encontró un RFC registrado en el correo. Revise manualmente.",
        "alert.fetch_failed.subject": "[FALLO DESCARGA][{rfc}] revisión manual requerida",
        "alert.fetch_failed.heading": "No se pudo descargar el documento del portal SAT",
        "alert.fetch_failed.link": "Ingrese manualmente al Buzón",
        "label.client": "Cliente",
        "label.act_type": "Tipo de acto",
        "label.deadline": "Plazo",
        "label.terms": "Términos detectados",
        "label.sender": "Remitente",
        "value.deadline_none": "no detectado",
        "prompt.master_password": "Contraseña maestra: ",
        "cli.added": "agregado {rfc}",
        "cli.removed": "eliminado",
        "cli.not_found": "no encontrado",
        "console.cycle_tally": "conteo del ciclo: {tally}",
        "ui.title": "Configuración de alertas — julia_tool",
        "ui.alert_words.label": "Palabras de alerta (separadas por comas)",
        "ui.alert_words.help": "El aviso del SAT se reenvía al responsable solo si aparece alguna de estas palabras. Vacío = reenviar todo.",
        "ui.recipient.label": "Correo del responsable de alertas",
        "ui.recipient.help": "Dirección que recibe los correos de alerta. Vacío = usar el de config.yaml.",
        "ui.save": "Guardar",
        "ui.saved": "Cambios guardados.",
        "ui.invalid_email": "Correo inválido; no se guardó el destinatario.",
        "ui.current": "Valores actuales",
        "ui.empty_note": "(sin palabras: se reenvía todo)",
        "ui.lang_toggle": "English",
    },
    "en": {
        "alert.urgent.subject": "[{urgency}][{rfc}] {act_type}",
        "alert.urgent.heading": "SAT notification — {urgency}",
        "alert.quarantine.subject": "[QUARANTINE] suspicious email: {subject}",
        "alert.quarantine.heading": "Email blocked by anti-phishing verification",
        "alert.quarantine.reason": "Reason: verification failure '{reason}'",
        "alert.quarantine.note": "No credentials were accessed. Review manually.",
        "alert.unknown.subject": "[NO CLIENT] notification with no recognized RFC: {subject}",
        "alert.unknown.heading": "SAT notification with no identified client",
        "alert.unknown.body": "No registered RFC was found in the email. Review manually.",
        "alert.fetch_failed.subject": "[DOWNLOAD FAILED][{rfc}] manual review required",
        "alert.fetch_failed.heading": "Could not download the document from the SAT portal",
        "alert.fetch_failed.link": "Log in manually to the Buzón",
        "label.client": "Client",
        "label.act_type": "Act type",
        "label.deadline": "Deadline",
        "label.terms": "Detected terms",
        "label.sender": "Sender",
        "value.deadline_none": "not detected",
        "prompt.master_password": "Master password: ",
        "cli.added": "added {rfc}",
        "cli.removed": "removed",
        "cli.not_found": "not found",
        "console.cycle_tally": "cycle tally: {tally}",
        "ui.title": "Alert settings — julia_tool",
        "ui.alert_words.label": "Alert words (comma-separated)",
        "ui.alert_words.help": "The SAT notice is forwarded to the responsible person only if one of these words appears. Empty = forward everything.",
        "ui.recipient.label": "Alert recipient email",
        "ui.recipient.help": "Address that receives the alert emails. Empty = use the one in config.yaml.",
        "ui.save": "Save",
        "ui.saved": "Changes saved.",
        "ui.invalid_email": "Invalid email; recipient not saved.",
        "ui.current": "Current values",
        "ui.empty_note": "(no words: everything is forwarded)",
        "ui.lang_toggle": "Español",
    },
}


def resolve_lang(value) -> str:
    if value is None:
        return DEFAULT_LANG
    v = str(value).strip().lower()
    return v if v in _LANGS else DEFAULT_LANG


def t(key: str, lang: str = DEFAULT_LANG, **kwargs) -> str:
    template = MESSAGES[resolve_lang(lang)][key]
    return template.format(**kwargs) if kwargs else template


def urgency_label(urgency: str, lang: str = DEFAULT_LANG) -> str:
    return URGENCY_LABELS[resolve_lang(lang)].get(urgency, urgency)
