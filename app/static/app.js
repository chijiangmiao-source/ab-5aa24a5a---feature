"use strict";

const SAMPLES = {
  concurrent: {
    baseline: [
      { id: "A", text: "起飞前绕机检查" },
      { id: "B", text: "确认襟翼处于起飞位" },
      { id: "C", text: "核对起飞简令" }
    ],
    branches: [
      {
        name: "left",
        ops: [
          { op_id: "L1", kind: "INSERT", new_id: "x-LTANK", anchor: "B", text: "左翼油箱油量复查" },
          { op_id: "L2", kind: "DELETE", target: "B" },
          { op_id: "L3", kind: "INSERT", new_id: "y-AFTER-TOMB", anchor: "B", text: "B 已删除仍锚定其后：检查单留存归档" },
          { op_id: "L4", kind: "INSERT", new_id: "z-WX", anchor: "FIRST", text: "最前位：气象雷达最后扫描" }
        ]
      },
      {
        name: "right",
        ops: [
          { op_id: "R1", kind: "INSERT", new_id: "p-RTANK", anchor: "B", text: "右翼油箱油量复查" },
          { op_id: "R2", kind: "INSERT", new_id: "q-AIL", anchor: "B", text: "右翼副翼行程复查" }
        ]
      }
    ]
  },
  merge: {
    baseline: [
      { id: "A", text: "记录起飞构型" },
      { id: "B", text: "设定起飞推力" },
      { id: "C", text: "喊话 V1" }
    ],
    branches: [
      {
        name: "left",
        ops: [
          { op_id: "L1", kind: "REPLACE", target: "A", text: "记录起飞构型（双签）" },
          { op_id: "L2", kind: "DELETE", target: "B" },
          { op_id: "L3", kind: "DELETE", target: "B" },
          { op_id: "L4", kind: "REPLACE", target: "A", text: "记录起飞构型（双签）" }
        ]
      },
      {
        name: "right",
        ops: [
          { op_id: "R1", kind: "REPLACE", target: "A", text: "记录起飞构型（双签）" },
          { op_id: "R2", kind: "DELETE", target: "B" },
          { op_id: "R3", kind: "REPLACE", target: "C", text: "喊话 V1 并计时" }
        ]
      }
    ]
  },
  conflict: {
    baseline: [
      { id: "A", text: "开车前许可确认" },
      { id: "B", text: "滑行路线复核" },
      { id: "C", text: "进入跑道前停顿检查" }
    ],
    branches: [
      {
        name: "left",
        ops: [
          { op_id: "L1", kind: "REPLACE", target: "A", text: "开车前许可确认（塔台频率）" },
          { op_id: "L2", kind: "DELETE", target: "C" }
        ]
      },
      {
        name: "right",
        ops: [
          { op_id: "R1", kind: "REPLACE", target: "A", text: "开车前许可确认（地面频率）" },
          { op_id: "R2", kind: "REPLACE", target: "C", text: "进入跑道前停顿检查并开灯" }
        ]
      }
    ]
  },
  fourway: {
    // 四支同轮回传：在同一墓碑序列上统一裁定；alpha 字典序最小，整体贴近锚点 B。
    // 注意：即使把四支先两两合并，相对位置也会随分组变化——系统不做两两合并。
    baseline: [
      { id: "A", text: "起飞前绕机检查" },
      { id: "B", text: "确认襟翼处于起飞位" },
      { id: "C", text: "核对起飞简令" }
    ],
    branches: [
      {
        name: "alpha",
        ops: [
          { op_id: "A1", kind: "INSERT", new_id: "a-LTANK", anchor: "B", text: "左翼油箱油量复查" },
          { op_id: "A2", kind: "INSERT", new_id: "a-ENG", anchor: "B", text: "左发滑油压力复查" },
          { op_id: "A3", kind: "DELETE", target: "B" },
          { op_id: "A4", kind: "INSERT", new_id: "a-TOMB", anchor: "B", text: "B 已删仍锚定其后：襟翼记录归档" }
        ]
      },
      {
        name: "beta",
        ops: [
          { op_id: "B1", kind: "INSERT", new_id: "b-RTANK", anchor: "B", text: "右翼油箱油量复查" }
        ]
      },
      {
        name: "gamma",
        ops: [
          { op_id: "G1", kind: "INSERT", new_id: "g-WX", anchor: "FIRST", text: "最前位：气象雷达最后扫描" },
          { op_id: "G2", kind: "REPLACE", target: "C", text: "核对起飞简令并双签" }
        ]
      },
      {
        name: "zulu",
        ops: [
          { op_id: "Z1", kind: "INSERT", new_id: "z-AIL", anchor: "B", text: "双副翼行程复查" },
          { op_id: "Z2", kind: "REPLACE", target: "C", text: "核对起飞简令并双签" }
        ]
      }
    ]
  },
  fourconflict: {
    // 四支中 alpha 与 gamma 对同一基线步骤 A 给出不同替换，
    // beta、zulu 两支夹在中间（跨第三支冲突）：系统仍稳定选出首个冲突的两条操作，
    // 不返回任何局部合并表；同时 C 上还埋有删除/替换交叉，但首个冲突必须是 A 那对。
    baseline: [
      { id: "A", text: "开车前许可确认" },
      { id: "B", text: "滑行路线复核" },
      { id: "C", text: "进入跑道前停顿检查" }
    ],
    branches: [
      {
        name: "alpha",
        ops: [
          { op_id: "A1", kind: "REPLACE", target: "A", text: "开车前许可确认（塔台频率）" },
          { op_id: "A2", kind: "DELETE", target: "C" }
        ]
      },
      {
        name: "beta",
        ops: [
          { op_id: "B1", kind: "INSERT", new_id: "b-note", anchor: "B", text: "滑行中线偏移量记录" }
        ]
      },
      {
        name: "gamma",
        ops: [
          { op_id: "G1", kind: "REPLACE", target: "A", text: "开车前许可确认（地面频率）" },
          { op_id: "G2", kind: "REPLACE", target: "C", text: "进入跑道前停顿检查并开灯" }
        ]
      },
      {
        name: "zulu",
        ops: [
          { op_id: "Z1", kind: "INSERT", new_id: "z-light", anchor: "A", text: "许可确认后开启着陆灯" }
        ]
      }
    ]
  }
};

