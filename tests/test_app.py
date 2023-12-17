from unittest.mock import mock_open, MagicMock, patch, AsyncMock
import httpx
import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException

from server.api.weather import (
    PrimaryForecastHandler,
    ReserveForecastHandler,
    WeekAveragePrecipitationStrategy,
    WeekAverageTemperatureStrategy,
    ThreeDayTemperatureStrategy,
    FORECAST_PRECISION,
    ForecastContext,
    validate_forecast,
)
from server.app import AppBuilder
from server.asgi import app
from server.api.parents import (
    JSONFileFactory,
    XMLFileFactory,
    YMLFileFactory,
    JSONFileParser,
    XMLFileParser,
    YMLFileParser,
    FileIterator,
)


client = TestClient(app)


@pytest.fixture
def parsed_data():
    return {
        "persons": [
            {
                "name": "Alex",
                "children": [{"name": "Marta"}, {"name": "Vlad"}],
            },
            {
                "name": "Maria",
                "children": [{"name": "Max"}, {"name": "Oliver"}],
            },
        ]
    }


@pytest.fixture
def xml_file_path():
    return "tests/fixtures/list.xml"


@pytest.fixture
def yml_file_path():
    return "tests/fixtures/children.yml"


@pytest.fixture
def json_file_path():
    return "tests/fixtures/subdirectory/report_2029.03.11.json"


@pytest.mark.parametrize(
    "factory_class, valid_file, invalid_file, parser_class",
    [
        (JSONFileFactory, "test.json", "test.xml", JSONFileParser),
        (XMLFileFactory, "test.xml", "test.json", XMLFileParser),
        (YMLFileFactory, "test.yaml", "test.xml", YMLFileParser),
    ],
)
def test_file_factories(factory_class, valid_file, invalid_file, parser_class):
    factory = factory_class()

    assert factory.is_correct_format(valid_file)
    assert not factory.is_correct_format(invalid_file)

    assert isinstance(factory.create_parser(), parser_class)


@pytest.mark.parametrize(
    "file_path, parser_cls",
    [
        (
            # pylint: disable=no-member
            pytest.lazy_fixture('xml_file_path'),
            XMLFileParser,
        ),
        (
            # pylint: disable=no-member
            pytest.lazy_fixture('yml_file_path'),
            YMLFileParser,
        ),
        (
            # pylint: disable=no-member
            pytest.lazy_fixture('json_file_path'),
            JSONFileParser,
        ),
    ],
)
def test_file_parser(file_path, parser_cls, parsed_data):
    parser = parser_cls()
    result = parser.parse(file_path)
    assert result == parsed_data


def test_file_generator(xml_file_path, yml_file_path, json_file_path):
    expected_files = {xml_file_path, yml_file_path, json_file_path}
    root_directory = 'tests/fixtures'
    file_iterator = FileIterator(root_directory, [])
    found_files = set(file_iterator._file_generator(root_directory))

    assert found_files == expected_files


def test_find_parent():
    response = client.get("/api/v1/parents/Marta")
    assert response.status_code == 200
    data = response.json()
    assert "found_parents" in data
    assert ["Alex"] * 3 == data["found_parents"]

    response = client.get("/api/v1/parents/Joe")
    assert response.status_code == 200
    data = response.json()
    assert "found_parents" in data
    assert [] == data["found_parents"]

    # Проверка для другого ребенка
    response = client.get("/api/v1/parents/Oliver")
    assert response.status_code == 200
    data = response.json()
    assert "found_parents" in data
    assert ["Maria"] * 3 == data["found_parents"]


def test_file_iterator_with_invalid_file():
    mocked_files = [
        ('tests/fixtures', [], ['invalid.json', 'invalid.xml', 'invalid.yml'])
    ]
    mocked_content = "{invalid_data: ]}"

    with patch('os.walk', return_value=mocked_files):
        with patch('builtins.open', mock_open(read_data=mocked_content)):
            file_iterator = FileIterator(
                'tests/fixtures',
                [JSONFileFactory(), XMLFileFactory(), YMLFileFactory()],
            )
            found_data = []

            for data in file_iterator:
                if data is not None:
                    found_data.append(data)

            assert not found_data


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'handler, mock_data',
    [
        (
            PrimaryForecastHandler(),
            [{'temperature': 290, 'precipitation': 20}],
        ),
        (ReserveForecastHandler(), [{'data': '29.0C:0.2'}]),
    ],
)
async def test_forecast_handler_success(handler, mock_data):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value=mock_data)

    with patch('httpx.AsyncClient.get', return_value=mock_response):
        result = await handler.get_month_forecast()
        expected_result = [{'temperature': 29.0, 'precipitation': 0.2}]
        assert result == expected_result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'handler',
    [
        PrimaryForecastHandler(),
        ReserveForecastHandler(),
    ],
)
async def test_forecast_handler_failure(handler):
    with patch(
        'httpx.AsyncClient.get',
        side_effect=httpx.RequestError(
            message="Test Request Error", request=None
        ),
    ):
        result = await handler.get_month_forecast()
        assert result is None


