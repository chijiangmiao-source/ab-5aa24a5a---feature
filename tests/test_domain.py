"""领域测试：墓碑保留序列模型、双支 OT 裁定、合并与拒绝。"""

import unittest

from app import domain


def mk(baseline, left=(), right=(), lname="left", rname="right"):
    return {
        "baseline": [{"id": i, "text": f"步骤{i}"} if isinstance(i, str) else i
                     for i in baseline],
        "branches": [
            {"name": lname, "ops": list(left)},
            {"name": rname, "ops": list(right)},
        ],
    }


def mkn(baseline, branches):
    """N 支请求：branches 为 [(name, [op, ...]), ...]，2~4 支。"""
    return {
        "baseline": [{"id": i, "text": f"步骤{i}"} if isinstance(i, str) else i
                     for i in baseline],
        "branches": [{"name": n, "ops": list(ops)} for n, ops in branches],
    }


def ins(op_id, new_id, anchor, text=None):
    d = {"op_id": op_id, "kind": "INSERT", "new_id": new_id,
         "anchor": anchor or "FIRST", "text": text or f"文本{new_id}"}
    return d


def dele(op_id, target):
    return {"op_id": op_id, "kind": "DELETE", "target": target}


def rep(op_id, target, text):
    return {"op_id": op_id, "kind": "REPLACE", "target": target, "text": text}


def live_ids(result):
    return [r["id"] for r in result["merged"] if r["step_no"] is not None]


def all_ids(result):
    return [r["id"] for r in result["merged"]]


def outcome_map(result):
    return {(o["branch"], o["op_id"]): o for o in result["outcomes"]}


class TestBasics(unittest.TestCase):
    def test_no_ops_keeps_baseline(self):
        r = domain.merge(mk(["A", "B", "C"]))
        self.assertTrue(r["ok"])
        self.assertEqual(live_ids(r), ["A", "B", "C"])
        self.assertEqual([row["step_no"] for row in r["merged"]], [1, 2, 3])

    def test_single_branch_full_lifecycle(self):
        r = domain.merge(mk(
            ["A", "B", "C"],
            left=[ins("L1", "x", "A"), dele("L2", "B"),
                  ins("L3", "y", "B"), rep("L4", "C", "新C")]))
        self.assertTrue(r["ok"], r)
        # A, x, B(墓碑), y(紧随墓碑), C(已替换文本)
        self.assertEqual(all_ids(r), ["A", "x", "B", "y", "C"])
        self.assertEqual(live_ids(r), ["A", "x", "y", "C"])
        b = next(row for row in r["merged"] if row["id"] == "B")
        self.assertEqual(b["status"], "tombstone")
        self.assertEqual(b["deleted_by"], "L2")
        c = next(row for row in r["merged"] if row["id"] == "C")
        self.assertEqual(c["text"], "新C")

    def test_insert_can_anchor_first(self):
        r = domain.merge(mk(["A"], left=[ins("L1", "x", None)]))
        self.assertTrue(r["ok"])
        self.assertEqual(all_ids(r), ["x", "A"])

    def test_insert_can_anchor_prior_insert(self):
        r = domain.merge(mk(["A"], left=[ins("L1", "x", "A"), ins("L2", "y", "x")]))
        self.assertTrue(r["ok"], r)
        self.assertEqual(all_ids(r), ["A", "x", "y"])

    def test_replace_does_not_drift_position(self):
        r = domain.merge(mk(["A", "B", "C"], left=[rep("L1", "B", "新B")]))
        b = next(row for row in r["merged"] if row["id"] == "B")
        self.assertEqual(b["position"], 1)
        self.assertEqual(b["step_no"], 2)