const $ = (id) => document.getElementById(id);
const inputEl = $("input");
const stateEl = $("input-state");

function esc(v) {
  return String(v ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

function markDirty(msg) {
  stateEl.textContent = msg;
  stateEl.className = "input-state dirty";
  $("result-area").classList.add("hidden");
  $("conflict-box").classList.add("hidden");
  $("error-box").classList.add("hidden");
}

inputEl.addEventListener("input", () => {
  markDirty("输入已改变：旧结论已作废，需重新执行复核");
});

document.querySelectorAll("button[data-sample]").forEach((btn) => {
  btn.addEventListener("click", () => {
    inputEl.value = JSON.stringify(SAMPLES[btn.dataset.sample], null, 2);
    markDirty("已载入示例，尚未复核");
  });
});

$("verify-btn").addEventListener("click", async () => {
  let payload;
  try {
    payload = JSON.parse(inputEl.value);
  } catch (err) {
    markDirty("JSON 解析失败，未产生任何结论");
    const box = $("error-box");
    box.classList.remove("hidden");
    box.innerHTML = `<h3>输入无法解析</h3><p>${esc(err.message)}</p>`;
    return;
  }
  let res;
  try {
    const resp = await fetch("/api/merge", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    res = await resp.json();
    if (!resp.ok) {
      throw new Error(res.error || `HTTP ${resp.status}`);
    }
  } catch (err) {
    markDirty("请求失败，未产生任何结论");
    const box = $("error-box");
    box.classList.remove("hidden");
    box.innerHTML = `<h3>服务拒绝了请求</h3><p>${esc(err.message)}</p>`;
    return;
  }

  if (!res.ok) {
    stateEl.textContent = "复核结论：拒绝合并（存在必须裁定的冲突）";
    stateEl.className = "input-state dirty";
    $("result-area").classList.add("hidden");
    renderConflict(res.conflict);
    return;
  }

  stateEl.textContent = "复核结论：通过，可执行步骤表已生成";
  stateEl.className = "input-state fresh";
  $("conflict-box").classList.add("hidden");
  $("error-box").classList.add("hidden");
  renderMerged(res);
  renderOutcomes(res);
  $("result-area").classList.remove("hidden");
});

function opCard(op, label) {
  if (!op) {
    return `<div class="op-card dead">${esc(label)}：不适用（该冲突由单方操作自身非法导致，无另一方操作）</div>`;
  }
  return `<div class="op-card"><strong>${esc(label)}</strong>\n${esc(JSON.stringify(op, null, 2))}</div>`;
}

function renderConflict(c) {
  const box = $("conflict-box");
  box.classList.remove("hidden");
  box.innerHTML = `
    <h3>⛔ 首个冲突：${esc(c.code)}（全表共 ${c.issue_count} 处，仅展示首个）</h3>
    <p><strong>变换依据：</strong>${esc(c.basis)}</p>
    <p><strong>涉及标识：</strong><code>${esc(c.ref ?? "—")}</code></p>
    <div class="pair">${opCard(c.op_a, "冲突方 A（首操作）")}${opCard(c.op_b, "冲突方 B")}</div>`;
}

function renderMerged(res) {
  const arb = res.arbitration;
  $("arbitration").textContent =
    `裁定规则：${arb.rule}；本次分支序：${arb.branch_order.join(" < ")}（字典序小者同锚点时贴近锚点）`;
  const tbody = $("merged-table").querySelector("tbody");
  tbody.innerHTML = res.merged.map((row) => {
    const stepCell = row.step_no == null
      ? '<span class="step-del">墓碑</span>'
      : `<span class="step-no">${row.step_no}</span>`;
    const tags = row.tags.length ? `<br><span class="basis-line">${row.tags.map(esc).join("；")}</span>` : "";
    const del = row.deleted_by ? `<br><span class="basis-line">删除操作：${esc(row.deleted_by)}</span>` : "";
    return `<tr class="${esc(row.status)}">
      <td>${stepCell}</td>
      <td>${row.position}</td>
      <td class="id-cell">${esc(row.id)}</td>
      <td>${esc(row.text)}</td>
      <td><span class="badge ${esc(row.status)}">${esc(row.status)}</span>${tags}${del}</td>
    </tr>`;
  }).join("");
  const s = res.stats;
  const opsLine = res.arbitration.branch_order
    .map((n) => `${n} ${s.ops[n] ?? 0} 条`)
    .join(" / ");
  const count = res.arbitration.branch_count ?? 2;
  $("stats-line").textContent =
    `基线 ${s.baseline} 条；本次 ${count} 支操作：${opsLine}；` +
    `可执行步骤 ${s.live} 条，墓碑保留 ${s.tombstones} 个。`;
}

const RESULT_LABEL = { kept: "保留", transformed: "转换", merged: "合并" };

function renderOutcomes(res) {
  const tbody = $("outcome-table").querySelector("tbody");
  tbody.innerHTML = res.outcomes.map((o) => {
    const detail = o.target ? `目标 <code>${esc(o.target)}</code>`
      : `新标识 <code>${esc(o.new_id)}</code> @ ${esc(o.anchor)}`;
    const shift = o.kind === "INSERT"
      ? `<br><span class="basis-line">序列位 ${o.position_before} → ${o.position_after}</span>` : "";
    const merged = o.merged_into
      ? `<br><span class="basis-line">并入 ${esc(o.merged_into.branch)} 支 ${esc(o.merged_into.op_id)} #${o.merged_into.seq}</span>`
      : "";
    return `<tr>
      <td>${esc(o.branch)}</td>
      <td>${o.seq}</td>
      <td class="id-cell">${esc(o.op_id)}</td>
      <td>${esc(o.kind)}<br><span class="basis-line">${detail}</span>${shift}${merged}</td>
      <td><span class="result-${esc(o.result)}">${esc(RESULT_LABEL[o.result] || o.result)}</span></td>
      <td>${esc(o.basis)}</td>
    </tr>`;
  }).join("");
}

inputEl.value = JSON.stringify(SAMPLES.concurrent, null, 2);
markDirty("已载入示例，尚未复核");
