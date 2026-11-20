> 🌐 [English](README.md) | Español

# julia_tool — vigilante del Buzón Tributario del SAT

`julia_tool` es un vigilante desatendido para un despacho contable mexicano que
supervisa las obligaciones fiscales de muchos clientes. El SAT (Servicio de
Administración Tributaria) envía correos de notificación del Buzón Tributario a un
único buzón compartido de Microsoft 365; el correo en sí es solo un aviso, nunca el
documento real. La herramienta consulta ese buzón mediante Microsoft Graph, verifica
que cada mensaje provenga genuinamente del SAT (alineación de dominio SPF/DKIM/DMARC,
no solo un SPF exitoso) antes de confiar en él, extrae el RFC (identificación fiscal)
del cliente a partir del mensaje, inicia sesión en el portal del Buzón Tributario del
SAT con las credenciales almacenadas de ese cliente (e.firma o CIEC) para descargar el
PDF real de la notificación, clasifica su urgencia (requerimiento, multa, sanción,
embargo, …) a partir del texto del PDF, y envía por correo una alerta con el PDF
adjunto a la persona responsable fija del despacho. Cada paso —verificación del
remitente, uso de credenciales y alerta— queda registrado, y ningún mensaje se
descarta jamás en silencio: cada uno termina en exactamente uno de estos resultados:
alert-sent, not-forwarded, quarantined, unknown-client, fetch-failed o
skipped-duplicate.

## Requisito legal / operativo

Antes de que esta herramienta se dirija a las credenciales del SAT de cualquier
cliente, **el despacho debe contar con una autorización firmada (carta responsiva) de
ese cliente** que otorgue al despacho la custodia de su e.firma (.cer/.key +
contraseña) o de sus credenciales CIEC (Contraseña) para este fin. No agregue un
cliente al almacén cifrado (`client add`, más abajo) sin tener esa autorización firmada
en archivo. Este es un requisito legal, no técnico —la herramienta no lo verifica.

## Instalación

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .[dev]
playwright install chromium
```

Requiere Python 3.12+. `playwright install chromium` descarga el binario del navegador
que utiliza la automatización del portal del Buzón; sin él, `_fetch_efirma`/`_fetch_ciec`
(una vez completados —vea "Estado actual" más abajo) y la lista de verificación de
`docs/manual-validation.md` no pueden ejecutarse.

## Registro de la aplicación en Azure / Entra

La herramienta se autentica ante Microsoft Graph como el *operador*, no como una
identidad de aplicación —de este modo solo puede hacer lo que el operador que inició
sesión ya tiene permitido hacer en el buzón compartido, y cada token queda ligado a una
persona real.

1. En el [Portal de Azure](https://portal.azure.com) → **Microsoft Entra ID** →
   **App registrations** → **New registration**.
   - Supported account types: single tenant (cuentas solo en este directorio
     organizacional), a menos que la configuración del tenant del despacho requiera
     otra cosa.
   - Deje el redirect URI en blanco por ahora —el flujo de código de dispositivo no
     utiliza uno.
2. En **Authentication**, habilite **"Allow public client flows"** → configúrelo en
   **Yes**, y guarde. Esto registra la aplicación como un *cliente público* (no se
   almacena ni se usa ningún client secret —`GraphClient` solo envía `client_id` +
   `tenant_id`, vea `julia_tool/graph_client.py`).
3. En **API permissions** → **Add a permission** → **Microsoft Graph** →
   **Delegated permissions**, agregue:
   - `Mail.Read.Shared`
   - `Mail.Send.Shared`
   Haga clic en **Grant admin consent** para el tenant (ambos son permisos delegados,
   pero un administrador del tenant típicamente aún necesita otorgar su consentimiento
   una vez para la organización).
4. Anote el **Application (client) ID** y el **Directory (tenant) ID** de la página
   Overview del registro.
5. **Acceso delegado al buzón compartido**: dado que se trata de permisos `.Shared`,
   la *cuenta de correo propia del operador* —la persona que ejecuta `julia_tool` y
   completa el inicio de sesión con código de dispositivo— debe tener, por separado,
   los derechos delegados **Full Access** y **Send As** (o **Send on Behalf**) sobre el
   buzón compartido de la oficina (`mailbox:` en `config.yaml`). Otorgue esto en el
   Exchange admin center / `Add-MailboxPermission` + `Add-RecipientPermission` (o en la
   configuración de delegados de buzón compartido del centro de administración de
   Microsoft 365) —el registro de la aplicación por sí solo no otorga acceso al buzón.
6. Coloque los dos IDs en `config.yaml`:
   ```yaml
   tenant_id: "<Directory (tenant) ID>"
   client_id: "<Application (client) ID>"
   ```

La primera ejecución (`python -m julia_tool.main`, sin token en caché) imprime un
código de `https://microsoft.com/devicelogin` —el operador abre esa URL, ingresa el
código e inicia sesión interactivamente una sola vez; después de eso, la caché de
tokens de MSAL (`.token_cache.bin`, ya excluida en git) mantiene la sesión en
silencio.

