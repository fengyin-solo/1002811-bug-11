"""接管/移交操作的身份与班组权限。

前端通过请求头带上当前值班人身份；写操作必须是本部门的管养员，
且班组与绿地接管班组一致，其他班组只能查看，不能改动。
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import unquote

from fastapi import Header, HTTPException

GARDENER_ROLE = "管养员"


@dataclass(frozen=True)
class Operator:
    name: str
    role: str
    team: str


def _decode(value: str | None) -> str:
    """前端对中文身份字段做了百分号编码，这里还原成可读文本。"""
    return unquote(value or "").strip()


def current_operator(
    name: str | None = Header(default=None, alias="X-Operator-Name"),
    role: str | None = Header(default=None, alias="X-Operator-Role"),
    team: str | None = Header(default=None, alias="X-Operator-Team"),
) -> Operator:
    """从请求头解析当前操作人；头缺失时视为匿名，写操作会被拦下。"""
    return Operator(name=_decode(name), role=_decode(role), team=_decode(team))


def require_gardener(operator: Operator, team: str | None = None) -> None:
    """校验接管信息改动权限。

    team 为 None 时只要求是管养员（用于登记新绿地）；
    传入绿地接管班组时，还必须是同一班组。
    """
    if operator.role != GARDENER_ROLE:
        raise HTTPException(status_code=403, detail="只有本部门的管养员才能改动接管信息")
    if team is not None and operator.team != team:
        raise HTTPException(status_code=403, detail=f"该绿地由{team}接管，其他班组无权改动")
