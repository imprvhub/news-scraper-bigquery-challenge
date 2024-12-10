import logging
import os
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
from google.cloud import bigquery
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class Article:
    """Data class to store article information"""
    title: str
    kicker: str
    link: str
    image: str
    scrape_date: str = None

    def __post_init__(self):
        self.scrape_date = datetime.now().isoformat()

class NewsScraperProcessor:
    def __init__(self):
        self.base_url = "https://www.yogonet.com/international/"
        self.chrome_options = self._configure_chrome_options()
        self.max_retries = 3
        self.retry_delay = 5

    def _configure_chrome_options(self) -> Options:
        """Configure Chrome options for headless browsing"""
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-notifications')
        options.add_argument('--disable-software-rasterizer')
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36')
        return options

    @contextmanager
    def _create_driver(self):
        """Context manager for creating and managing the WebDriver"""
        driver = None
        try:
            service = Service()
            driver = webdriver.Chrome(service=service, options=self.chrome_options)
            driver.set_page_load_timeout(30)
            yield driver
        finally:
            if driver:
                driver.quit()

    def _safe_find_element(self, container, by, value, default=""):
        """Safely find an element and return its text or attribute"""
        try:
            element = container.find_element(by, value)
            return element.text.strip() if by != By.TAG_NAME else element.get_attribute("src")
        except NoSuchElementException:
            return default
        except Exception as e:
            logger.debug(f"Error finding element {value}: {str(e)}")
            return default

    def scrape_news(self) -> List[Article]:
        """Main scraping method with retry mechanism"""
        for attempt in range(self.max_retries):
            try:
                articles = self._scrape_with_selenium()
                if articles:
                    return articles
                logger.warning(f"Attempt {attempt + 1} yielded no articles")
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < self.max_retries - 1:
                    logger.info(f"Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                else:
                    logger.error("All retry attempts failed")
                    raise
        return []

    def _get_article_kicker(self, driver, url: str) -> str:
        """Get kicker from individual article page if needed"""
        try:
            driver.get(url)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "volanta_noticia"))
            )

            kicker_selectors = [
                (By.CLASS_NAME, "volanta_noticia"),
                (By.CLASS_NAME, "volanta_noticia fuente_roboto_slab"),
                (By.CSS_SELECTOR, ".slot.contenido_fijo.titulo_de_noticia .volanta_noticia"),
                (By.CSS_SELECTOR, ".titulo_de_noticia .volanta_noticia")
            ]
            
            for selector in kicker_selectors:
                try:
                    element = driver.find_element(*selector)
                    kicker_text = element.text.strip()
                    if kicker_text:
                        return kicker_text
                except NoSuchElementException:
                    continue
                
            return ""
        except Exception as e:
            logger.error(f"Error getting article kicker from {url}: {str(e)}")
            return ""

    def _scrape_with_selenium(self) -> List[Article]:
        """Scrape articles using Selenium with protection against stale elements"""
        articles = []
        
        with self._create_driver() as driver:
            try:
                logger.info(f"Accessing URL: {self.base_url}")
                try:
                    driver.get(self.base_url)
                except TimeoutException:
                    logger.error(f"Timeout while accessing {self.base_url}")
                    raise
                except WebDriverException as e:
                    logger.error(f"WebDriver error while accessing {self.base_url}: {str(e)}")
                    raise

                try:
                    WebDriverWait(driver, 20).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "contenedor_dato_modulo"))
                    )
                except TimeoutException:
                    logger.error("Timeout waiting for article containers to load")
                    raise

                article_data = []
                article_containers = driver.find_elements(By.CLASS_NAME, "contenedor_dato_modulo")
                logger.info(f"Found {len(article_containers)} news items")
                
                for container in article_containers:
                    try:
                        article_info = {
                            'title': '',
                            'link': '',
                            'kicker': '',
                            'image': ''
                        }
                        
                        try:
                            link_element = container.find_element(By.CLASS_NAME, "titulo").find_element(By.TAG_NAME, "a")
                            article_info['title'] = link_element.text.strip()
                            article_info['link'] = link_element.get_attribute("href")
                        except NoSuchElementException:
                            continue
                        
                        if not article_info['title']:
                            continue

                        kicker_selectors = [
                            (By.CLASS_NAME, "volanta"),
                            (By.CLASS_NAME, "volanta fuente_roboto_slab"),
                            (By.CLASS_NAME, "volanta_noticia"),
                            (By.CLASS_NAME, "volanta_noticia fuente_roboto_slab"),
                            (By.CSS_SELECTOR, ".volanta_titulo .volanta"),
                            (By.CSS_SELECTOR, "div.volanta")
                        ]

                        for selector in kicker_selectors:
                            try:
                                element = container.find_element(*selector)
                                kicker_text = element.text.strip()
                                if kicker_text:
                                    article_info['kicker'] = kicker_text
                                    break
                            except NoSuchElementException:
                                continue
                        article_info['image'] = self._safe_find_element(container, By.TAG_NAME, "img")
                        
                        article_data.append(article_info)
                        
                    except Exception as e:
                        logger.error(f"Error extracting initial article data: {str(e)}")
                        continue
                
                for article_info in article_data:
                    try:
                        if not article_info['kicker'] and article_info['link']:
                            logger.info(f"No kicker found in main page for {article_info['title'][:50]}... Checking article page...")
                            
                            try:
                                driver.get(article_info['link'])
                            except TimeoutException:
                                logger.error(f"Timeout while accessing article page: {article_info['link']}")
                                continue
                            except WebDriverException as e:
                                logger.error(f"WebDriver error while accessing article page: {str(e)}")
                                continue

                            try:
                                WebDriverWait(driver, 10).until(
                                    EC.presence_of_element_located((By.CLASS_NAME, "contenido_noticia"))
                                )
                            except TimeoutException:
                                logger.error(f"Timeout waiting for article content to load: {article_info['link']}")
                                continue

                            article_kicker_selectors = [
                                (By.CLASS_NAME, "volanta_noticia"),
                                (By.CLASS_NAME, "volanta_noticia fuente_roboto_slab"),
                                (By.CSS_SELECTOR, ".slot.contenido_fijo.titulo_de_noticia .volanta_noticia"),
                                (By.CSS_SELECTOR, ".titulo_de_noticia .volanta_noticia")
                            ]
                            
                            for selector in article_kicker_selectors:
                                try:
                                    element = driver.find_element(*selector)
                                    kicker_text = element.text.strip()
                                    if kicker_text:
                                        article_info['kicker'] = kicker_text
                                        break
                                except NoSuchElementException:
                                    continue
                        article = Article(
                            title=article_info['title'],
                            kicker=article_info['kicker'],
                            link=article_info['link'],
                            image=article_info['image']
                        )
                        articles.append(article)
                        logger.info(f"Processed article: {article_info['title'][:50]}... | Kicker: {article_info['kicker'][:50]}...")
                        
                    except Exception as e:
                        logger.error(f"Error processing article page: {str(e)}")
                        continue
                        
            except Exception as e:
                logger.error(f"Error during scraping: {str(e)}")
                raise
                    
            return articles
        
    def process_data(self, articles: List[Article]) -> Optional[pd.DataFrame]:
        """Process scraped articles and compute metrics"""
        if not articles:
            logger.error("No articles to process")
            return None
            
        df = pd.DataFrame([vars(article) for article in articles])

        df['title_word_count'] = df['title'].str.split().str.len()
        df['title_char_count'] = df['title'].str.len()
        df['capital_words'] = df['title'].apply(
            lambda x: [word for word in x.split() if word and word[0].isupper()]
        )
        
        return df

    def upload_to_bigquery(self, df: pd.DataFrame) -> bool:
        """Upload processed data to BigQuery"""
        if df is None or df.empty:
            logger.error("No data to upload to BigQuery")
            return False
            
        try:
            client = bigquery.Client()
            table_ref = f"{os.getenv('GCP_PROJECT_ID')}.{os.getenv('BQ_DATASET_ID')}.{os.getenv('BQ_TABLE_ID')}"

            job_config = bigquery.LoadJobConfig(
                write_disposition="WRITE_APPEND",
                schema_update_options=[
                    bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION
                ]
            )
            
            job = client.load_table_from_dataframe(
                df, table_ref, job_config=job_config
            )
            job.result() 
            
            logger.info(f"Successfully uploaded {len(df)} rows to BigQuery")
            return True
            
        except Exception as e:
            logger.error(f"Error uploading to BigQuery: {str(e)}")
            return False
        
    def save_to_csv(self, df: pd.DataFrame) -> None:
        """Save DataFrame to CSV with timestamp"""
        try:
            output_dir = "/app/output"
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
                
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"news_scraper_results_{timestamp}.csv"
            filepath = os.path.join(output_dir, filename)
            
            print(f"\nAttempting to save CSV to: {filepath}")
            df.to_csv(filepath, index=False)
            
            if os.path.exists(filepath):
                print(f"File successfully created. Size: {os.path.getsize(filepath)} bytes")
                print(f"Contents of {output_dir}: {os.listdir(output_dir)}")
            
        except Exception as e:
            print(f"Error saving CSV: {e}")
            raise

def main():
    try:
        scraper = NewsScraperProcessor()
        logger.info("Starting news scraping...")
        
        articles = scraper.scrape_news()
        
        if articles:
            logger.info(f"Successfully scraped {len(articles)} articles")
            df = scraper.process_data(articles)
            
            if df is not None:
                success = scraper.upload_to_bigquery(df)
                
                if not success:
                    logger.error("Failed to upload data to BigQuery")
                    sys.exit(1)
                
                scraper.save_to_csv(df)

                print("\nSample of processed articles:")
                print(df[['title', 'kicker', 'title_word_count', 'title_char_count']].head())
                print("\nExample of capital words in first article:", df['capital_words'].iloc[0])
        else:
            logger.error("No articles were scraped")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Main process error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
