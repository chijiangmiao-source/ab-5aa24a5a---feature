# 飞行试验检查单 · 多支离线修订 OT 复核（至多四支）

2~4 支离线修订（分支名唯一）同轮回传后，复核员在浏览器中判断它们能否合为一份
可执行步骤表。多支修订在**同一条墓碑序列上统一重放与裁定**，不做两两合并
（两两合并会使并发插入的相对位置随分组变化）。系统采用**保留删除锚点（墓碑）
的序列模型**完成多支操作变换，防止位置漂移让修改落到错误步骤。

## 模型要点

- 基线步骤带唯一 ASCII 标识；每支至多 **80** 条按顺序发生的
  `INSERT` / `DELETE` / `REPLACE`。
- `branches` 为 **2~4 支、分支名唯一**的数组（既有 left/right 双支请求与页面
  录入的裁定结果逐字不变，双支检查单可扩展为至多四支）。
- 插入带全局唯一新标识，可锚定 `FIRST` 或任一**尚存、已删（墓碑）或本支先前
  插入**的步骤；删除只置墓碑、节点永不回收，故锚点位置永不漂移。
- **同锚点并发插入**按 `(分支名, 操作标识)` 稳定裁定：分支名字典序小者整体
  贴近锚点；分支内部保持顺序重放结果（后发生的同锚点插入更贴近锚点）。裁定
  只取决于分支名与操作标识，与分支提交 / 分组顺序无关。
- 幂等合并：相同替换、重复删除（支内或跨任意支）合并入先生效的操作。
- 必须拒绝并展示**首个冲突**的双方操作与变换依据（冲突响应不含任何局部合并
  表）：
  - `DIVERGENT_REPLACE` 不同分支对同一步骤的不同替换（含跨第三支）
  - `DELETE_REPLACE_CONFLICT` 删除与替换交叉（支内或跨任意支）
  - `DUPLICATE_NEW_ID` 插入新标识重复（含跨非相邻支）
  - `DANGLING_ANCHOR` / `DANGLING_TARGET` 悬空引用
- 通过时同时展示**规范合并步骤表**（墓碑灰显、执行序号连续）、**每条原操作的
  保留 / 转换 / 合并结论及依据**，以及**参与裁定的分支顺序**（多支时响应附
  `branch_count`）。输入一旦改变或校验失败，页面旧结论立即作废（编辑任一分支
  即触发）。

零第三方依赖：Python 3.11 标准库 HTTP 服务 + 原生前端；测试用 `unittest`。

## 本地运行（无需 Docker）

```bash
python3 -m app.server            # 默认 0.0.0.0:8080，可用 PORT 覆盖
curl http://127.0.0.1:8080/healthz
python3 -m unittest discover -s tests -v
```

## Docker Compose

```bash
docker compose up -d web                 # 浏览器访问 http://localhost:8080
HOST_PORT=9090 docker compose up -d web  # 可配置宿主端口
```

验收服务 `verify`：构建镜像、等待 `web` 健康检查通过后，运行**领域测试 +
构建检查 + 页面 / 健康 HTTP 冒烟**（覆盖四支同锚点统一裁定、分组无关、
跨第三支冲突、墓碑后插入、幂等合并、冲突拒绝与双支响应回归），随后退出，
退出码即验收结论：

```bash
docker compose build web verify
docker compose run verify; echo "退出码=$?"   # 0 = 验收通过
# 或一次性： docker compose up --build verify （web 会作为依赖一并启动）
```

## API

`POST /api/merge`

```json
{
  "baseline": [{"id": "A", "text": "起飞前绕机检查"}],
  "branches": [
    {"name": "left",  "ops": [
      {"op_id": "L1", "kind": "INSERT", "new_id": "x", "anchor": "A", "text": "左翼油量复查"},
      {"op_id": "L2", "kind": "DELETE", "target": "A"},
      {"op_id": "L3", "kind": "REPLACE", "target": "x", "text": "复查双发油量"}
    ]},
    {"name": "right", "ops": []}
  ]
}
```

- `200 {"ok": true, ...}`：含 `merged`（规范步骤表）、`outcomes`（逐操作结论）、
  `arbitration`（裁定规则与分支序；超过两支时另附 `branch_count`）。
- `200 {"ok": false, "conflict": {...}}`：领域冲突，含 `code`、`basis`、
  `op_a` / `op_b`（首个冲突双方）、`ref`、`issue_count`，且不含 `merged` /
  `outcomes`（不返回局部合并表）。
- `400 {"error": ...}`：结构非法（JSON 错误、标识不合规、分支数不在 2~4、
  分支名重复、超过 80 条等）。
