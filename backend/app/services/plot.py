"""绿地台账业务规则：接管信息校验、状态流转、权限口径与面积汇总。

接管环节固定按 待接管 → 已接管 → 已移交 依次推进：
- 新登记的绿地进入「待接管」，由本部门管养员完成「接管登记」后变为「已接管」；
- 「已接管」的绿地才能「办理移交」，移交后不可再接管，也不允许跳级。
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.security import Operator
from app.store import parse_area, store

MODULE = "plot"

# 绿地业务字段（与列表、详情、登记表单保持同一份口径）
BUSINESS_FIELDS = ["绿地编号", "绿地名称", "所属区域", "绿地类型", "面积", "植被群落", "管养等级"]
REQUIRED_FIELDS = list(BUSINESS_FIELDS)
FIELD_TEAM = "管养班组"
TAKEOVER_FIELDS = [FIELD_TEAM, *BUSINESS_FIELDS]

STATUS_PENDING = "待接管"
STATUS_TAKEN = "已接管"
STATUS_TRANSFERRED = "已移交"
STATUS_ORDER = [STATUS_PENDING, STATUS_TAKEN, STATUS_TRANSFERRED]

ACTION_TAKEOVER = "接管登记"
ACTION_TRANSFER = "办理移交"
ACTION_RULES = {
    ACTION_TAKEOVER: {"from": STATUS_PENDING, "to": STATUS_TAKEN},
    ACTION_TRANSFER: {"from": STATUS_TAKEN, "to": STATUS_TRANSFERRED},
}


class PlotService:
    # ---------- 读取 ----------
    def _filtered(self, *, keyword: str | None, status: str | None, zone: str | None) -> list[dict[str, Any]]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("绿地编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if zone:
            rows = [row for row in rows if zone in str(row.get("所属区域", ""))]
        return rows

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        zone: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = [self._normalize(row) for row in self._filtered(keyword=keyword, status=status, zone=zone)]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        row = store.find(MODULE, entry_id)
        return self._normalize(row) if row else None

    def find_row(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def stats(self) -> dict[str, Any]:
        """接管明细驱动的实时统计：在管面积只统计「已接管」绿地。"""
        rows = [self._normalize(row) for row in store.rows(MODULE)]
        by_status = {status: 0 for status in STATUS_ORDER}
        managed_area = 0.0
        for row in rows:
            status = str(row.get("status"))
            if status in by_status:
                by_status[status] += 1
            if status == STATUS_TAKEN:
                managed_area += float(row.get("面积") or 0.0)
        return {
            STATUS_PENDING: by_status[STATUS_PENDING],
            STATUS_TAKEN: by_status[STATUS_TAKEN],
            STATUS_TRANSFERRED: by_status[STATUS_TRANSFERRED],
            "在管面积": round(managed_area, 2),
        }

    def zones(self, *, keyword: str | None = None) -> list[dict[str, Any]]:
        """分区视图：按所属区域汇总，面积口径与列表/详情完全一致。"""
        grouped: dict[str, dict[str, Any]] = {}
        for raw in self._filtered(keyword=keyword, status=None, zone=None):
            row = self._normalize(raw)
            zone = str(row.get("所属区域") or "未分区")
            bucket = grouped.setdefault(
                zone,
                {"所属区域": zone, "绿地数量": 0, "在管数量": 0, "面积合计": 0.0, "items": []},
            )
            bucket["绿地数量"] += 1
            if row.get("status") == STATUS_TAKEN:
                bucket["在管数量"] += 1
            bucket["面积合计"] += float(row.get("面积") or 0.0)
            bucket["items"].append(row)
        for bucket in grouped.values():
            bucket["面积合计"] = round(bucket["面积合计"], 2)
        return list(grouped.values())

    # ---------- 写入 ----------
    def create_entry(self, values: dict[str, Any], operator: Operator) -> tuple[dict[str, Any] | None, str]:
        """登记接管信息；缺项逐项点明，面积非法、编号重复都会被拦下。"""
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"

        area = parse_area(values.get("面积"))
        if area is None:
            return None, "面积必须是不小于 0 的数字（可带「㎡」单位），请核对后再提交"

        code = str(values.get("绿地编号")).strip()
        existing = self._find_by_code(code)
        if existing is not None:
            # 同一绿地编号重复提交只留一条，幂等返回已有记录
            return self._normalize(existing), f"绿地编号 {code} 已登记（接管状态：{existing.get('status')}），未重复创建"

        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in BUSINESS_FIELDS:
            entry[field] = str(values.get(field)).strip()
        entry["面积"] = area
        # 登记班组默认取当前管养员所在班组，后续只有该班组能改动
        entry[FIELD_TEAM] = operator.team or str(values.get(FIELD_TEAM) or "").strip()
        entry["status"] = STATUS_PENDING
        entry["pending"] = True
        entry["abnormal"] = False
        entry["登记人"] = operator.name
        rows.append(entry)
        return self._normalize(entry), ""

    def run_action(self, entry_id: int, action: str, operator: Operator) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"绿地 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于接管移交可执行范围"

        rule = ACTION_RULES[action]
        current = entry.get("status")
        if current == STATUS_TRANSFERRED:
            return None, "该绿地已移交，不能再接管或重新移交"
        if current != rule["from"]:
            expected = ACTION_TAKEOVER if current == STATUS_PENDING else ACTION_TRANSFER
            return None, f"当前为「{current}」，需先执行「{expected}」，接管移交不允许跳级"

        today = date.today().isoformat()
        entry["status"] = rule["to"]
        entry["pending"] = rule["to"] == STATUS_PENDING
        entry["abnormal"] = False
        if action == ACTION_TAKEOVER:
            entry["接管人"] = operator.name
            entry["接管日期"] = today
            done = "接管完成"
        else:
            entry["移交人"] = operator.name
            entry["移交日期"] = today
            done = "移交完成"
        return self._normalize(entry), f"绿地{done}，当前状态：{rule['to']}"

    # ---------- 内部工具 ----------
    def _find_by_code(self, code: str) -> dict[str, Any] | None:
        for row in store.rows(MODULE):
            if str(row.get("绿地编号", "")).strip() == code:
                return row
        return None

    def _normalize(self, row: dict[str, Any]) -> dict[str, Any]:
        """统一出口：列表、详情、分区、导出共用同一份字段与面积口径。"""
        normalized = dict(row)
        for field in TAKEOVER_FIELDS:
            normalized.setdefault(field, "")
        area = parse_area(normalized.get("面积"))
        normalized["面积"] = area if area is not None else 0.0
        # 绿地状态始终与接管流转状态保持一致，避免两列串位
        normalized["绿地状态"] = row.get("status", "")
        return normalized
