# 企业内网服务健康巡检系统

这是方案 C 的一个可运行实现。Django 提供管理 API，SQLite 保存服务、巡检记录和每日统计，Celery worker 执行定时任务，Celery beat 负责调度，Redis 负责传递任务。

## 数据与流程

- `Environment`（dev/test/prod）、`Team`、`Service`：管理被巡检的 HTTP 服务及归属关系。
- `CheckRecord`：每次主动巡检的时间、状态码、耗时及成功与否。
- `DailyStat`：每个服务在指定日期的成功次数、总次数和健康率，同时保留环境与团队维度。
- `POST /api/services/{id}/check/`：同步请求服务的 `base_url + health_path`，保存结果后返回。HTTP 2xx 算成功，重定向及网络错误算失败，请求超时为 5 秒。
- Celery beat 在北京时间 00:00、08:00、16:00 发起 Token 轮换任务；每日 00:00 发起上一自然日的统计任务。重复执行同一天的统计会更新原有行，不会新增重复行。
- `health_rate` 以 0 到 1 表示；没有巡检记录时为 `null`，不表示 0% 健康率。

## 本地运行

以 Python 3.12 为例，在项目目录执行：

```powershell
conda activate hr-django
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

把最后一条命令输出的密钥填入 `.env` 的 `SERVICE_TOKEN_KEY=` 后面。这个密钥必须保留；换密钥后，数据库里已有的 Token 无法解密。`.env` 和 `db.sqlite3` 不提交到仓库。

```powershell
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

另开终端启动 Redis，例如已安装 Docker 时：

```powershell
docker run --rm --name hr-ai-redis -p 6380:6379 -d redis:7
```

示例使用本机 6380 端口，避免占用已有 Redis 的 6379 端口。如果已有 Redis 6.2 或更新版本，也可以使用现有实例并按需修改 `.env` 的 `CELERY_BROKER_URL`。再分别启动 worker 和 beat：

```powershell
conda activate hr-django
python -m celery -A config worker -l INFO --pool=solo
```

```powershell
conda activate hr-django
python -m celery -A config beat -l INFO
```

`--pool=solo` 用于 Windows 本地调试。运行定时任务需要 Redis、worker 和 beat 都在运行。

## API

先用超级用户登录 `http://127.0.0.1:8000/api-auth/login/`，再用浏览器中的 DRF 页面操作 API。接口仅对管理员开放。

| 路径 | 功能 |
| --- | --- |
| `/api/environments/` | 环境 CRUD，`code` 为 `dev`、`test` 或 `prod` |
| `/api/teams/` | 团队 CRUD |
| `/api/services/` | 服务 CRUD；`token` 可在创建或修改时传入，但不会在响应中显示 |
| `/api/services/{id}/check/` | POST 发起一次健康检查 |
| `/api/checks/?service={id}` | 查看巡检记录 |
| `/api/stats/?environment={id}&team={id}` | 查看每日统计 |
| `/healthz/` | 本地演示用的被巡检端点 |

可以创建一个服务：`base_url` 为 `http://127.0.0.1:8000`，`health_path` 为 `/healthz/`，关联已创建的环境和团队。调用它的 `check` 接口后，查看 `/api/checks/`。每个响应都有 `X-Request-Duration-Ms` 响应头，服务端日志也记录接口耗时。

为方便当场验证定时任务，无需等待到 00:00，可在 Django shell 中直接调用：

```powershell
python manage.py shell
```

```python
from django.utils import timezone
from monitor.tasks import rotate_service_tokens, summarize_daily_health

rotate_service_tokens()
summarize_daily_health(timezone.localdate().isoformat())
```

第二行按当天日期手动统计；正常的定时调用不传日期，统计前一个自然日。

## 题目边界

巡检请求会把本系统保存的 Token 解密后放入 `Authorization: Bearer ...` 请求头。每 8 小时的轮换只更新本系统的加密记录。题目没有提供目标服务的 Token 更新协议，因此此实现不声称能同步修改外部服务的鉴权配置；若目标服务校验该 Token，需要补充同步接口。系统只对实际产生的巡检记录计算健康率，题目未要求自动周期巡检。

## Cloudflare 临时预览

仓库包含 `wrangler.jsonc` 和 `Dockerfile.preview`，可以把 Django、Redis、Celery worker 和 beat 放进一个 Cloudflare Container，供短时间在线演示。部署前需要已开通 Containers 的 Cloudflare 账户、Docker 和 Node.js：

```powershell
npm install
npx wrangler deploy
```

部署后，通过 `npx wrangler secret bulk <本地密钥文件>` 配置 `DJANGO_SECRET_KEY`、`SERVICE_TOKEN_KEY`、`PREVIEW_ADMIN_PASSWORD` 三个密钥。密钥文件只保存在本机，不要提交。预览账户名为 `previewadmin`。打开部署所得的 `/api/` 地址，或在 `/api-auth/login/` 登录后试用接口。

这是临时预览环境：容器空闲后可能休眠或重启，容器里的 SQLite 数据会丢失；休眠期间 Celery beat 也不会准时执行定时任务。要长期运行，需改用持久数据库与持续可用的任务调度环境。Cloudflare Containers 可能产生费用，部署前应查看账户套餐。
