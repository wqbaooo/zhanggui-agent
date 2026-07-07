from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

from config import AMAP_WEBSERVICE_KEY

router = APIRouter(prefix="/amap", tags=["高德地图"])


class GeocodeRequest(BaseModel):
    address: str = Field(..., description="地址")
    city: Optional[str] = Field(None, description="城市")


class GeocodeResponse(BaseModel):
    formatted_address: str = Field(..., description="格式化地址")
    province: str = Field(..., description="省份")
    city: str = Field(..., description="城市")
    district: str = Field(..., description="区县")
    location: str = Field(..., description="经纬度")
    level: str = Field(..., description="精度级别")


@router.post("/geocode", response_model=GeocodeResponse)
def geocode(request: GeocodeRequest):
    if not AMAP_WEBSERVICE_KEY:
        raise HTTPException(status_code=500, detail="未配置高德地图API Key")

    try:
        from amap_tool import AmapTool
        tool = AmapTool(key=AMAP_WEBSERVICE_KEY)
        result = tool.geocode(request.address, request.city)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class LocationInfo(BaseModel):
    address: str = Field(..., description="店铺地址")
    city: Optional[str] = Field(None, description="城市")


@router.post("/location-info")
def get_location_info(request: LocationInfo):
    if not AMAP_WEBSERVICE_KEY:
        raise HTTPException(status_code=500, detail="未配置高德地图API Key")

    try:
        from amap_tool import AmapTool
        tool = AmapTool(key=AMAP_WEBSERVICE_KEY)
        geo_result = tool.geocode(request.address, request.city)

        location = geo_result.get("location", "")
        if location:
            competitors = tool.search_around(location, "章鱼烧", radius=500)
            anchors = []
            for kw in ["商场", "超市", "地铁站", "公交站"]:
                pois = tool.search_around(location, kw, radius=500)
                if pois:
                    anchors.extend(pois[:3])
        else:
            competitors = []
            anchors = []

        return {
            "geocode": geo_result,
            "competitors_count": len(competitors),
            "nearby_anchors": [{"name": poi.name, "type": poi.type, "distance": poi.distance} for poi in anchors[:10]],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))