## Configuración

```bash
cp config.example.yaml config.yaml
```

Luego edite `config.yaml`:
- `mailbox`: la dirección del buzón compartido de la oficina que recibe los avisos del
  SAT.
- `responsible_email`: la persona fija que recibe cada alerta.
- `tenant_id` / `client_id`: del registro de la aplicación en Azure, arriba.
- `portal.*`: URLs del portal del SAT y selectores CSS —vea
  `docs/manual-validation.md` para saber cómo se confirman en sitio.
- `keyword_map`: **opcional**. Omítalo por completo para usar las reglas de palabras
  clave de urgencia en español integradas (`julia_tool/classify.py:DEFAULT_KEYWORDS`);
  configúrelo solo para sobrescribir esos valores predeterminados.
- `language`: **opcional**, `es` | `en` —el idioma usado para la salida en consola, la
  CLI de `client` y los correos de alerta. El valor predeterminado es `es`; un valor
  inválido también recae en `es`. Sobrescríbalo para una sola ejecución sin editar
  `config.yaml` con el indicador `--lang` (vea "Ejecución" más abajo).

## Agregar clientes

Las credenciales de los clientes viven en un almacén cifrado (`clients.secret`),
protegido por una contraseña maestra que usted elige. Configúrela una vez por sesión
de shell (o se le pedirá de forma interactiva):

```bash
export JULIA_MASTER_PW='choose-a-strong-master-password'
```

Agregar un cliente usando CIEC (Contraseña):

```bash
JULIA_MASTER_PW=$JULIA_MASTER_PW python -m julia_tool.main client add \
  --rfc XAXX010101000 --name "Cliente Ejemplo SA de CV" \
  --auth-type ciec --ciec-password 'the-client-CIEC-password'
```

Agregar un cliente usando e.firma (FIEL):

```bash
JULIA_MASTER_PW=$JULIA_MASTER_PW python -m julia_tool.main client add \
  --rfc XAXX010101000 --name "Cliente Ejemplo SA de CV" \
  --auth-type efirma \
  --cer-path /secure/certs/XAXX010101000.cer \
  --key-path /secure/certs/XAXX010101000.key \
  --key-password 'the-.key-file-password'
```

Listar y eliminar clientes:

```bash
JULIA_MASTER_PW=$JULIA_MASTER_PW python -m julia_tool.main client list
JULIA_MASTER_PW=$JULIA_MASTER_PW python -m julia_tool.main client remove --rfc XAXX010101000
```

## Ejecución

Comience siempre con una ejecución de prueba (dry run) —ejecuta el pipeline completo
(consulta a Graph, verificación del remitente, extracción de RFC, búsqueda de
credenciales) pero nunca inicia sesión en el portal del SAT ni envía correo; solo
imprime el recuento de resultados por mensaje:

```bash
JULIA_MASTER_PW=$JULIA_MASTER_PW python -m julia_tool.main --once --dry-run
```

Una vez que el recuento de la ejecución de prueba se vea correcto, ejecute un ciclo
real (con descarga del portal y correos de alerta habilitados):

```bash
JULIA_MASTER_PW=$JULIA_MASTER_PW python -m julia_tool.main --once
```

Luego ejecute de forma continua (sin `--once`) —se ejecuta en bucle indefinidamente,
consultando cada `poll_interval_s` segundos (300 por defecto), adecuado para un
servicio de larga duración, o bien omita `--once` para usarlo con cron/Task Scheduler:

```bash
JULIA_MASTER_PW=$JULIA_MASTER_PW python -m julia_tool.main
```

Indicadores útiles en cada ejecución:
- `--responsible EMAIL` — envía las alertas de esta ejecución a `EMAIL` en lugar del
  `responsible_email` de `config.yaml` (por ejemplo, para dirigir una ejecución de
  prueba a usted mismo sin editar la configuración).
- `--config PATH` — usa un archivo de configuración distinto de `config.yaml` (por
  ejemplo, una configuración por entorno o por prueba).
