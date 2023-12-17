from __future__ import annotations

from typing import Any

from abc import ABC, abstractmethod

from fastapi import APIRouter, HTTPException

import httpx
from server import contracts


router = APIRouter()

PRIMARY_WEATHER_SERVER_URL = "http://weather_server:8080/api/"
RESERVE_WEATHER_SERVER_URL = "http://reserve_weather_server:8081/weather/month"
FORECAST_PRECISION = 2


class ForecastHandler(ABC):
    _next_handler: ForecastHandler | None = None

    def set_next(self, forecast_handler: ForecastHandler) -> ForecastHandler:
        self._next_handler = forecast_handler
        return forecast_handler

    @abstractmethod
    async def get_month_forecast(self) -> list[dict] | None:
        if self._next_handler:
            return await self._next_handler.get_month_forecast()
        return None


class PrimaryForecastHandler(ForecastHandler):
    async def get_month_forecast(self) -> list[dict] | None:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(PRIMARY_WEATHER_SERVER_URL)

                if response.status_code != httpx.codes.OK:
                    return await super().get_month_forecast()

                data = response.json()
                for day in data:
                    day['temperature'] = day['temperature'] / 10
                    day['precipitation'] = day['precipitation'] / 100
                return data

        except httpx.RequestError:
            return await super().get_month_forecast()


class ReserveForecastHandler(ForecastHandler):
    async def get_month_forecast(self) -> list[dict] | None:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(RESERVE_WEATHER_SERVER_URL)

                if response.status_code != httpx.codes.OK:
                    return await super().get_month_forecast()

                data = response.json()
                result = []
                for day in data:
                    temperature, precipitation = day['data'].split(':')
                    temperature = float(temperature.rstrip('C'))
                    precipitation = float(precipitation)
                    result.append(
                        {
                            'temperature': temperature,
                            'precipitation': precipitation,
                        }
                    )
                return result

        except httpx.RequestError:
            return await super().get_month_forecast()


class ForecastStrategy(ABC):
    @abstractmethod
    async def get_forecast(
        self, forecast_provider: ForecastHandler
    ) -> Any | None:
        pass  # pragma no cover


class ThreeDayTemperatureStrategy(ForecastStrategy):
    async def get_forecast(
        self, forecast_provider: ForecastHandler
    ) -> list[float] | None:
        month_forecast = await forecast_provider.get_month_forecast()
        if month_forecast is None:
            return None
        three_day_forecast = month_forecast[:3]
        return [day['temperature'] for day in three_day_forecast]


class WeekAverageTemperatureStrategy(ForecastStrategy):
    async def get_forecast(
        self, forecast_provider: ForecastHandler
    ) -> float | None:
        month_forecast = await forecast_provider.get_month_forecast()
        if month_forecast is None:
            return None
        seven_day_forecast = month_forecast[:7]
        avg_temp = sum(day['temperature'] for day in seven_day_forecast) / len(
            seven_day_forecast
        )
        return round(avg_temp, FORECAST_PRECISION)


class WeekAveragePrecipitationStrategy(ForecastStrategy):
    async def get_forecast(
        self, forecast_provider: ForecastHandler
    ) -> float | None:
        month_forecast = await forecast_provider.get_month_forecast()
        if month_forecast is None:
            return None
        seven_day_forecast = month_forecast[:7]
        avg_precip = sum(
            day['precipitation'] for day in seven_day_forecast
        ) / len(seven_day_forecast)
        return round(avg_precip, FORECAST_PRECISION)


class ForecastContext:
    def __init__(
        self, strategy: ForecastStrategy, forecast_handler: ForecastHandler
    ) -> None:
        self._strategy = strategy
        self.forecast_handler = forecast_handler

    async def forecast(self) -> Any | None:
        return await self._strategy.get_forecast(self.forecast_handler)


primary_handler = PrimaryForecastHandler()
reserve_handler = ReserveForecastHandler()
primary_handler.set_next(reserve_handler)


def validate_forecast(forecast: Any | None) -> None:
    if forecast is None:
        raise HTTPException(
            status_code=404,
            detail="Forecast not found",
        )


@router.get("/weather/3days")
async def weather_report_3days() -> contracts.ThreeDayTemperature:
    context = ForecastContext(ThreeDayTemperatureStrategy(), primary_handler)
    forecast = await context.forecast()
    validate_forecast(forecast)
    return contracts.ThreeDayTemperature(forecast_d3=forecast)


@router.get("/weather/week_avg_temp")
async def weather_report_week_avg_temp() -> contracts.WeekAverageTemperature:
    context = ForecastContext(
        WeekAverageTemperatureStrategy(), primary_handler
    )
    forecast = await context.forecast()
    validate_forecast(forecast)
    return contracts.WeekAverageTemperature(forecast_d1=forecast)


@router.get("/weather/week_avg_precip")
async def weather_report_week_avg_prec() -> contracts.WeekAveragePrecipitation:
    context = ForecastContext(
        WeekAveragePrecipitationStrategy(), primary_handler
    )
    forecast = await context.forecast()
    validate_forecast(forecast)
    return contracts.WeekAveragePrecipitation(forecast_pp=forecast)
