"""绿地台账接口：登记接管信息，按 待接管 → 已接管 → 已移交 推进。

所有写操作都要求本部门管养员身份，且只能改动本班组接管的绿地。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.security import Operator, current_operator, require_gardener
from app.services.plot import (
    ACTION_RULES,
    FIELD_TEAM,
    PlotService,
    STATUS_PENDING,
    STATUS_TAKEN,
    STATUS_TRANSFERRED,
)

router = APIRouter(prefix="/api/plot", tags=["绿地台账"])

service = PlotService()

LIST_FIELDS = ["绿地编号", "绿地名称", "所属区域", "绿地类型", "面积", "植被群落", "管养等级", "绿地状态"]
STATUSES = [STATUS_PENDING, STATUS_TAKEN, STATUS_TRANSFERRED]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按绿地编号检索"),
    status: str | None = Query(default=None, description="待接管、已接管、已移交"),
    zone: str | None = Query(default=None, description="按所属区域检索"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按绿地编号、状态与区域过滤绿地台账列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, zone=zone, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/stats")
def plot_stats() -> dict[str, Any]:
    """在管面积等指标：始终由接管明细实时汇总。"""
    return service.stats()


@router.get("/zones")
def plot_zones(keyword: str | None = Query(default=None, description="按绿地编号过滤后再分区")) -> dict[str, Any]:
    """分区视图：分区面积与详情行共用同一份口径，不会串位。"""
    return {"module": "plot", "zones": service.zones(keyword=keyword)}


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出绿地台账清单：返回当前全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "plot", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条绿地明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"绿地 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload, operator: Operator = Depends(current_operator)) -> ActionResult:
    """登记一条绿地接管信息，缺项逐项点明而不是静默拦截。"""
    require_gardener(operator)
    entry, message = service.create_entry(payload.values, operator)
    if message:
        ok = entry is not None  # 编号重复时幂等返回已有记录
        return ActionResult(ok=ok, message=message, entry=entry)
    return ActionResult(ok=True, message="绿地接管信息已登记，状态：待接管", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(
    entry_id: int,
    payload: EntryPayload,
    operator: Operator = Depends(current_operator),
) -> ActionResult:
    """执行接管登记、办理移交；非本班组、已移交、跳级都会被拦下并说明原因。"""
    row = service.find_row(entry_id)
    if row is None:
        return ActionResult(ok=False, message=f"绿地 {entry_id} 不存在或已归档")
    require_gardener(operator, str(row.get(FIELD_TEAM) or ""))

    action = str(payload.values.get("action") or "").strip()
    if action not in ACTION_RULES:
        return ActionResult(ok=False, message=f"动作「{action}」不属于接管移交可执行范围")
    entry, message = service.run_action(entry_id, action, operator)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