- `--lang es|en` — sobrescribe el `language` de `config.yaml` para el idioma de la
  salida en consola, los correos de alerta y la CLI de `client` en esta ejecución
  (`--lang` también funciona antes de `client add` / `client list` / `client remove`).
  El valor predeterminado es `es`; un valor no reconocido recae en `es`.

## Alertas por WhatsApp (opcional)

Además del correo, `julia_tool` puede enviar un mensaje corto de WhatsApp al
responsable en cada alerta (aviso urgente, descarga fallida, cliente no identificado,
correo en cuarentena). Usa la **API de WhatsApp Cloud** oficial de Meta. El correo se
envía siempre primero; si WhatsApp falla, se muestra el error y el correo y el
procesamiento del aviso continúan.

Configuración única por parte del despacho:

1. Crear (o usar) la cuenta **Meta Business** del despacho en business.facebook.com.
2. En developers.facebook.com crear una app de tipo **Business** y añadir el producto
   **WhatsApp**. Añadir el número del despacho que enviará los avisos (no debe estar en
   uso en la app de WhatsApp del teléfono) y verificarlo. Anotar su **Phone number ID**.
3. Crear un **token de acceso permanente**: Configuración del negocio → Usuarios del
   sistema → añadir un usuario del sistema → asignarle la app y la cuenta de WhatsApp →
   *Generar token* con el permiso `whatsapp_business_messaging`. Guardarlo en secreto.
4. En WhatsApp Manager → **Plantillas de mensajes** → crear una plantilla:
   - Categoría **Utilidad**, nombre `julia_aviso_sat`, idioma **Español (MEX)** (`es_MX`)
   - Cuerpo: `Aviso de julia_tool: {{1}}. Cliente: {{2}}. Revisa el correo del despacho para ver el detalle.`
   - Enviarla a aprobación (normalmente de minutos a unas horas).
5. Completar el bloque `whatsapp:` de `config.yaml` (ver `config.example.yaml`):
   `enabled: true`, el `phone_number_id` y el número o números destinatarios en formato
   internacional, solo dígitos (México: `52` + 10 dígitos).
6. Arrancar la herramienta con el token en una variable de entorno:
   ```bash
   JULIA_WA_TOKEN='EAAG...' JULIA_MASTER_PW=$JULIA_MASTER_PW python -m julia_tool.main
   ```
   Con Docker, añadir `-e JULIA_WA_TOKEN` a `docker run`. Sin la variable, la
   herramienta muestra un aviso y envía solo correo.

El mensaje se ve, por ejemplo, así: *"Aviso de julia_tool: URGENTE — requerimiento.
Cliente: ACME (XAXX010101000). Revisa el correo del despacho para ver el detalle."*
Con `include_client_details: false` no se envía por WhatsApp ni el nombre ni el RFC
del cliente (la segunda variable muestra "—"). Meta cobra una pequeña tarifa por cada
mensaje de utilidad entregado; consulte la tarifa vigente de Meta para México. Si un
número mexicano no recibe el mensaje, revise el formato que Meta devuelve para ese
número en la respuesta de la API (`wa_id`).

## Interfaz web

```bash
python -m julia_tool.main ui --port 8770
```

Esto abre una pequeña página web local (`http://127.0.0.1:8770`) donde el operador
puede configurar dos cosas sin editar `config.yaml` ni reiniciar el vigilante:
- **Palabras de alerta** — una lista separada por comas (por ejemplo,
  `requerimiento, multa, sanción`).
- **Correo del destinatario** — la dirección que recibe los correos de alerta.

Ambas se guardan en `settings_path` de `config.yaml` (por defecto `ui_settings.json`,
ya excluido en git —contiene datos operativos, no un secreto) y el vigilante las vuelve
a leer en cada ciclo de consulta, así que los cambios surten efecto sin reiniciar
`julia_tool`.

**El filtro de reenvío.** Las palabras de alerta filtran el *reenvío* de una
notificación genuina del SAT, no su clasificación —cada mensaje sigue verificándose,
descargándose y clasificándose igual que antes. Las palabras se comparan contra el
correo de notificación (asunto + cuerpo) y contra el texto del documento del SAT
descargado:
- Una lista de palabras **vacía** reenvía todo —este es el comportamiento
  predeterminado, así que nada cambia hasta que el operador decida participar
  escribiendo al menos una palabra.
- Si alguna palabra **coincide**, la alerta se envía al destinatario como siempre
  (resultado `alert_sent`).
- Si **ninguna palabra coincide**, la alerta **no se envía** —el resultado es
  `not_forwarded`. Aun así queda registrada y auditada (nada se descarta en silencio),
  simplemente no se envía por correo.