class TestConcurrentInsertArbitration(unittest.TestCase):
    def test_same_anchor_concurrent_insert_branch_order(self):
        payload = mk(["A", "B", "C"],
                     left=[ins("Lx", "x", "B")],
                     right=[ins("Rp", "p", "B"), ins("Rq", "q", "B")])
        r = domain.merge(payload)
        self.assertTrue(r["ok"], r)
        # 分支名 left<right：left 整体贴近 B；right 内保持重放序（q 后插更贴近）
        self.assertEqual(all_ids(r), ["A", "B", "x", "q", "p", "C"])
        om = outcome_map(r)
        self.assertEqual(om[("left", "Lx")]["result"], domain.R_KEPT)  # 贴近锚点一方
        self.assertEqual(om[("right", "Rp")]["result"], domain.R_TRANSFORMED)
        self.assertEqual(om[("right", "Rq")]["result"], domain.R_TRANSFORMED)
        # 仲裁依据必须包含稳定裁定说明
        self.assertIn("(分支名, 操作标识)", om[("right", "Rp")]["basis"])

    def test_arbitration_uses_names_not_positions(self):
        payload = mk(["A", "B"],
                     left=[ins("Z1", "z", "B")],
                     right=[ins("A1", "a", "B")],
                     lname="zulu", rname="alpha")
        r = domain.merge(payload)
        self.assertTrue(r["ok"], r)
        # alpha 字典序小，贴近 B
        self.assertEqual(all_ids(r), ["A", "B", "a", "z"])

    def test_concurrent_insert_at_FIRST(self):
        r = domain.merge(mk(["A"],
                            left=[ins("L1", "l", None)],
                            right=[ins("R1", "r0", None), ins("R2", "r1", None)]))
        self.assertTrue(r["ok"], r)
        self.assertEqual(all_ids(r), ["l", "r1", "r0", "A"])

    def test_position_shift_from_unrelated_concurrent_insert_is_transformed(self):
        # right 在 A 后插入；left 在 C 后插入 —— 锚点不同，但 left 的合并位整体后移
        r = domain.merge(mk(["A", "B", "C"],
                            left=[ins("L1", "l", "C")],
                            right=[ins("R1", "r", "A")]))
        self.assertTrue(r["ok"], r)
        self.assertEqual(all_ids(r), ["A", "r", "B", "C", "l"])
        om = outcome_map(r)
        self.assertEqual(om[("left", "L1")]["result"], domain.R_TRANSFORMED)
        self.assertEqual(om[("left", "L1")]["position_before"], 3)
        self.assertEqual(om[("left", "L1")]["position_after"], 4)


class TestTombstoneAnchor(unittest.TestCase):
    def test_insert_after_tombstone_on_same_branch(self):
        r = domain.merge(mk(["A", "B", "C"],
                            left=[dele("L1", "B"), ins("L2", "y", "B")]))
        self.assertTrue(r["ok"], r)
        self.assertEqual(all_ids(r), ["A", "B", "y", "C"])
        om = outcome_map(r)
        self.assertEqual(om[("left", "L2")]["result"], domain.R_KEPT)
        self.assertIn("墓碑", om[("left", "L2")]["basis"])

    def test_other_branch_anchor_deleted_tombstone_holds_position(self):
        r = domain.merge(mk(["A", "B", "C"],
                            left=[dele("L1", "B"), ins("L2", "y", "B")],
                            right=[ins("R1", "r", "B")]))
        self.assertTrue(r["ok"], r)
        # B 墓碑后：left 块（y）贴近，然后 right（r）
        self.assertEqual(all_ids(r), ["A", "B", "y", "r", "C"])

    def test_delete_outcome_kept_and_tombstone_count(self):
        r = domain.merge(mk(["A", "B"], left=[dele("L1", "A")]))
        om = outcome_map(r)
        self.assertEqual(om[("left", "L1")]["result"], domain.R_KEPT)
        self.assertEqual(r["stats"]["tombstones"], 1)
        self.assertEqual(r["stats"]["live"], 1)


class TestIdempotentMerge(unittest.TestCase):
    def test_duplicate_delete_within_branch_merges(self):
        r = domain.merge(mk(["A"], left=[dele("L1", "A"), dele("L2", "A")]))
        self.assertTrue(r["ok"], r)
        om = outcome_map(r)
        self.assertEqual(om[("left", "L1")]["result"], domain.R_KEPT)
        self.assertEqual(om[("left", "L2")]["result"], domain.R_MERGED)
        self.assertEqual(om[("left", "L2")]["merged_into"]["op_id"], "L1")

    def test_identical_replace_within_branch_merges(self):
        r = domain.merge(mk(["A"], left=[rep("L1", "A", "同文"), rep("L2", "A", "同文")]))
        self.assertTrue(r["ok"], r)
        om = outcome_map(r)
        self.assertEqual(om[("left", "L2")]["result"], domain.R_MERGED)

    def test_identical_replace_cross_branch_merges(self):
        r = domain.merge(mk(["A"], left=[rep("L1", "A", "同文")],
                            right=[rep("R1", "A", "同文")]))
        self.assertTrue(r["ok"], r)
        self.assertEqual(next(row for row in r["merged"] if row["id"] == "A")["text"], "同文")
        om = outcome_map(r)
        # keeper 取 (分支名, op_id) 最小者：L1
        self.assertEqual(om[("right", "R1")]["result"], domain.R_MERGED)
        self.assertEqual(om[("right", "R1")]["merged_into"]["op_id"], "L1")
        self.assertEqual(om[("left", "L1")]["result"], domain.R_KEPT)

    def test_duplicate_delete_cross_branch_merges(self):
        r = domain.merge(mk(["A"], left=[dele("L9", "A")], right=[dele("R1", "A")]))
        self.assertTrue(r["ok"], r)
        om = outcome_map(r)
        self.assertEqual(om[("right", "R1")]["result"], domain.R_MERGED)
        self.assertEqual(om[("right", "R1")]["merged_into"]["op_id"], "L9")


