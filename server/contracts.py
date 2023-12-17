from pydantic import BaseModel


class ThreeDayTemperature(BaseModel):
    forecast_d3: list[float]


class WeekAverageTemperature(BaseModel):
    forecast_d1: float


class WeekAveragePrecipitation(BaseModel):
    forecast_pp: float


class SearchResult(BaseModel):
    found_parents: list[str]
