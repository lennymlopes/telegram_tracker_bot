import requests
from bs4 import BeautifulSoup
import re

def get_jobs():
    try:
        response = requests.get("https://www.init7.net/de/init7/jobs/")
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        job_links = soup.find_all('a', href=re.compile(r'/de/init7/jobs/[^/]+/$'))

        jobs = []

        for link in job_links:
            job_name = link.get_text().strip()
            job_url = link.get('href')

            if job_url.startswith('/'):
                job_url = 'https://www.init7.net' + job_url

            # Skip benefits link
            if 'benefits' not in job_url.lower():
                jobs.append({
                    'name': job_name,
                    'url': job_url
                })

        return jobs

    except requests.RequestException as e:
        print(f"Error fetching the page: {e}")
        return []
    except Exception as e:
        print(f"Error parsing the page: {e}")
        return []