@pytest.fixture
def mock_forecast_data():
    return [
        {'temperature': 10, 'precipitation': 0.2},
        {'temperature': 12, 'precipitation': 0.3},
        {'temperature': 11, 'precipitation': 0.1},
        {'temperature': 9, 'precipitation': 0.2},
        {'temperature': 8, 'precipitation': 0.4},
        {'temperature': 7, 'precipitation': 0.3},
        {'temperature': 6, 'precipitation': 0.2},
        {'temperature': 5, 'precipitation': 0.1},
        {'temperature': 4, 'precipitation': 0.2},
    ]


@pytest.mark.asyncio
async def test_three_day_temperature_strategy(mock_forecast_data):
    handler = MagicMock()
    handler.get_month_forecast = AsyncMock(
        return_value=mock_forecast_data[:10]
    )

    strategy = ThreeDayTemperatureStrategy()
    result = await strategy.get_forecast(handler)
    expected_result = [10, 12, 11]
    assert result == expected_result

    handler.get_month_forecast = AsyncMock(return_value=None)
    result = await strategy.get_forecast(handler)
    assert result is None


@pytest.mark.asyncio
async def test_week_average_temperature_strategy(mock_forecast_data):
    handler = MagicMock()
    handler.get_month_forecast = AsyncMock(return_value=mock_forecast_data[:7])

    strategy = WeekAverageTemperatureStrategy()
    result = await strategy.get_forecast(handler)
    expected_result = round(
        sum(day['temperature'] for day in mock_forecast_data[:7]) / 7,
        FORECAST_PRECISION,
    )
    assert result == expected_result

    handler.get_month_forecast = AsyncMock(return_value=None)
    result = await strategy.get_forecast(handler)
    assert result is None


@pytest.mark.asyncio
async def test_week_average_precipitation_strategy(mock_forecast_data):
    handler = MagicMock()
    handler.get_month_forecast = AsyncMock(return_value=mock_forecast_data[:7])

    strategy = WeekAveragePrecipitationStrategy()
    result = await strategy.get_forecast(handler)
    expected_result = round(
        sum(day['precipitation'] for day in mock_forecast_data[:7]) / 7,
        FORECAST_PRECISION,
    )
    assert result == expected_result

    handler.get_month_forecast = AsyncMock(return_value=None)
    result = await strategy.get_forecast(handler)
    assert result is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "strategy, expected_result",
    [
        (ThreeDayTemperatureStrategy(), [10, 12, 11]),
        (WeekAverageTemperatureStrategy(), 9.0),
        (WeekAveragePrecipitationStrategy(), 0.24),
    ],
)
async def test_forecast_context(strategy, expected_result, mock_forecast_data):
    handler = MagicMock()
    handler.get_month_forecast = AsyncMock(return_value=mock_forecast_data)

    context = ForecastContext(strategy, handler)
    result = await context.forecast()
    assert result == expected_result


def test_validate_forecast():
    forecast = None
    with pytest.raises(HTTPException) as exc_info:
        validate_forecast(forecast)
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Forecast not found"


def test_weather_report_3days():
    with patch(
        'server.api.weather.ForecastContext.forecast',
        return_value=[20, 22, 21],
    ):
        response = client.get("/api/v1/weather/3days")
        assert response.status_code == 200
        assert response.json() == {"forecast_d3": [20, 22, 21]}


def test_weather_report_week_avg_temp():
    with patch('server.api.weather.ForecastContext.forecast', return_value=21):
        response = client.get("/api/v1/weather/week_avg_temp")
        assert response.status_code == 200
        assert response.json() == {"forecast_d1": 21}


def test_weather_report_week_avg_prec():
    with patch(
        'server.api.weather.ForecastContext.forecast', return_value=0.1
    ):
        response = client.get("/api/v1/weather/week_avg_precip")
        assert response.status_code == 200
        assert response.json() == {"forecast_pp": 0.1}


def test_weather_report_primary_server_down(mock_forecast_data):
    with patch(
        'httpx.AsyncClient.get', return_value=httpx.Response(status_code=404)
    ), patch(
        'server.api.weather.ReserveForecastHandler.get_month_forecast',
        return_value=mock_forecast_data,
    ):
        response = client.get("/api/v1/weather/3days")
        assert response.status_code == 200
        assert response.json() == {"forecast_d3": [10, 12, 11]}


def test_weather_report_both_servers_down():
    with patch(
        'httpx.AsyncClient.get', return_value=httpx.Response(status_code=404)
    ):
        response = client.get("/api/v1/weather/3days")
        assert response.status_code == 404
        assert response.json() == {"detail": "Forecast not found"}


def test_set_api_prefix():
    builder = AppBuilder()
    builder.set_api_prefix('/api/test')
    assert builder._api_prefix == '/api/test'


def test_enable_file_logging():
    builder = AppBuilder()
    builder.enable_file_logging('test.log', 'INFO')
    assert builder._log_to_file is True
    assert builder._log_file_path == 'test.log'
    assert builder._file_log_level == 'INFO'