class TestRejections(unittest.TestCase):
    def _conflict(self, payload, code):
        r = domain.merge(payload)
        self.assertFalse(r["ok"])
        c = r["conflict"]
        self.assertEqual(c["code"], code)
        self.assertTrue(c["basis"])
        self.assertIsNotNone(c["op_a"])
        return c

    def test_divergent_replace_within_branch(self):
        c = self._conflict(
            mk(["A"], left=[rep("L1", "A", "文本1"), rep("L2", "A", "文本2")]),
            "DIVERGENT_REPLACE")
        self.assertEqual(c["op_a"]["op_id"], "L1")
        self.assertEqual(c["op_b"]["op_id"], "L2")

    def test_divergent_replace_cross_branch(self):
        c = self._conflict(
            mk(["A"], left=[rep("L1", "A", "塔台频率")], right=[rep("R1", "A", "地面频率")]),
            "DIVERGENT_REPLACE")
        self.assertEqual(c["ref"], "A")

    def test_replace_then_delete_within_branch(self):
        c = self._conflict(
            mk(["A"], left=[rep("L1", "A", "新"), dele("L2", "A")]),
            "DELETE_REPLACE_CONFLICT")
        self.assertEqual(c["op_b"]["op_id"], "L2")

    def test_delete_then_replace_within_branch(self):
        self._conflict(
            mk(["A"], left=[dele("L1", "A"), rep("L2", "A", "新")]),
            "DELETE_REPLACE_CONFLICT")

    def test_delete_replace_cross_branch(self):
        c = self._conflict(
            mk(["A"], left=[dele("L1", "A")], right=[rep("R1", "A", "新")]),
            "DELETE_REPLACE_CONFLICT")
        self.assertEqual(c["op_a"]["op_id"], "L1")
        self.assertEqual(c["op_b"]["op_id"], "R1")

    def test_duplicate_new_id_within_branch(self):
        c = self._conflict(
            mk(["A"], left=[ins("L1", "dup", "A"), ins("L2", "dup", "A")]),
            "DUPLICATE_NEW_ID")
        self.assertEqual(c["ref"], "dup")

    def test_duplicate_new_id_cross_branch(self):
        self._conflict(
            mk(["A"], left=[ins("L1", "dup", "A")], right=[ins("R1", "dup", "A")]),
            "DUPLICATE_NEW_ID")

    def test_new_id_collides_baseline(self):
        self._conflict(mk(["A"], left=[ins("L1", "A", "FIRST")]), "DUPLICATE_NEW_ID")

    def test_dangling_anchor(self):
        c = self._conflict(mk(["A"], left=[ins("L1", "x", "GHOST")]), "DANGLING_ANCHOR")
        self.assertIsNone(c["op_b"])  # 单方操作即非法
        self.assertEqual(c["ref"], "GHOST")

    def test_dangling_target_to_other_branch_insert(self):
        # right 不能引用只有 left 插入的标识
        self._conflict(
            mk(["A"], left=[ins("L1", "x", "A")], right=[dele("R1", "x")]),
            "DANGLING_TARGET")

    def test_first_conflict_is_earliest_by_order(self):
        # 两处异替换：(left L1, A) 与 (left L3, B)；首个必须指向 A 那对
        payload = mk(
            ["A", "B"],
            left=[rep("L1", "A", "a1"), rep("L3", "B", "b1")],
            right=[rep("R9", "A", "a2"), rep("R8", "B", "b2")])
        r = domain.merge(payload)
        self.assertFalse(r["ok"])
        self.assertEqual(r["conflict"]["ref"], "A")
        self.assertEqual(r["conflict"]["issue_count"], 2)


