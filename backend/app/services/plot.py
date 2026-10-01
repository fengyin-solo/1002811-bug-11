"""绿地台账业务规则：接管/移交流转、字段校验、权限与面积口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "plot"

# 接管登记要求字段齐全；缺哪一项必须明确报给界面。
REQUIRED_FIELDS = ["绿地编号", "绿地名称", "所属区域", "绿地类型", "面积", "植被群落", "管养等级"]
DETAIL_FIELDS = REQUIRED_FIELDS + ["绿地状态"]

# 接管环节只能按 待接管 -> 已接管 -> 已移交 依次推进，不允许跳级、不允许回头。
STATUS_ORDER = ["待接管", "已接管", "已移交"]
ACTION_RULES = {"接管登记": "已接管", "确认移交": "已移交"}
ACTION_LABEL = {"接管登记": "接管", "确认移交": "移交"}


class PermissionError(Exception):
    """操作者无权改动接管信息（不是本部门管养员）。"""


def _text(values: dict[str, Any], field: str) -> str:
    return str(values.get(field) if values.get(field) is not None else "").strip()


def parse_area(raw: Any) -> float | None:
    """面积按数值解析；空串、非数字一律视为缺项，不允许静默存成文本。"""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


class PlotService:
    # ---- 查询 ----------------------------------------------------------------

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        zone: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("绿地编号", ""))]
        if zone:
            rows = [row for row in rows if str(row.get("所属区域", "")) == zone]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def zones(self) -> list[dict[str, Any]]:
        """分区视图：面积直接取明细里的数值字段汇总，保证与详情口径一致。"""
        summary: dict[str, dict[str, Any]] = {}
        for row in store.rows(MODULE):
            zone = str(row.get("所属区域") or "未分区")
            bucket = summary.setdefault(zone, {
                "所属区域": zone,
                "绿地数量": 0,
                "待接管": 0,
                "已接管": 0,
                "已移交": 0,
                "面积合计": 0.0,
                "在管面积": 0.0,
            })
            bucket["绿地数量"] += 1
            status = str(row.get("status") or "")
            if status in STATUS_ORDER:
                bucket[status] += 1
            area = parse_area(row.get("面积"))
            if area is not None:
                bucket["面积合计"] = round(bucket["面积合计"] + area, 2)
                if status == "已接管":
                    bucket["在管面积"] = round(bucket["在管面积"] + area, 2)
        return [summary[key] for key in sorted(summary)]

    def summary(self) -> dict[str, Any]:
        """绿地总览：在管面积随接管明细重算，而不是读某个会过期的缓存值。"""
        rows = store.rows(MODULE)
        counts = {status: 0 for status in STATUS_ORDER}
        managed_area = 0.0
        for row in rows:
            status = str(row.get("status") or "")
            if status in counts:
                counts[status] += 1
            if status == "已接管":
                area = parse_area(row.get("面积"))
                if area is not None:
                    managed_area += area
        return {
            "待接管": counts["待接管"],
            "已接管": counts["已接管"],
            "已移交": counts["已移交"],
            "在管面积": round(managed_area, 2),
        }

    # ---- 写入 ----------------------------------------------------------------

    def create_entry(
        self, values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, list[str], str | None]:
        area, area_invalid = self._validate_area(values)
        missing = [field for field in REQUIRED_FIELDS if not _text(values, field)]
        if area is None and "面积" not in missing:
            missing.append("面积")
        if area_invalid:
            return None, [], "面积必须是数字（单位平方米），请核对后再提交"
        if missing:
            return None, missing, None

        code = _text(values, "绿地编号")
        existing = self._find_by_code(code)
        if existing is not None:
            # 同一绿地编号重复提交只留一条：直接返回已有记录，不再新增。
            return existing, [], f"绿地编号 {code} 已存在（编号 {existing['id']}），未重复登记"

        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: _text(values, field) for field in DETAIL_FIELDS})
        entry["面积"] = area
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        entry["接管部门"] = None
        entry["管养员"] = None
        rows.append(entry)
        return entry, [], None

    def update_entry(
        self,
        entry_id: int,
        values: dict[str, Any],
        *,
        operator: dict[str, str],
    ) -> tuple[dict[str, Any] | None, list[str], str | None]:
        """补全/修改接管信息：只有本部门管养员能改，且字段口径与登记一致。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, [], f"绿地 {entry_id} 不存在或已归档"
        self._ensure_owner(operator, entry)

        area, area_invalid = self._validate_area(values)
        missing = [
            field for field in REQUIRED_FIELDS
            if not _text(values, field) and not _text(entry, field)
        ]
        if area is None and "面积" not in missing and not str(entry.get("面积") or "").strip():
            missing.append("面积")
        if area_invalid:
            return None, [], "面积必须是数字（单位平方米），请核对后再提交"
        if missing:
            return None, missing, None

        for field in DETAIL_FIELDS:
            if field == "面积":
                continue
            value = _text(values, field)
            if value:
                entry[field] = value
        if area is not None:
            entry["面积"] = area
        return entry, [], None

    def run_action(
        self,
        entry_id: int,
        action: str,
        *,
        operator: dict[str, str],
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"绿地 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于绿地接管可执行范围"

        # 只有管养员岗位能改动接管信息，别的班组连动作都提交不了。
        if operator.get("role") != "管养员":
            raise PermissionError(
                f"当前岗位「{operator.get('role') or '未知'}」无权{ACTION_LABEL[action]}绿地，"
                "仅本部门管养员可操作"
            )

        current = str(entry.get("status") or "")
        target = ACTION_RULES[action]

        if action == "接管登记":
            if current == "已移交":
                return None, "该绿地已移交，不能再次接管"
            if current == target:
                return None, "该绿地已是「已接管」状态，无需重复接管"
            if current != "待接管":
                return None, f"当前状态「{current}」不能直接接管，请先核对绿地状态"
            entry["status"] = target
            entry["pending"] = False
            entry["abnormal"] = False
            entry["接管部门"] = operator.get("department")
            entry["管养员"] = operator.get("name")
        else:  # 确认移交
            if current == "已移交":
                return None, "该绿地已移交，无需重复操作"
            if current != "已接管":
                # 待接管不能一步跳到已移交。
                return None, f"当前状态「{current}」不能移交：须先接管登记，再确认移交，不允许跳级"
            self._ensure_owner(operator, entry)
            entry["status"] = target
            entry["pending"] = False
            entry["abnormal"] = False

        return entry, f"绿地已{action}"

    # ---- 内部辅助 ------------------------------------------------------------

    def _find_by_code(self, code: str) -> dict[str, Any] | None:
        for row in store.rows(MODULE):
            if str(row.get("绿地编号") or "").strip() == code:
                return row
        return None

    @staticmethod
    def _validate_area(values: dict[str, Any]) -> tuple[float | None, bool]:
        """返回 (解析后面积, 是否给出了非法格式)。缺面积时面积为 None 且非法标志为假。"""
        raw = values.get("面积")
        if raw is None or not str(raw).strip():
            return None, False
        area = parse_area(raw)
        if area is None:
            return None, True
        if area < 0:
            return None, True
        return area, False

    @staticmethod
    def _ensure_owner(operator: dict[str, str], entry: dict[str, Any]) -> None:
        """接管后的绿地只认接管时落账的部门；待接管绿地本部门管养员都可以补录。"""
        if operator.get("role") != "管养员":
            raise PermissionError(
                f"当前岗位「{operator.get('role') or '未知'}」无权改动接管信息，仅本部门管养员可操作"
            )
        owner_department = entry.get("接管部门")
        if owner_department and operator.get("department") != owner_department:
            raise PermissionError(
                f"该绿地由「{owner_department}」接管，本部门（{operator.get('department') or '未知'}）不能改动"
            )
