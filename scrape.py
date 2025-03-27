# import time
# from selenium import webdriver
# from selenium.webdriver.chrome.service import Service
# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# from webdriver_manager.chrome import ChromeDriverManager

# def scrape_jobs():
#     # Set up Chrome options (uncomment headless mode if desired)
#     options = webdriver.ChromeOptions()
#     # options.add_argument('--headless')  # Uncomment for headless mode
#     options.add_argument('--no-sandbox')
#     options.add_argument('--disable-dev-shm-usage')
    
#     # Initialize the Chrome driver using webdriver-manager
#     driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
#     wait = WebDriverWait(driver, 20)
    
#     # URL of the careers page
#     # url = "https://www.google.com/about/careers/applications/jobs/results/"
#     url = "https://www.google.com/about/careers/applications/jobs/results/?location=India&target_level=EARLY&target_level=INTERN_AND_APPRENTICE"
#     driver.get(url)
    
#     # Wait until at least one "Learn more" button is present
#     wait.until(EC.presence_of_all_elements_located((By.XPATH, "//span[text()='Learn more']")))
    
#     # Find all <a> tags that follow a "Learn more" span.
#     # This assumes that each "Learn more" span is immediately followed by an <a> with the job link.
#     learn_more_links = driver.find_elements(By.XPATH, "//span[text()='Learn more']/following-sibling::a")
    
#     jobs = []
#     print(f"Found {len(learn_more_links)} job links to process.")
    
#     for link_elem in learn_more_links:
#         job_link = link_elem.get_attribute("href")
#         if not job_link:
#             continue
        
#         # Open the job link in a new tab
#         driver.execute_script("window.open(arguments[0]);", job_link)
#         driver.switch_to.window(driver.window_handles[-1])
        
#         try:
#             # Wait until the job detail page loads and the job name element is available.
#             job_name_elem = wait.until(
#                 EC.presence_of_element_located((By.CSS_SELECTOR, "div.sPeqm h2.p1N2lc"))
#             )
#             job_name = job_name_elem.text
#             print(f"Scraped: {job_name} - {job_link}")
#             jobs.append({"job_name": job_name, "job_link": driver.current_url})
#         except Exception as e:
#             print(f"Error processing {job_link}: {e}")
        
#         # Close the current tab and switch back to the main listing page
#         driver.close()
#         driver.switch_to.window(driver.window_handles[0])
    
#     driver.quit()
#     return jobs

# if __name__ == '__main__':
#     job_list = scrape_jobs()
#     print("Final job data:")
#     for job in job_list:
#         print(job)



# {
#     "domain":"google",
#     "job_id":"232342342342342",
#     "job_name":"Software Engineer II",
#    "job_link" :"https://www.google.com/about/careers/applications/jobs/results/129411685923332806-software-engineer-ii-full-stack-platforms-and-ecosystems?location=India&target_level=EARLY&target_level=INTERN_AND_APPRENTICE"

# },

# {
#         domain:"google",
#     job_id:"545334433323",
# },

# {
#         domain:"google",
#     job_id:"857584748478",
# },

import re
import time
from urllib.parse import urlparse

from pymongo import MongoClient
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


# ---------------- Helper Functions ----------------

def domain_extractor(url):
    """
    Extracts the second-level domain (e.g., "google" or "microsoft") from a URL.
    """
    parsed = urlparse(url)
    parts = parsed.netloc.split('.')
    if len(parts) >= 2:
        return parts[-2].lower()
    return parsed.netloc.lower()

def job_id_extractor(url):
    """
    Extracts a numeric job ID from the URL using regex.
    For Google, expects a pattern like /results/<digits>-
    For Microsoft, if no numeric pattern is found, returns None.
    """
    m = re.search(r'/results/(\d+)-', url)
    if m:
        return m.group(1)
    m = re.search(r'/job/(\d+)', url)
    if m:
        return m.group(1)
    return None

def connect_to_db():
    """
    Connects to a local MongoDB server and returns the 'jobs' collection.
    Assumes the server is running at mongodb://localhost:27017.
    """
    client = MongoClient("mongodb://localhost:27017")
    db = client.job_scraper
    return db.jobs

def insert_job_if_not_exists(job_data, collection):
    """
    Inserts a job record into MongoDB if the job_id is not already present.
    Returns True if inserted, False if duplicate.
    """
    if collection.find_one({"job_id": job_data["job_id"]}):
        return False
    collection.insert_one(job_data)
    return True


# ---------------- Scraping Functions ----------------

