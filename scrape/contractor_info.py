import os
import time
import json
import csv
import re
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from typing import Dict, Any, Optional, List


class ContractorInfoScraper:
    """Scraper for extracting detailed information from GAF contractor profile pages."""
    
    def __init__(self, headless: bool = True):
        """Initialize the scraper.
        
        Args:
            headless: Whether to run Chrome in headless mode (default: True)
        """
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
        self.wait = WebDriverWait(self.driver, 20)  # Set wait time to 20 seconds
        
    def fetch_profile_html(self, url: str, save_path: str = "data/contractor_profile.html") -> str:
        """Fetch the HTML from a contractor profile page and save it for analysis.
        
        Args:
            url: URL of the contractor profile page
            save_path: Path to save the HTML file
            
        Returns:
            The HTML content of the page
        """
        try:
            print(f"Loading profile page: {url}")
            self.driver.get(url)
            
            # Wait for the page to load
            time.sleep(5)
            
            # Accept cookies if the banner is present
            self._accept_cookies()
            
            # Wait for the main profile content to load
            try:
                self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".contractor-profile, .about-us-block"))
                )
                print("Profile content loaded successfully")
            except TimeoutException:
                print("Timed out waiting for profile content to load")
                
            # Get the page source and save it
            html_content = self.driver.page_source
            self._save_html(html_content, save_path)
            
            return html_content
            
        except Exception as e:
            print(f"Error fetching profile HTML: {e}")
            return ""
    
    def scrape_contractor_profile(self, url: str, id: int = None) -> Dict[str, Any]:
        """Scrape detailed information from a contractor profile page.
        
        Args:
            url: URL of the contractor profile page
            id: Optional unique ID for the contractor
            
        Returns:
            Dictionary containing all the scraped contractor information
        """
        contractor_data = {
            "id": id,  # Add ID field
            "url": url,
            "name": "",
            "website": "",
            "phone": "",
            "about": "",
            "certifications": [],
            "awards": [],
            "years_in_business": "",
            "contractor_id": "",
            "state_license_number": "",
            "review_score": "",
            "review_count": "",
            "reviews": []
        }
        
        # Extract contractor ID from URL
        match = re.search(r'(\d+)$', url)
        if match:
            contractor_data["contractor_id"] = match.group(1)
        
        # Fetch the profile page HTML
        html_content = self.fetch_profile_html(url)
        if not html_content:
            print(f"Could not fetch profile HTML for: {url}")
            return contractor_data
            
        # Parse the HTML
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Extract basic information
        contractor_data["name"] = self._extract_name(soup)
        contractor_data["phone"] = self._extract_phone(soup)
        contractor_data["website"] = self._extract_website(soup)
        contractor_data["about"] = self._extract_about(soup)
        
        # Extract certifications and awards
        certs_awards = self._extract_certifications_awards(soup)
        contractor_data["certifications"] = certs_awards["certifications"]
        contractor_data["awards"] = certs_awards["awards"]
        
        # Extract business information
        business_info = self._extract_business_info(soup)
        contractor_data["years_in_business"] = business_info.get("years_in_business", "")
        contractor_data["state_license_number"] = business_info.get("state_license_number", "")
        
        # Extract reviews
        reviews_data = self._extract_reviews(soup)
        contractor_data["review_score"] = reviews_data["score"]
        contractor_data["review_count"] = reviews_data["count"]
        contractor_data["reviews"] = reviews_data["reviews"]
        
        return contractor_data
    
    def _extract_name(self, soup: BeautifulSoup) -> str:
        """Extract the contractor name from the profile page.
        
        Args:
            soup: BeautifulSoup object of the profile page
            
        Returns:
            Contractor name as a string
        """
        # Try different selectors for the name
        selectors = [
            "h1.contractor-profile__heading",
            "h1.contractor-profile-heading",
            ".contractor-profile h1",
            ".about-us-block h1",
            "h1"
        ]
        
        for selector in selectors:
            name_elem = soup.select_one(selector)
            if name_elem:
                return name_elem.text.strip()
        
        return ""
    
    def _extract_phone(self, soup: BeautifulSoup) -> str:
        """Extract the phone number from the profile page.
        
        Args:
            soup: BeautifulSoup object of the profile page
            
        Returns:
            Phone number as a string
        """
        # Try different selectors for the phone number
        selectors = [
            "a.certification-card__phone",
            ".contractor-profile__phone",
            ".contact-info__phone",
            "a[href^='tel:']"
        ]
        
        for selector in selectors:
            phone_elem = soup.select_one(selector)
            if phone_elem:
                phone_text = phone_elem.text.strip()
                # Remove "Phone Number:" if present
                phone_text = phone_text.replace("Phone Number:", "").strip()
                return phone_text
        
        return ""
    
    def _extract_website(self, soup: BeautifulSoup) -> str:
        """Extract the website URL from the profile page.
        
        Args:
            soup: BeautifulSoup object of the profile page
            
        Returns:
            Website URL as a string
        """
        # First priority: look for the specific "Visit Website" link 
        visit_website_links = soup.select('a[rel="noopener noreferrer"][target="_blank"]')
        for link in visit_website_links:
            if "Visit Website" in link.text.strip():
                href = link.get("href", "")
                if href and href.startswith("http"):
                    return href
        
        # Try different selectors for the website
        selectors = [
            "a.contractor-profile__website",
            ".contractor-profile__website a",
            ".contact-info__website a",
            "a.website-link",
            "a[target='_blank']:not([href*='gaf.com'])"
        ]
        
        for selector in selectors:
            website_elems = soup.select(selector)
            for elem in website_elems:
                href = elem.get("href", "")
                if href and "gaf.com" not in href and href.startswith("http"):
                    return href
        
        return ""
    
    def _extract_about(self, soup: BeautifulSoup) -> str:
        """Extract the about section from the profile page.
        
        Args:
            soup: BeautifulSoup object of the profile page
            
        Returns:
            About text as a string
        """
        # Try different selectors for the about section
        selectors = [
            ".about-us-block__content",
            ".about-us-block p",
            ".contractor-profile__about",
            ".contractor-profile__description"
        ]
        
        for selector in selectors:
            about_elems = soup.select(selector)
            if about_elems:
                about_text = " ".join([elem.text.strip() for elem in about_elems])
                return about_text
        
        return ""
    
    def _extract_certifications_awards(self, soup: BeautifulSoup) -> Dict[str, List[str]]:
        """Extract certifications and awards from the profile page.
        
        Args:
            soup: BeautifulSoup object of the profile page
            
        Returns:
            Dictionary with certifications and awards lists
        """
        result = {
            "certifications": [],
            "awards": []
        }
        
        # Find the certifications section
        cert_section = soup.find("section", class_=lambda c: c and "certification" in (c or ""))
        if cert_section:
            # Look for certification items
            cert_items = cert_section.find_all("li", class_=lambda c: c and "certification" in (c or ""))
            for item in cert_items:
                cert_text = item.text.strip()
                if cert_text:
                    # Determine if it's an award or certification
                    if "award" in cert_text.lower() or "president" in cert_text.lower():
                        result["awards"].append(cert_text)
                    else:
                        result["certifications"].append(cert_text)
            
            # If no items found with the specific class, try to find any list items
            if not cert_items:
                cert_items = cert_section.find_all("li")
                for item in cert_items:
                    cert_text = item.text.strip()
                    if cert_text:
                        # Determine if it's an award or certification
                        if "award" in cert_text.lower() or "president" in cert_text.lower():
                            result["awards"].append(cert_text)
                        else:
                            result["certifications"].append(cert_text)
        
        return result
    
    def _extract_business_info(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract business information from the profile page.
        
        Args:
            soup: BeautifulSoup object of the profile page
            
        Returns:
            Dictionary with business information
        """
        result = {
            "years_in_business": "",
            "state_license_number": ""
        }
        
        # Look for specific "In business since" format
        business_since = soup.select_one("p.contractor-details__description")
        if business_since and "business since" in business_since.text:
            result["years_in_business"] = business_since.text.strip()
        
        # Look specifically for license number in contractor-details section
        license_title = soup.select_one("h3.contractor-details__title")
        if license_title and "license" in license_title.text.lower():
            license_desc = license_title.find_next("p", class_="contractor-details__description")
            if license_desc:
                result["state_license_number"] = license_desc.text.strip()
        
        # Fall back to the general approach if specific elements weren't found
        if not result["state_license_number"]:
            info_labels = soup.find_all(["dt", "th", "strong", "span", "label", "h3"])
            
            for label in info_labels:
                label_text = label.text.strip().lower()
                
                # Look for years in business if not already found
                if not result["years_in_business"] and "years" in label_text and "business" in label_text:
                    # Try to find the corresponding value
                    if label.find_next(["dd", "td", "span", "div", "p"]):
                        value = label.find_next(["dd", "td", "span", "div", "p"]).text.strip()
                        result["years_in_business"] = value
                    elif label.parent and label.parent.find_next(["dd", "td", "span", "div", "p"]):
                        value = label.parent.find_next(["dd", "td", "span", "div", "p"]).text.strip()
                        result["years_in_business"] = value
                
                # Look for license number if not already found
                if not result["state_license_number"] and ("license" in label_text or "registration" in label_text):
                    # Try to find the corresponding value
                    if label.find_next(["dd", "td", "span", "div", "p"]):
                        value = label.find_next(["dd", "td", "span", "div", "p"]).text.strip()
                        result["state_license_number"] = value
                    elif label.parent and label.parent.find_next(["dd", "td", "span", "div", "p"]):
                        value = label.parent.find_next(["dd", "td", "span", "div", "p"]).text.strip()
                        result["state_license_number"] = value
        
        return result
    
    def _extract_reviews(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract reviews from the profile page.
        
        Args:
            soup: BeautifulSoup object of the profile page
            
        Returns:
            Dictionary with review score, count, and individual reviews
        """
        result = {
            "score": "",
            "count": "",
            "reviews": []
        }
        
        # Find the reviews section
        reviews_section = soup.find("section", class_=lambda c: c and "review" in (c or ""))
        if not reviews_section:
            # Try looking for specific contractor-reviews class
            reviews_section = soup.find(class_=lambda c: c and "contractor-reviews" in (c or ""))
            if not reviews_section:
                return result
            
        # Try to find the rating summary
        rating_summary = reviews_section.find(class_=lambda c: c and "rating" in (c or ""))
        if rating_summary:
            # Look for the score
            rating_avg = rating_summary.find(class_=lambda c: c and "average" in (c or ""))
            if rating_avg:
                result["score"] = rating_avg.text.strip()
                
            # Look for the count
            rating_count = rating_summary.find(class_=lambda c: c and ("count" in (c or "") or "total" in (c or "")))
            if rating_count:
                count_text = rating_count.text.strip()
                # Extract just the number from format like "(54)"
                if count_text.startswith("(") and count_text.endswith(")"):
                    result["count"] = count_text[1:-1]
                else:
                    result["count"] = count_text
        
        # Find individual reviews
        # First check for specific contractor review quotes
        review_quotes = soup.select("p.contractor-reviews__quote")
        if review_quotes:
            for quote in review_quotes:
                review = {
                    "author": "",
                    "date": "",
                    "rating": "",
                    "text": ""
                }
                
                # Get the review text
                quote_text = quote.select_one(".contractor-reviews__quote-text")
                if quote_text:
                    review["text"] = quote_text.text.strip()
                else:
                    review["text"] = quote.text.strip()
                
                # Look for author and date in the cite element that follows
                cite = quote.find_next("cite", class_="contractor-reviews__cite")
                if cite:
                    cite_text = cite.text.strip()
                    if "," in cite_text:
                        author, date = cite_text.split(",", 1)
                        review["author"] = author.strip()
                        review["date"] = date.strip()
                    else:
                        review["author"] = cite_text
                
                # Only add if we have at least text content
                if review["text"]:
                    result["reviews"].append(review)
        else:
            # Fall back to general review items search
            review_items = reviews_section.find_all(class_=lambda c: c and "review-item" in (c or ""))
            if not review_items:
                review_items = reviews_section.find_all("article")
                if not review_items:
                    review_items = reviews_section.find_all("li")
                
            for item in review_items:
                review = {
                    "author": "",
                    "date": "",
                    "rating": "",
                    "text": ""
                }
                
                # Author
                author_elem = item.find(class_=lambda c: c and ("author" in (c or "") or "name" in (c or "")))
                if author_elem:
                    review["author"] = author_elem.text.strip()
                    
                # Date
                date_elem = item.find(class_=lambda c: c and "date" in (c or ""))
                if date_elem:
                    review["date"] = date_elem.text.strip()
                    
                # Rating
                rating_elem = item.find(class_=lambda c: c and "rating" in (c or ""))
                if rating_elem:
                    # Try to find the rating value
                    rating_value = rating_elem.get("data-rating", "")
                    if rating_value:
                        review["rating"] = rating_value
                    else:
                        # Count the filled stars
                        filled_stars = rating_elem.find_all(class_=lambda c: c and "filled" in (c or ""))
                        if filled_stars:
                            review["rating"] = str(len(filled_stars))
                        
                # Text
                text_elem = item.find(class_=lambda c: c and ("text" in (c or "") or "content" in (c or "") or "quote" in (c or "")))
                if text_elem:
                    review["text"] = text_elem.text.strip()
                
                # Only add if we have at least some content
                if any(review.values()):
                    result["reviews"].append(review)
        
        return result
    
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
            
    def _save_html(self, html: str, filename: str):
        """Save the HTML content to a file.
        
        Args:
            html: HTML content to save
            filename: Path to save the HTML file
        """
        os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)
            
        print(f"Saved HTML to {filename}")
    
    def scrape_contractors_from_csv(self, csv_file: str, output_json: str = "data/contractor_details.json", 
                                    output_csv: str = "data/contractor_details.csv", limit: int = None):
        """Scrape detailed information for contractors listed in a CSV file.
        
        Args:
            csv_file: Path to the CSV file with contractor URLs
            output_json: Path to save the output JSON file
            output_csv: Path to save the output CSV file
            limit: Maximum number of contractors to scrape (None = all)
        
        Returns:
            List of contractor details
        """
        contractors = []
        
        # Read the CSV file
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            # Create a list of URLs to scrape
            urls_to_scrape = []
            for i, row in enumerate(reader):
                if limit is not None and i >= limit:
                    break
                
                # Get the URL from the CSV
                url = row.get('website', '')
                if url and 'gaf.com' in url:
                    urls_to_scrape.append(url)
        
        print(f"Found {len(urls_to_scrape)} contractor URLs to scrape")
        
        # Scrape each URL
        for i, url in enumerate(urls_to_scrape):
            print(f"Scraping contractor {i+1}/{len(urls_to_scrape)}: {url}")
            try:
                # Pass the index as the ID
                contractor_data = self.scrape_contractor_profile(url, id=i)
                contractors.append(contractor_data)
                
                # Save progress after each contractor to JSON
                with open(output_json, 'w', encoding='utf-8') as f:
                    json.dump(contractors, f, indent=4)
                    
                # Also save progress to CSV after each contractor
                self._save_to_csv(contractors, output_csv)
                    
                # Add some delay between requests to avoid overloading the server
                if i < len(urls_to_scrape) - 1:
                    time.sleep(2)
            except Exception as e:
                print(f"Error scraping {url}: {e}")
        
        print(f"Scraped {len(contractors)} contractors.")
        print(f"Saved detailed data to:")
        print(f"- JSON: {output_json}")
        print(f"- CSV: {output_csv}")
        
        return contractors
    
    def _save_to_csv(self, contractors: List[Dict[str, Any]], filename: str):
        """Save the contractor data to a CSV file.
        
        Args:
            contractors: List of contractor dictionaries
            filename: Output CSV filename
        """
        if not contractors:
            print("No data to save to CSV")
            return
        
        os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
        
        # Create a flattened structure for CSV
        flattened_data = []
        for contractor in contractors:
            flat_contractor = contractor.copy()
            
            # Flatten certifications and awards into comma-separated strings
            flat_contractor['certifications'] = '; '.join(contractor.get('certifications', []))
            flat_contractor['awards'] = '; '.join(contractor.get('awards', []))
            
            # Handle reviews separately or exclude them from CSV
            # For simplicity, just add the count and exclude the review details
            flat_contractor['reviews_count'] = len(contractor.get('reviews', []))
            flat_contractor.pop('reviews', None)  # Remove the reviews list
            
            flattened_data.append(flat_contractor)
        
        # Get all field names from all contractors
        fieldnames = set()
        for contractor in flattened_data:
            fieldnames.update(contractor.keys())
        
        fieldnames = sorted(list(fieldnames))
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(flattened_data)
            
        print(f"Saved {len(flattened_data)} contractors to {filename}")
    
    def close(self):
        """Close the WebDriver."""
        if hasattr(self, 'driver'):
            self.driver.quit()


