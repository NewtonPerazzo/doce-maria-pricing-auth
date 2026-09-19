# Doce Maria Pricing Auth

Serviço FastAPI independente para cadastro, login, refresh, logout e recuperação de senha.
Não importa nem chama a API de precificação. Não depende de outros produtos.

## Rodar localmente

Python 3.12+ e Docker Desktop são necessários.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
.\.venv\Scripts\python.exe scripts\generate_keys.py
docker compose up -d --build
docker compose ps
```

Não repita a geração se as chaves já existirem. O script não sobrescreve arquivos.
Swagger em [localhost:8002/docs](http://localhost:8002/docs); Mailpit em
[localhost:8025](http://localhost:8025). MongoDB do Auth usa porta local 27018.
`docker compose up --build` também executa o Auth em contêiner, depois de gerar as chaves.

## Contrato HTTP

| Método | Caminho | Entrada |
| --- | --- | --- |
| POST | `/users` | first_name, last_name, email, phone, password |
| POST | `/authentication/login` | email, password |
| POST | `/authentication/refresh` | refresh_token |
| POST | `/authentication/logout` | refresh_token |
| GET | `/users/me` | Authorization: Bearer access_token |
| POST | `/authentication/forgot-password` | email |
| POST | `/authentication/reset-password` | reset_token, new_password |

Login/refresh retornam access_token, refresh_token, token_type e access_token_expires_in.
A recuperação responde genericamente mesmo para emails sem conta. O código é enviado por
email, expira, é armazenado como hash e pode ser utilizado apenas uma vez. Uma nova
solicitação substitui o código anterior. Na confirmação, a versão de autenticação muda,
invalidando as sessões anteriores no Auth.

## Segurança e configuração

- Senhas: Argon2id; 8–128 caracteres, sem alteração silenciosa de espaços na senha.
- Access tokens: RS256, validade configurável de 5 minutos por padrão.
- Refresh: token opaco armazenado como hash, rotação atômica e duração de 7 dias.
  Reutilizar um dos últimos 100 refresh tokens rotacionados revoga a sessão.
- Recuperação: código aleatório de uso único, padrão de 20 minutos.
- Limitação de tentativas compartilhada no MongoDB: padrão 30/minuto por IP e rota,
  com limite adicional de 3 solicitações de recuperação/minuto por email.
- A limitação usa o IP da conexão. Configure corretamente proxies confiáveis ao implantar;
  não aceite cabeçalhos de IP arbitrários da internet.
- A chave privada permanece em `.keys/access-private.pem`. Distribua somente
  `.keys/access-public.pem` para APIs que validem tokens localmente.
- O frontend consulta a sessão no Auth. A API de Pricing não faz isso: um access token já
  emitido pode continuar válido nela até expirar, mesmo após logout ou troca de senha.
- O Auth não implementa vínculo de contas de outros emissores nem assinatura comercial.

SMTP local usa Mailpit e não envia emails externos. Para produção, configure SMTP_HOST,
SMTP_PORT, SMTP_STARTTLS, SMTP_USERNAME, SMTP_PASSWORD e MAIL_FROM, além de HTTPS, banco
protegido e armazenamento seguro das chaves. O envio de recuperação usa tarefa em processo;
falhas são registradas sem dados pessoais/tokens, e o usuário pode solicitar novamente.
Entrega durável com fila e política de retenção/exclusão de contas são decisões de implantação.

## Arquitetura e testes

`domain` define política/erros; `application` implementa os casos de uso contra interfaces;
`infrastructure` adapta MongoDB, Argon2, JWT e SMTP; `presentation` contém HTTP e validação.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check app tests scripts
.\.venv\Scripts\python.exe -m ruff format --check app tests scripts
```

Os testes cobrem hashes, login, rotação/reutilização, logout, expiração, recuperação de senha,
invalidação de sessões e limitação de tentativas. Nenhuma chave real é incluída nos testes.

