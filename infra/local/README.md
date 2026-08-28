# infra/local — 本地开发栈（Phase 01 / Subphase 07）

可复现的本地依赖栈，仅使用合成数据、Fake Identity 与模拟 Credential。
**不连接任何 DEV/SIT/UAT/PRD 服务，不包含任何真实凭据。**

## 组件

| 服务 | 镜像 | 默认端口 | 用途 |
| --- | --- | --- | --- |
| postgres | postgres:16 | 15432 | API/Worker 数据库（trust 认证，一次性数据） |
| queue | rabbitmq:4-alpine | 15672 | Queue Emulator（仓库代码默认仍用 infra-core FakeQueueClient） |
| objectstore | minio/minio | 19000/19001 | S3 兼容 Object Store Emulator |
| otel-collector | otel/opentelemetry-collector | 14317/14318 | OTLP Telemetry Collector（debug exporter） |
| fake-iam | python:3.12-alpine | 18080 | 最小 Fake OIDC Provider（合成用户/token） |

## 启动

```bash
cd infra/local
cp .env.example .env   # 每个 Worktree 单独一份
docker compose up -d
docker compose ps      # 等待全部 healthy
```

停止并清理：`docker compose down -v`。

## Worktree 隔离

每个 Worktree 修改自己的 `.env`：

- `COMPOSE_PROJECT_NAME`：独立 Compose 项目名（容器/网络/卷互不冲突）。
- `DMT_DB_NAME`：独立数据库名。
- `DMT_*_PORT`：独立宿主端口。
- `DMT_BUCKET_PREFIX`：独立对象存储 bucket 前缀。

## Fake IAM 接口

- `GET /healthz`、`GET /.well-known/openid-configuration`、`GET /jwks`、`GET /users`
- `POST /token`（form: `subject=content-author` 等）→ 返回 `fake-local-<subject>` 合成 token。

## 边界

- 本栈只服务本地开发与测试；受保护环境部署见 `.github/workflows/deploy-dev.yml`（仅定义，不在普通 PR 执行）。
- 镜像为公共 emulator；企业批准的镜像仓库/扫描方案落地后按其替换来源。
- 密钥永远不进入本目录；配置只允许 `secretref://` 引用（见 `config/`）。
