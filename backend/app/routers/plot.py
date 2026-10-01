"""绿地台账接口：接管登记、信息补录、确认移交、分区视图与总览。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.plot import MODULE, PermissionError, PlotService

router = APIRouter(prefix="/api/plot", tags=["绿地台账"])

service = PlotService()

LIST_FIELDS = ["绿地编号", "绿地名称", "所属区域", "绿地类型", "面积", "植被群落", "管养等级", "绿地状态"]
STATUSES = ["待接管", "已接管", "已移交"]


def _operator(payload: EntryPayload | None, headers: tuple[str | None, str | None, str | None]) -> dict[str, str]:
    """操作人优先取请求体（浏览器可直接带中文），请求头只作兼容回退。"""
    raw = {}
    if payload is not None:
        raw = payload.values.get("operator") if isinstance(payload.values, dict) else None
        raw = raw if isinstance(raw, dict) else {}
    name = raw.get("name") or headers[0] or ""
    role = raw.get("role") or headers[1] or ""
    department = raw.get("department") or headers[2] or ""
    return {"name": str(name).strip(), "role": str(role).strip(), "department": str(department).strip()}


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按绿地编号检索"),
    zone: str | None = Query(default=None, description="按所属区域过滤"),
    status: str | None = Query(default=None, description="待接管、已接管、已移交"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按绿地编号、分区与状态过滤；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, zone=zone, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/zones")
def zone_view() -> dict[str, Any]:
    """分区视图：各分区面积合计直接来自明细，和详情读到的面积保持一致。"""
    items = service.zones()
    return {"module": MODULE, "total": len(items), "items": items}


@router.get("/summary")
def plot_summary() -> dict[str, Any]:
    """绿地总览：在管面积等指标按接管明细实时重算，刷新后仍对得上。"""
    return service.summary()


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出绿地台账清单：返回当前全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": MODULE, "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条绿地明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"绿地 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条绿地；缺字段时点明少了哪一项，面积非数字也直接指出。"""
    entry, missing, notice = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    if entry is None:
        return ActionResult(ok=False, message=notice or "绿地登记失败")
    return ActionResult(ok=True, message=notice or "绿地已登记，等待接管", entry=entry)


@router.put("/{entry_id}", response_model=ActionResult)
def update_entry(
    entry_id: int,
    payload: EntryPayload,
    x_operator_name: str | None = Header(default=None),
    x_operator_role: str | None = Header(default=None),
    x_operator_dept: str | None = Header(default=None),
) -> ActionResult:
    """补全/修改接管信息：只有本部门管养员能改，缺项同样逐项点明。"""
    operator = _operator(
        payload, (x_operator_name, x_operator_role, x_operator_dept)
    )
    try:
        entry, missing, notice = service.update_entry(entry_id, payload.values, operator=operator)
    except PermissionError as exc:
        return ActionResult(ok=False, message=str(exc))
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    if entry is None:
        return ActionResult(ok=False, message=notice or "接管信息保存失败")
    return ActionResult(ok=True, message=notice or "接管信息已保存", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(
    entry_id: int,
    payload: EntryPayload,
    x_operator_name: str | None = Header(default=None),
    x_operator_role: str | None = Header(default=None),
    x_operator_dept: str | None = Header(default=None),
) -> ActionResult:
    """接管登记/确认移交：仅本部门管养员可操作，状态只能依次推进，已移交不可再接。"""
    action = str(payload.values.get("action") or "").strip()
    operator = _operator(
        payload, (x_operator_name, x_operator_role, x_operator_dept)
    )
    try:
        entry, message = service.run_action(entry_id, action, operator=operator)
    except PermissionError as exc:
        return ActionResult(ok=False, message=str(exc))
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