class TestStructuralValidation(unittest.TestCase):
    def test_reject_81_ops(self):
        ops = [dele(f"L{i:02d}", "A") for i in range(81)]  # 大量重复删除也只 81 条输入
        payload = mk(["A"], left=ops[:1])
        payload["branches"][0]["ops"] = ops
        with self.assertRaises(domain.OTReject):
            domain.merge(payload)

    def test_accept_80_ops(self):
        # 80 条：1 条删除 + 79 条对它的重复删除（合并）
        ops = [dele("L0", "A")] + [dele(f"L{i}", "A") for i in range(1, 80)]
        r = domain.merge(mk(["A", "B"], left=ops))
        self.assertTrue(r["ok"], r)
        self.assertEqual(len(r["outcomes"]), 80)

    def test_non_ascii_id_rejected(self):
        with self.assertRaises(domain.OTReject):
            domain.merge(mk(["A步骤"], left=[]))

    def test_whitespace_id_rejected(self):
        payload = {"baseline": [{"id": "A B", "text": "x"}],
                   "branches": [{"name": "left", "ops": []},
                                {"name": "right", "ops": []}]}
        with self.assertRaises(domain.OTReject):
            domain.merge(payload)

    def test_duplicate_op_id_rejected(self):
        with self.assertRaises(domain.OTReject):
            domain.merge(mk(["A"], left=[dele("DUP", "A"), dele("DUP", "A")]))
        # 注意：这是结构拒绝（操作标识必须唯一），区别于幂等合并的业务语义

    def test_must_have_two_branches(self):
        with self.assertRaises(domain.OTReject):
            domain.merge({"baseline": [{"id": "A", "text": "x"}], "branches": []})


class TestOutcomeCompleteness(unittest.TestCase):
    def test_every_original_op_classified(self):
        payload = mk(
            ["A", "B", "C"],
            left=[ins("L1", "x", "B"), dele("L2", "B"),
                  ins("L3", "y", "B"), dele("L4", "B"),
                  rep("L5", "C", "新C")],
            right=[ins("R1", "p", "B"), ins("R2", "q", "B"),
                   rep("R3", "C", "新C"), dele("R4", "B")])
        r = domain.merge(payload)
        self.assertTrue(r["ok"], r)
        self.assertEqual(len(r["outcomes"]), 9)
        results = {o["result"] for o in r["outcomes"]}
        self.assertEqual(results, {domain.R_KEPT, domain.R_TRANSFORMED, domain.R_MERGED})
        # 合并表中每个存活步骤序号连续且从 1 开始
        live = [row["step_no"] for row in r["merged"] if row["step_no"] is not None]
        self.assertEqual(live, list(range(1, len(live) + 1)))