La coincidencia es **insensible a acentos y a mayúsculas/minúsculas**, así que
`sancion` coincide con `sanción` y `MULTA` coincide con `multa`.

**Las alertas de cuarentena, cliente desconocido y descarga fallida nunca se
filtran** —esos son avisos de seguridad u operativos, no notificaciones del SAT, y
siempre se envían sin importar las palabras de alerta.

**Precedencia del destinatario**, de mayor a menor prioridad: el indicador
`--responsible` de esta ejecución > el correo del destinatario guardado en la interfaz
web (si está configurado) > `responsible_email` en `config.yaml`.

La interfaz web se enlaza únicamente a `127.0.0.1` —nunca es accesible desde la red, y
no toca el almacén cifrado de credenciales ni pide la contraseña maestra.

## Notas de seguridad

- **Almacén de credenciales cifrado.** `clients.secret` está cifrado con Fernet; la
  clave de cifrado se deriva de su contraseña maestra con scrypt (`n=2**16, r=8,
  p=1`), y nunca se almacena. El archivo se escribe con permisos `0600` y se reemplaza
  de forma atómica en cada escritura (`julia_tool/secrets_store.py`).
- **Registro de auditoría.** Cada uso de credenciales (RFC, propósito, resultado,
  marca de tiempo) se escribe en la tabla `audit` de `state.sqlite` *antes* del intento
  de inicio de sesión en el portal —el registro muestra cada vez que se usaron las
  credenciales del SAT de un cliente, se haya logrado o no la descarga
  (`julia_tool/state.py`).
- **Cobertura de `.gitignore`.** El `.gitignore` del repositorio ya bloquea
  `clients.secret`, `*.cer`, `*.key`, `.token_cache*`, `state.sqlite` y `downloads/`
  —nunca los confirme (commit), y verifique `git status` antes de confirmar cambios si
  ha movido alguno de ellos.
- **Mantenga los archivos `.cer`/`.key` totalmente fuera del repositorio.** El almacén
  de secretos solo guarda *rutas* a los archivos de certificado/llave de e.firma, no
  los archivos en sí —guarde los archivos `.cer`/`.key` reales en un directorio fuera
  del repositorio con ACLs a nivel de sistema operativo que restrinjan el acceso de
  lectura a la cuenta que ejecuta `julia_tool` (por ejemplo, `chmod 700` al directorio,
  propiedad de una cuenta de servicio dedicada, no legible por todos).
- **La verificación del remitente siempre precede al uso de credenciales.** Un mensaje
  que falla la verificación de alineación de dominio SPF/DKIM/DMARC
  (`julia_tool/verify.py`) se pone en cuarentena y nunca dispara un inicio de sesión en
  el portal —vea `docs/superpowers/specs/2026-07-18-sat-buzon-watcher-design.md` §6
  para el modelo de seguridad completo.

## Estado actual / completar la descarga en vivo del portal

Todo lo que hay en este repositorio está construido y probado con pruebas unitarias
—ejecute la suite con:

```bash
.venv/bin/python -m pytest -q
```

**Excepto** los dos métodos de automatización de navegador en vivo,
`BuzonFetcher._fetch_efirma` y `BuzonFetcher._fetch_ciec` en `julia_tool/buzon.py`,
que actualmente son stubs seguros que lanzan `NotImplementedError`. Sus selectores
reales del portal y —para e.firma— el desafío de certificado de cliente FIEL solo
pueden confirmarse contra el portal en vivo del SAT con las credenciales de un cliente
real, algo que no puede validarse fuera de línea. Una implementación de referencia
completa y lista para copiar y pegar de ambos flujos, más la lista de verificación en
sitio para confirmar los selectores y trasladar el código confirmado a `buzon.py`, está
en [`docs/manual-validation.md`](docs/manual-validation.md).

Hasta que se complete ese paso en sitio, la herramienta sigue siendo completamente
funcional de extremo a extremo: cada correo del gobierno se verifica, se identifica a
su cliente y se envía una alerta a la persona responsable. Cuando la descarga en vivo
no está disponible (el stub lanza una excepción), el pipeline
(`julia_tool/pipeline.py`) la captura como un resultado normal de `fetch_failed` y
envía una alerta de respaldo que contiene el nombre del cliente, su RFC y un enlace
manual al portal del SAT (`portal.buzon_url` en `config.yaml`) —de modo que ninguna
notificación se pierda jamás mientras se termina la automatización en vivo.
