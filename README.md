# Sistema Controlo v1

Protótipo funcional de gestão de dispositivos Android explicitamente inscritos e autorizados.

## Arranque

`pip install -r requirements.txt` e depois `python starter.py`. Por defeito usa a porta 80; em desenvolvimento pode usar `PORT=8000`. Credenciais iniciais: `admin` / `admin123` (configuráveis no `.env`).

Inclui FastAPI, SQLite, autenticação, dashboard, inscrição/revogação, WebSocket, heartbeat, comandos, mensagens, notificações, logs, APK Builder, Demo Mode e esqueleto Android. A captura de ecrã/controlo deve usar apenas APIs oficiais Android e consentimento explícito.