def test_contractor_profile_scraper():
    """Test the contractor profile scraper on an example URL."""
    example_url = "https://www.gaf.com/en-us/roofing-contractors/residential/usa/nj/wayne/matute-roofing-1113654"
    
    scraper = ContractorInfoScraper(headless=False)  # Set to False to see the browser
    try:
        # Scrape the contractor profile
        contractor_data = scraper.scrape_contractor_profile(example_url)
        
        # Print the scraped data
        print("\nScraped Contractor Data:")
        print(f"Name: {contractor_data['name']}")
        print(f"Phone: {contractor_data['phone']}")
        print(f"Website: {contractor_data['website']}")
        print(f"Contractor ID: {contractor_data['contractor_id']}")
        print(f"Years in Business: {contractor_data['years_in_business']}")
        print(f"State License Number: {contractor_data['state_license_number']}")
        print(f"Review Score: {contractor_data['review_score']}")
        print(f"Review Count: {contractor_data['review_count']}")
        
        print("\nAbout:")
        print(contractor_data['about'][:200] + "..." if len(contractor_data['about']) > 200 else contractor_data['about'])
        
        print("\nCertifications:")
        for cert in contractor_data['certifications']:
            print(f"- {cert}")
            
        print("\nAwards:")
        for award in contractor_data['awards']:
            print(f"- {award}")
            
        print(f"\nNumber of Reviews: {len(contractor_data['reviews'])}")
        if contractor_data['reviews']:
            print("\nSample Review:")
            review = contractor_data['reviews'][0]
            print(f"Author: {review['author']}")
            print(f"Date: {review['date']}")
            print(f"Rating: {review['rating']}")
            print(f"Text: {review['text'][:100]}..." if len(review['text']) > 100 else review['text'])
        
        # Save the data to a JSON file
        with open("data/test_contractor.json", 'w', encoding='utf-8') as f:
            json.dump(contractor_data, f, indent=4)
            
        print("\nSaved test data to data/test_contractor.json")
        
    finally:
        scraper.close()


if __name__ == "__main__":
    # Run the full scraper on all contractors from the CSV file
    scraper = ContractorInfoScraper(headless=True)
    try:
        # Specify input and output files
        input_csv = "data/gaf_contractors.csv"
        output_json = "data/contractor_details.json"
        output_csv = "data/contractor_details.csv"
        
        # You can set a limit for testing or set to None for all contractors
        limit = None  # Set to a number like 5 for testing, or None for all
        
        # Run the scraper
        scraper.scrape_contractors_from_csv(
            csv_file=input_csv, 
            output_json=output_json,
            output_csv=output_csv,
            limit=limit
        )
    finally:
        scraper.close()
