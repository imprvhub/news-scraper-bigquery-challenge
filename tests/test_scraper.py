import datetime
import sys
from dataclasses import dataclass
from unittest.mock import MagicMock, patch
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
import pytest

sys.modules['google'] = MagicMock()
sys.modules['google.cloud'] = MagicMock()
sys.modules['google.cloud.bigquery'] = MagicMock()

@dataclass
class Article:
    title: str
    kicker: str
    link: str
    image: str
    scrape_date: str = None

    def __post_init__(self):
        self.scrape_date = datetime.now().isoformat()

class TestNewsScraperProcessor:
    @pytest.fixture(autouse=True)
    def mock_dependencies(self):
        with patch('google.cloud.bigquery', MagicMock()), \
             patch('selenium.webdriver.Chrome', MagicMock()), \
             patch('pandas.DataFrame', MagicMock()):
            yield

    @pytest.fixture
    def scraper(self):
        from scraper import NewsScraperProcessor
        return NewsScraperProcessor()

    @pytest.fixture
    def mock_driver(self):
        with patch('selenium.webdriver.Chrome') as mock:
            yield mock.return_value

    @pytest.fixture
    def sample_article(self):
        return Article(
            title="Test Article",
            kicker="Test Kicker",
            link="https://example.com",
            image="https://example.com/image.jpg"
        )

    def test_configure_chrome_options(self, scraper):
        options = scraper._configure_chrome_options()
        assert '--headless' in options.arguments
        assert '--no-sandbox' in options.arguments
        assert any('user-agent' in arg for arg in options.arguments)

    def test_safe_find_element_with_no_such_element(self, scraper):
        mock_container = MagicMock()
        mock_container.find_element.side_effect = NoSuchElementException()
        result = scraper._safe_find_element(mock_container, "class name", "test-class")
        assert result == ""

    def test_safe_find_element_success(self, scraper):
        mock_container = MagicMock()
        mock_element = MagicMock()
        mock_element.text = "Test Text"
        mock_container.find_element.return_value = mock_element
        result = scraper._safe_find_element(mock_container, "class name", "test-class")
        assert result == "Test Text"

    @pytest.mark.parametrize("exception", [TimeoutException, WebDriverException])
    def test_scrape_news_with_exceptions(self, scraper, mock_driver, exception):
        mock_driver.get.side_effect = exception()
        with pytest.raises(exception):
            scraper.scrape_news()

    def test_process_data_with_empty_articles(self, scraper):
        result = scraper.process_data([])
        assert result is None

    def test_article_post_init(self):
        article = Article(
            title="Test",
            kicker="Test",
            link="https://example.com",
            image="https://example.com/image.jpg"
        )
        assert article.scrape_date is not None
        assert isinstance(datetime.fromisoformat(article.scrape_date), datetime)

    @pytest.mark.parametrize("test_input,expected", [
        ({"title": "Test Title", "kicker": "Test", "link": "https://example.com", "image": "test.jpg"}, True),
        ({"title": "", "kicker": "Test", "link": "https://example.com", "image": "test.jpg"}, False),
    ])
    def test_article_validation(self, test_input, expected):
        article = Article(**test_input)
        assert bool(article.title) == expected

    def test_timeout_exception_handling(self, scraper, mock_driver):
        mock_driver.get.side_effect = TimeoutException("Timeout")
        with pytest.raises(TimeoutException):
            scraper.scrape_news()

    def test_webdriver_exception_handling(self, scraper, mock_driver):
        mock_driver.get.side_effect = WebDriverException("WebDriver Error")
        with pytest.raises(WebDriverException):
            scraper.scrape_news()