class TestMultiBranch(unittest.TestCase):
    """三 / 四支同轮回传：统一墓碑序列，禁止两两分组。"""

    def test_three_branch_same_anchor_block_order(self):
        # 三支各向 B 后插入；分支块按分支名贴近锚点，块内保持重放序
        payload = mkn(["A", "B", "C"], [
            ("zulu",  [ins("Z1", "z1", "B")]),
            ("alpha", [ins("A1", "a1", "B"), ins("A2", "a2", "B")]),
            ("mid",   [ins("M1", "m1", "B")]),
        ])
        r = domain.merge(payload)
        self.assertTrue(r["ok"], r)
        # alpha 块（块内后插的 a2 更贴近 B）→ mid → zulu
        self.assertEqual(all_ids(r), ["A", "B", "a2", "a1", "m1", "z1", "C"])
        self.assertEqual(r["arbitration"]["branch_order"], ["alpha", "mid", "zulu"])
        om = outcome_map(r)
        # alpha 块最贴近锚点：a2 位置保留；a1 被本支 a2 顶开属块内重放序保留
        self.assertEqual(om[("alpha", "A1")]["result"], domain.R_KEPT)
        self.assertEqual(om[("alpha", "A2")]["result"], domain.R_KEPT)
        self.assertEqual(om[("mid", "M1")]["result"], domain.R_TRANSFORMED)
        self.assertEqual(om[("zulu", "Z1")]["result"], domain.R_TRANSFORMED)
        # 依据必须列出全部参与裁定的分支
        self.assertIn("alpha < mid < zulu", om[("zulu", "Z1")]["basis"])

    def test_four_branch_same_anchor_at_FIRST(self):
        payload = mkn(["A"], [
            ("b4", [ins("B1", "b", None)]),
            ("a1", [ins("A1", "a", None)]),
            ("c2", [ins("C1", "c", None), ins("C2", "c2", None)]),
            ("d3", [ins("D1", "d", None)]),
        ])
        r = domain.merge(payload)
        self.assertTrue(r["ok"], r)
        # a1 块 → b4 块（单条 b）→ c2 块（块内后插的 c2 更贴近首位）→ d3 块，然后基线 A
        self.assertEqual(all_ids(r), ["a", "b", "c2", "c", "d", "A"])

    def test_four_branch_interleaved_anchors(self):
        # 不同锚点的插入递归展开，整体顺序不依赖分支分组方式
        payload = mkn(["A", "B", "C"], [
            ("b1", [ins("B1", "ba", "A"), ins("B2", "bb", "ba")]),
            ("b2", [ins("X1", "x", "C")]),
            ("b3", [ins("Y1", "y", "B")]),
            ("b4", [ins("Z1", "z", None)]),
        ])
        r = domain.merge(payload)
        self.assertTrue(r["ok"], r)
        # z @ FIRST；A, ba, bb（ba 后）；B, y；C, x
        self.assertEqual(all_ids(r), ["z", "A", "ba", "bb", "B", "y", "C", "x"])

    def test_arbitration_independent_of_request_grouping(self):
        # 同一批分支以两种排列顺序提交，规范合并序必须完全一致
        branches = [
            ("zulu",  [ins("Z1", "z1", "B"), dele("Z2", "A")]),
            ("alpha", [ins("A1", "a1", "B"), rep("A2", "C", "共同新文")]),
            ("mid",   [ins("M1", "m1", "B"), rep("M2", "C", "共同新文")]),
        ]
        r1 = domain.merge(mkn(["A", "B", "C"], branches))
        r2 = domain.merge(mkn(["A", "B", "C"], list(reversed(branches))))
        self.assertTrue(r1["ok"], r1)
        self.assertTrue(r2["ok"], r2)
        self.assertEqual(all_ids(r1), all_ids(r2))
        self.assertEqual(live_ids(r1), live_ids(r2))
        self.assertEqual(r1["arbitration"]["branch_order"],
                         r2["arbitration"]["branch_order"])

    def test_cross_third_branch_divergent_replace(self):
        # left/right 一致替换，第三支给出不同文本：必须拒绝且报稳定的首对
        payload = mkn(["A"], [
            ("left",   [rep("L1", "A", "塔台频率")]),
            ("right",  [rep("R1", "A", "塔台频率")]),
            ("third",  [rep("T9", "A", "地面频率")]),
        ])
        r = domain.merge(payload)
        self.assertFalse(r["ok"])
        c = r["conflict"]
        self.assertEqual(c["code"], "DIVERGENT_REPLACE")
        self.assertEqual(c["op_a"]["op_id"], "L1")
        self.assertEqual(c["op_b"]["op_id"], "T9")
        self.assertEqual(c["ref"], "A")
        # 冲突时不得返回局部合并表
        self.assertNotIn("merged", r)
        self.assertNotIn("outcomes", r)

    def test_delete_replace_conflict_across_third_branch(self):
        payload = mkn(["A"], [
            ("left",  []),
            ("right", [dele("R5", "A")]),
            ("third", [rep("T1", "A", "新文本")]),
        ])
        r = domain.merge(payload)
        self.assertFalse(r["ok"])
        c = r["conflict"]
        self.assertEqual(c["code"], "DELETE_REPLACE_CONFLICT")
        self.assertEqual(c["op_a"]["op_id"], "R5")
        self.assertEqual(c["op_b"]["op_id"], "T1")

    def test_duplicate_new_id_among_three_branches(self):
        payload = mkn(["A"], [
            ("left",  [ins("L1", "dup", "A")]),
            ("mid",   [ins("M1", "other", "A")]),
            ("right", [ins("R1", "dup", "A")]),
        ])
        r = domain.merge(payload)
        self.assertFalse(r["ok"])
        self.assertEqual(r["conflict"]["code"], "DUPLICATE_NEW_ID")
        self.assertEqual(r["conflict"]["op_a"]["op_id"], "L1")
        self.assertEqual(r["conflict"]["op_b"]["op_id"], "R1")

    def test_duplicate_new_id_chain_reports_first_pair(self):
        # 同一新标识出现三次：首个冲突取前两支
        payload = mkn(["A"], [
            ("b1", [ins("O1", "dup", "A")]),
            ("b2", [ins("O2", "dup", "A")]),
            ("b3", [ins("O3", "dup", "A")]),
        ])
        r = domain.merge(payload)
        self.assertFalse(r["ok"])
        self.assertEqual(r["conflict"]["op_a"]["op_id"], "O1")
        self.assertEqual(r["conflict"]["op_b"]["op_id"], "O2")
        self.assertEqual(r["conflict"]["issue_count"], 2)

    def test_dangling_anchor_in_fourth_branch(self):
        payload = mkn(["A"], [
            ("b1", []), ("b2", []), ("b3", []),
            ("b4", [ins("X1", "x", "GHOST")]),
        ])
        r = domain.merge(payload)
        self.assertFalse(r["ok"])
        self.assertEqual(r["conflict"]["code"], "DANGLING_ANCHOR")
        self.assertEqual(r["conflict"]["ref"], "GHOST")

    def test_multi_branch_idempotent_merge(self):
        # 四支同删 A、三支同文替换 B：仅各保留 (分支名, op_id) 最小者，其余合并
        payload = mkn(["A", "B"], [
            ("b1", [dele("D1", "A"), rep("P1", "B", "共同")]),
            ("b2", [dele("D2", "A"), rep("P2", "B", "共同")]),
            ("b3", [dele("D3", "A")]),
            ("b4", [dele("D4", "A"), rep("P4", "B", "共同")]),
        ])
        r = domain.merge(payload)
        self.assertTrue(r["ok"], r)
        om = outcome_map(r)
        self.assertEqual(om[("b1", "D1")]["result"], domain.R_KEPT)
        for bid, oid in [("b2", "D2"), ("b3", "D3"), ("b4", "D4")]:
            self.assertEqual(om[(bid, oid)]["result"], domain.R_MERGED)
            self.assertEqual(om[(bid, oid)]["merged_into"]["op_id"], "D1")
        self.assertEqual(om[("b1", "P1")]["result"], domain.R_KEPT)
        self.assertEqual(om[("b2", "P2")]["result"], domain.R_MERGED)
        self.assertEqual(om[("b4", "P4")]["result"], domain.R_MERGED)

    def test_every_op_classified_with_four_branches(self):
        payload = mkn(["A", "B"], [
            ("b1", [ins("I1", "i1", "A"), dele("X1", "B")]),
            ("b2", [ins("I2", "i2", "A")]),
            ("b3", [ins("I3", "i3", "A"), dele("X3", "B")]),
            ("b4", [ins("I4", "i4", "A")]),
        ])
        r = domain.merge(payload)
        self.assertTrue(r["ok"], r)
        self.assertEqual(len(r["outcomes"]), 6)
        self.assertTrue(all(o["result"] in ("kept", "transformed", "merged")
                            for o in r["outcomes"]))
        live = [row["step_no"] for row in r["merged"] if row["step_no"] is not None]
        self.assertEqual(live, list(range(1, len(live) + 1)))


class TestBranchCountValidation(unittest.TestCase):
    def test_reject_one_branch(self):
        with self.assertRaises(domain.OTReject):
            domain.merge(mkn(["A"], [("left", [])]))

    def test_reject_five_branches(self):
        with self.assertRaises(domain.OTReject):
            domain.merge(mkn(["A"], [(f"b{i}", []) for i in range(5)]))

    def test_reject_duplicate_branch_names_among_four(self):
        payload = mkn(["A"], [("same", []), ("b2", []), ("same", []), ("b4", [])])
        with self.assertRaises(domain.OTReject):
            domain.merge(payload)

    def test_accept_two_three_four_branches(self):
        for n in (2, 3, 4):
            r = domain.merge(mkn(["A"], [(f"b{i}", []) for i in range(n)]))
            self.assertTrue(r["ok"], n)
            self.assertEqual(len(r["arbitration"]["branch_order"]), n)


if __name__ == "__main__":
    unittest.main(verbosity=2)