def scrape_google_jobs(start_url, collection):
    """
    Scrapes job details from a Google careers URL.
    It opens each job's details page (via the "Learn more" link),
    extracts the job name, job ID (via regex on the URL), and then stores the data.
    Pagination is handled by clicking the next page link.
    """
    options = webdriver.ChromeOptions()
    # Uncomment the next line for headless mode:
    # options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    wait = WebDriverWait(driver, 20)
    
    duplicate_count = 0
    driver.get(start_url)
    
    while True:
        try:
            wait.until(EC.presence_of_all_elements_located((By.XPATH, "//span[text()='Learn more']")))
        except Exception as e:
            print(f"[Google] Timeout waiting for jobs on page: {e}")
            break

        learn_more_links = driver.find_elements(By.XPATH, "//span[text()='Learn more']/following-sibling::a")
        print(f"[Google] Found {len(learn_more_links)} job links on current page.")
        
        for link_elem in learn_more_links:
            if duplicate_count >= 5:
                print("[Google] Reached 5 duplicates; stopping scraping for this domain.")
                driver.quit()
                return
            
            job_link = link_elem.get_attribute("href")
            if not job_link:
                continue

            # Open job detail page in a new tab
            driver.execute_script("window.open(arguments[0]);", job_link)
            driver.switch_to.window(driver.window_handles[-1])
            try:
                job_name_elem = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.sPeqm h2.p1N2lc"))
                )
                job_name = job_name_elem.text
                current_url = driver.current_url
                job_id = job_id_extractor(current_url)
                domain = domain_extractor(current_url)
                if not job_id:
                    print(f"[Google] Could not extract job id from {current_url}. Skipping.")
                else:
                    job_data = {
                        "domain": domain,
                        "job_id": job_id,
                        "job_name": job_name,
                        "job_link": current_url
                    }
                    if insert_job_if_not_exists(job_data, collection):
                        print(f"[Google] Inserted: {job_name} - ID: {job_id}")
                    else:
                        duplicate_count += 1
                        print(f"[Google] Duplicate found for job id {job_id} (count={duplicate_count})")
            except Exception as e:
                print(f"[Google] Error processing {job_link}: {e}")
            finally:
                if len(driver.window_handles) > 1:
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
            
        try:
            next_page = driver.find_element(By.CSS_SELECTOR, "a[aria-label='Go to next page']")
            next_url = next_page.get_attribute("href")
            if next_url:
                print(f"[Google] Navigating to next page: {next_url}")
                driver.get(next_url)
                time.sleep(2)
            else:
                print("[Google] Next page URL not found; ending pagination.")
                break
        except Exception as e:
            print(f"[Google] No next page found: {e}")
            break

    driver.quit()


def scrape_microsoft_jobs(base_url, collection):
    """
    Scrapes Microsoft jobs using a base search URL with a page parameter.
    It changes the "pg" value sequentially (e.g. pg=1, pg=2, …) and extracts
    job details from each job card on the page.
    
    Each job card is expected to contain an element with an aria-label that includes
    "Job item <job_id>" and the job name is extracted from an h2 element with class
    "MZGzlrn8gfgSs8TZHhv2". The job link is constructed as:
         https://jobs.careers.microsoft.com/global/en/job/<job_id>
    
    The function stops when no job cards are found.
    """
    import re
    import time
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    # Set up the Selenium driver
    options = webdriver.ChromeOptions()
    # options.add_argument('--headless')  # Uncomment to run headless
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    wait = WebDriverWait(driver, 20)
    
    page = 1
    while True:
        # Construct URL by replacing the pg parameter with the current page number
        current_url = re.sub(r"pg=\d+", f"pg={page}", base_url)
        print(f"[Microsoft] Loading page {page}: {current_url}")
        driver.get(current_url)
        
        try:
            wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.ms-List-cell")))
        except Exception as e:
            print(f"[Microsoft] Timeout waiting for job cards on page {page}: {e}")
            break

        job_cards = driver.find_elements(By.CSS_SELECTOR, "div.ms-List-cell")
        if not job_cards:
            print(f"[Microsoft] No job cards found on page {page}. Ending pagination.")
            break
        print(f"[Microsoft] Found {len(job_cards)} job cards on page {page}.")
        
        for card in job_cards:
            try:
                # Extract the job id from an element with aria-label like "Job item 1781145"
                job_item_elem = card.find_element(By.XPATH, ".//*[contains(@aria-label, 'Job item')]")
                aria_text = job_item_elem.get_attribute("aria-label")
                match = re.search(r'Job item (\d+)', aria_text)
                if match:
                    job_id = match.group(1)
                else:
                    print(f"[Microsoft] Could not extract job id from: {aria_text}")
                    continue

                # Extract the job name from the h2 element
                job_name_elem = card.find_element(By.CSS_SELECTOR, "h2.MZGzlrn8gfgSs8TZHhv2")
                job_name = job_name_elem.text.strip()
                
                domain = domain_extractor(current_url)
                job_link = f"https://jobs.careers.microsoft.com/global/en/job/{job_id}"
                
                job_data = {
                    "domain": domain,
                    "job_id": job_id,
                    "job_name": job_name,
                    "job_link": job_link
                }
                
                if insert_job_if_not_exists(job_data, collection):
                    print(f"[Microsoft] Inserted: {job_name} - ID: {job_id}")
                else:
                    print(f"[Microsoft] Duplicate found for job id {job_id}")
            except Exception as e:
                print(f"[Microsoft] Error processing a job card on page {page}: {e}")
        
        page += 1
        time.sleep(2)
        
    driver.quit()





# ---------------- Main Execution ----------------

def main():
    # Connect to local MongoDB
    collection = connect_to_db()

    # List of start URLs for different domains
    urls = [
        "https://www.google.com/about/careers/applications/jobs/results/?location=India&target_level=EARLY&target_level=INTERN_AND_APPRENTICE",
        "https://jobs.careers.microsoft.com/global/en/search?exp=Students%20and%20graduates&et=Full-Time&et=Internship&l=en_us&pg=1&pgSz=20&o=Relevance&flt=true"
    ]
    
    for url in urls:
        domain = domain_extractor(url)
        print(f"\nStarting scrape for domain: {domain}")
        if "google" in domain:
            # pass
            scrape_google_jobs(url, collection)
        elif "microsoft" in domain:
            # pass
            scrape_microsoft_jobs(url, collection)
        else:
            print(f"No scraper defined for domain: {domain}")

    print("Scraping complete.")

if __name__ == '__main__':
    main()