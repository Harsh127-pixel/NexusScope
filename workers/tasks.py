import time
from celery_app import celery_app
from shared.schemas import InvestigationTask
import dns.resolver
from bs4 import BeautifulSoup
import requests
import exifread
# from playwright.sync_api import sync_playwright # Uncomment in worker Dockerfile after install

@celery_app.task(name="tasks.perform_dns_lookup")
def perform_dns_lookup(domain: str):
    """Perform DNS intelligence gathering."""
    results = {"domain": domain, "records": {}}
    record_types = ['A', 'MX', 'TXT', 'NS']
    
    for record in record_types:
        try:
            answers = dns.resolver.resolve(domain, record)
            results["records"][record] = [str(r) for r in answers]
        except Exception as e:
            results["records"][record] = f"Error: {str(e)}"
            
    return results

@celery_app.task(name="tasks.scrape_web_intelligence")
def scrape_web_intelligence(url: str):
    """Scrape web metadata and technology stack."""
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        return {
            "url": url,
            "title": soup.title.string if soup.title else "No Title",
            "meta_description": soup.find("meta", attrs={"name": "description"}).get("content", "") if soup.find("meta", attrs={"name": "description"}) else "",
            "server": response.headers.get("Server", "Unknown")
        }
    except Exception as e:
        return {"url": url, "error": str(e)}

@celery_app.task(name="tasks.analyze_image_metadata")
def analyze_image_metadata(image_url: str):
    """Extract Exif metadata from image."""
    try:
        # Simplified for demonstration
        return {"image_url": image_url, "metadata": "Processing logic placeholder"}
    except Exception as e:
        return {"error": str(e)}
