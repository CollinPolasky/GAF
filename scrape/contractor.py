import time
import os
import json
import csv
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import TimeoutException, NoSuchElementException

class GAFContractorScraper:
    """Scraper for extracting contractor information from GAF's website using Selenium."""
    
    BASE_URL = "https://www.gaf.com/en-us/roofing-contractors/residential"
    
    def __init__(self, zip_code: str = None, distance: int = 25, headless: bool = True, max_pages: int = None):
        """Initialize the scraper with the given zip code and search radius.
        
        Args:
            zip_code: The ZIP code to search around (optional)
            distance: Search radius in miles (default: 25)
            headless: Whether to run Chrome in headless mode (default: True)
            max_pages: Maximum number of pages to scrape (default: None = all pages)
        """
        self.zip_code = zip_code
        self.distance = distance
        self.max_pages = max_pages
        self.setup_webdriver(headless)
        
    def setup_webdriver(self, headless: bool = True):
        """Set up the Chrome WebDriver.
        
        Args:
            headless: Whether to run Chrome in headless mode
        """
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        
        # Use webdriver manager to handle driver installation
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.wait = WebDriverWait(self.driver, 20)  # Increased wait time to 20 seconds
        
    def get_contractors(self) -> List[Dict[str, Any]]:
        """Fetch and parse contractor data from GAF website.
        
        Returns:
            List of dictionaries containing contractor information
        """
        all_contractors = []
        url = f"https://www.gaf.com/en-us/roofing-contractors/residential?distance={self.distance}"
        
        # If zip code is provided, add it to the URL
        if self.zip_code:
            url += f"&postalCode={self.zip_code}"
        
        try:
            # Navigate to the contractor search page with distance parameter already set
            self.driver.get(url)
            print(f"Loading page: {url}")
            
            # Wait a bit for the page to load
            time.sleep(5)
            
            # Save the HTML for debugging
            self.save_html(self.driver.page_source, "data/gaf_page.html")
            
            # Wait for the page to load and then for search results to appear
            try:
                # Handle cookie banner first - very important before interacting with the page
                self._accept_cookies()
                time.sleep(2) # Give time for banner to disappear
                
                # First check if we need to click a "Search" button after the page loads
                # This might be needed if the zip code parameter doesn't auto-trigger search
                search_buttons = self.driver.find_elements(By.CSS_SELECTOR, 
                                        "button.field__input-search[type='submit'], button.search-button")
                if search_buttons and len(search_buttons) > 0 and search_buttons[0].is_displayed() and search_buttons[0].is_enabled():
                    print("Clicking search button...")
                    try:
                        search_buttons[0].click()
                    except Exception as click_e:
                        print(f"Normal click failed: {click_e}, trying JavaScript click")
                        self.driver.execute_script("arguments[0].click();", search_buttons[0])
                    time.sleep(3)  # Wait for results to load
                
                # Directly navigate to URL with parameters if the button click fails
                try:
                    # Wait for contractor cards to appear, with a longer timeout
                    self.wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "article.certification-card"))
                    )
                    print("Contractor cards found on page")
                except TimeoutException:
                    print("No contractor cards found after search. Checking for no results message...")
                    no_results = self.driver.find_elements(By.CSS_SELECTOR, ".query-summary:contains('0 results')")
                    if no_results and len(no_results) > 0:
                        print("Search returned 0 results")
                        return all_contractors
                    
                # Process the results
                contractors_on_page = []
                self._process_results_page(contractors_on_page)
                all_contractors.extend(contractors_on_page)
                print(f"Found {len(contractors_on_page)} contractors on page 1")
                
                # Handle pagination if it exists
                page_num = 1
                while self._go_to_next_page():
                    page_num += 1
                    if self.max_pages and page_num > self.max_pages:
                        print(f"Reached maximum pages limit ({self.max_pages})")
                        break
                        
                    contractors_on_page = []
                    self._process_results_page(contractors_on_page)
                    all_contractors.extend(contractors_on_page)
                    print(f"Found {len(contractors_on_page)} contractors on page {page_num}")
                
            except (TimeoutException, NoSuchElementException) as e:
                print(f"Error loading search results: {e}")
                # Try to debug the issue
                print("Current page HTML structure:")
                page_source = self.driver.page_source
                if "certification-card" in page_source:
                    print("certification-card class exists in HTML but elements may not be visible")
                else:
                    print("certification-card class not found in HTML - page structure may be different")
                
        except Exception as e:
            print(f"Unexpected error: {e}")
        finally:
            self.driver.quit()
            
        # Show ZIP code in results summary if it was used
        if self.zip_code:
            print(f"Found {len(all_contractors)} contractors near {self.zip_code} (within {self.distance} miles)")
        else:
            print(f"Found {len(all_contractors)} contractors total (within {self.distance} miles)")
            
        return all_contractors
    
    def _accept_cookies(self):
        """Accept cookies if the banner is present."""
        try:
            # First check for the common cookie acceptance button
            cookie_buttons = self.driver.find_elements(By.CSS_SELECTOR, 
                "#onetrust-accept-btn-handler, .accept-cookies-button, .cookie-accept-button")
            
            if cookie_buttons and len(cookie_buttons) > 0 and cookie_buttons[0].is_displayed():
                print("Accepting cookies via button...")
                cookie_buttons[0].click()
                time.sleep(1)
                return True
                
            # Also check for the specific OneTrust cookie banner that might be blocking
            overlay = self.driver.find_elements(By.CSS_SELECTOR, "#onetrust-banner-sdk, #onetrust-consent-sdk")
            if overlay and len(overlay) > 0 and overlay[0].is_displayed():
                # Try to close it using the close button
                close_buttons = self.driver.find_elements(By.CSS_SELECTOR, 
                    "#onetrust-close-btn-container button, .onetrust-close-btn-handler")
                if close_buttons and len(close_buttons) > 0 and close_buttons[0].is_displayed():
                    print("Closing cookie banner...")
                    close_buttons[0].click()
                    time.sleep(1)
                    return True
                    
                # If no dedicated close button, try clicking the accept button
                accept_buttons = self.driver.find_elements(By.CSS_SELECTOR, 
                    "#onetrust-accept-btn-container button, .onetrust-accept-btn-handler")
                if accept_buttons and len(accept_buttons) > 0 and accept_buttons[0].is_displayed():
                    print("Accepting cookies via OneTrust banner...")
                    accept_buttons[0].click()
                    time.sleep(1)
                    return True
                    
                # Try JavaScript approach if buttons aren't working
                try:
                    print("Attempting to remove cookie banner via JavaScript...")
                    self.driver.execute_script("""
                        var elements = document.querySelectorAll("#onetrust-banner-sdk, #onetrust-consent-sdk");
                        for(var i=0; i<elements.length; i++){
                            elements[i].style.display = 'none';
                        }
                    """)
                    time.sleep(1)
                    return True
                except Exception as js_e:
                    print(f"JavaScript removal failed: {js_e}")
            
            return False
        except Exception as e:
            print(f"Note: Could not interact with cookie banner: {e}")
            return False
    
    def _process_results_page(self, contractors: List[Dict[str, Any]]):
        """Process a single page of contractor results.
        
        Args:
            contractors: List to append contractor data to
        """
        # Wait for contractor listings to appear
        try:
            # Allow some time for the results to load
            time.sleep(5)
            
            # Wait for certification cards to be present
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "article.certification-card"))
            )
            
            # Get the page source and parse with BeautifulSoup for easier extraction
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, "html.parser")
            
            # Find all certification card elements
            certification_cards = soup.find_all("article", class_="certification-card")
            print(f"Found {len(certification_cards)} contractor cards on current page")
            
            for card in certification_cards:
                contractor_data = self._parse_contractor_element(card)
                if contractor_data:
                    contractors.append(contractor_data)
                    
        except Exception as e:
            print(f"Error processing results page: {e}")
    
    def _go_to_next_page(self) -> bool:
        """Navigate to the next page of results if available.
        
        Returns:
            True if successfully navigated to next page, False otherwise
        """
        try:
            # Accept cookies again if needed
            self._accept_cookies()
            
            # Look for "Next" button in pagination
            next_buttons = self.driver.find_elements(By.CSS_SELECTOR, "button.pagination__next")
            
            if not next_buttons or not next_buttons[0].is_enabled():
                print("No more pages or next button is disabled")
                return False
            
            # Try to scroll to make the button visible
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_buttons[0])
            time.sleep(1)
            
            # Try to use JavaScript to click the button if normal click fails
            try:
                next_buttons[0].click()
            except Exception as js_e:
                print(f"Normal click failed, trying JavaScript click: {js_e}")
                self.driver.execute_script("arguments[0].click();", next_buttons[0])
            
            print("Clicked next page button")
            
            # Wait for the new page to load
            time.sleep(5)
            return True
            
        except Exception as e:
            print(f"Error navigating to next page: {e}")
            return False
    
    def _parse_contractor_element(self, element) -> Optional[Dict[str, Any]]:
        """Parse a contractor element from the search results.
        
        Args:
            element: BeautifulSoup element representing a contractor
            
        Returns:
            Dictionary containing contractor information or None if parsing failed
        """
        try:
            contractor = {
                "name": "",
                "address": "",
                "city": "",
                "state": "",
                "zip": "",
                "phone": "",
                "website": "",
                "distance": "",
                "certifications": [],
                "rating": "",
                "review_count": "",
                "search_zip_code": self.zip_code,
                "search_distance": self.distance
            }
            
            # Get the contractor name from the certification-card__heading
            heading = element.find("h2", class_="certification-card__heading")
            if heading and heading.find("a"):
                contractor["name"] = heading.find("a").get_text(strip=True)
                
                # Get the website URL from the heading link
                contractor["website"] = heading.find("a").get("href", "")
            
            # Get city and distance information
            city_elem = element.find("p", class_="certification-card__city")
            if city_elem:
                city_text = city_elem.get_text(strip=True)
                # Extract city, state and distance (format: "City, ST - XX.X mi")
                parts = city_text.split(" - ")
                if len(parts) == 2:
                    city_state = parts[0]
                    contractor["distance"] = parts[1]
                    
                    # Extract city and state
                    if "," in city_state:
                        city, state = city_state.split(",", 1)
                        contractor["city"] = city.strip()
                        contractor["state"] = state.strip()
                    else:
                        contractor["city"] = city_state.strip()
            
            # Get the phone number
            phone_elem = element.find("a", class_="certification-card__phone")
            if phone_elem:
                # Extract the text but ignore the "Phone Number:" text
                phone_text = phone_elem.get_text(strip=True)
                if "Phone Number:" in phone_text:
                    phone_text = phone_text.replace("Phone Number:", "").strip()
                contractor["phone"] = phone_text
            
            # Get the ratings
            rating_stars = element.find("div", class_="rating-stars")
            if rating_stars:
                # Get rating average
                rating_avg = rating_stars.find("span", class_="rating-stars__average")
                if rating_avg:
                    contractor["rating"] = rating_avg.get_text(strip=True)
                
                # Get review count
                review_count = rating_stars.find("span", class_="rating-stars__total")
                if review_count:
                    # Extract just the number from format like "(54)"
                    count_text = review_count.get_text(strip=True)
                    if count_text.startswith("(") and count_text.endswith(")"):
                        contractor["review_count"] = count_text[1:-1]
            
            # Get certifications
            cert_list = element.find("ul", class_="certification-card__certifications-list")
            if cert_list:
                cert_items = cert_list.find_all("li", class_="certification-card__certification")
                for cert in cert_items:
                    cert_text = cert.get_text(strip=True)
                    if cert_text:
                        contractor["certifications"].append(cert_text)
            
            # Only return if we found at least a name
            if contractor["name"]:
                return contractor
            return None
            
        except Exception as e:
            print(f"Error parsing contractor element: {e}")
            return None
    
    def save_to_csv(self, contractors: List[Dict[str, Any]], filename: str = "gaf_contractors.csv"):
        """Save the contractor data to a CSV file.
        
        Args:
            contractors: List of contractor dictionaries
            filename: Output CSV filename
        """
        if not contractors:
            print("No data to save")
            return
            
        os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
        
        fieldnames = list(contractors[0].keys())
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(contractors)
            
        print(f"Saved {len(contractors)} contractors to {filename}")
    
    def save_to_json(self, contractors: List[Dict[str, Any]], filename: str = "gaf_contractors.json"):
        """Save the contractor data to a JSON file.
        
        Args:
            contractors: List of contractor dictionaries
            filename: Output JSON filename
        """
        if not contractors:
            print("No data to save")
            return
            
        os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(contractors, f, indent=4)
            
        print(f"Saved {len(contractors)} contractors to {filename}")
            
    def save_html(self, html: str, filename: str = "gaf_page.html"):
        """Save the raw HTML to a file for debugging.
        
        Args:
            html: HTML content to save
            filename: Output HTML filename
        """
        os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)
            
        print(f"Saved HTML to {filename}")


def main():
    """Main function to demonstrate the scraper usage."""
    zip_code = "10013"  # NYC zipcode as specified
    scraper = GAFContractorScraper(zip_code=zip_code, headless=False, max_pages=50)  #Can limit pages for testing
    contractors = scraper.get_contractors()
    
    # Save the data to both CSV and JSON formats
    scraper.save_to_csv(contractors, "data/gaf_contractors.csv")
    scraper.save_to_json(contractors, "data/gaf_contractors.json")
    
    print(f"Scraping completed. Found {len(contractors)} contractors.")


if __name__ == "__main__":
    main()
