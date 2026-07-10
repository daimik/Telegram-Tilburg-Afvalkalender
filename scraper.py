import sys
import os
import time
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

DUTCH_MONTHS = {
    'januari': 1, 'februari': 2, 'maart': 3, 'april': 4,
    'mei': 5, 'juni': 6, 'juli': 7, 'augustus': 8,
    'september': 9, 'oktober': 10, 'november': 11, 'december': 12
}


def parse_date(month_year_str, day_number):
    try:
        match = re.search(r'(\w+)\s*-?\s*(\d{4})', month_year_str)
        if match:
            month_name = match.group(1).lower()
            year = int(match.group(2))
            month = DUTCH_MONTHS.get(month_name)
            if month:
                return datetime(year, month, int(day_number))
    except:
        pass
    return None


def find_chrome_binary():
    import shutil
    for binary in ['google-chrome', 'chromium', 'chromium-browser']:
        path = shutil.which(binary)
        if path:
            return path
    return None


def find_chromedriver():
    import shutil
    for name in ['chromedriver', 'chromium.chromedriver']:
        path = shutil.which(name)
        if path:
            return path
    return None


def scrape_waste_calendar(postcode="5000AA", huisnummer="1", months_ahead=2):
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-software-rasterizer')
    chrome_options.add_argument('--log-level=3')

    chrome_binary = find_chrome_binary()
    if chrome_binary:
        chrome_options.binary_location = chrome_binary

    driver_path = find_chromedriver()
    if driver_path:
        driver = webdriver.Chrome(service=Service(driver_path), options=chrome_options)
    else:
        driver = webdriver.Chrome(options=chrome_options)
    collections = []

    try:
        driver.get("https://21burgerportaal.mendixcloud.com/p/tilburg/landing/")
        time.sleep(3)

        visible_inputs = [inp for inp in driver.find_elements(By.TAG_NAME, "input")
                         if inp.is_displayed() and inp.get_attribute('type') == 'text']

        if len(visible_inputs) >= 2:
            visible_inputs[0].click()
            visible_inputs[0].clear()
            visible_inputs[0].send_keys(postcode)
            time.sleep(0.5)
            visible_inputs[1].click()
            visible_inputs[1].clear()
            visible_inputs[1].send_keys(huisnummer)
            visible_inputs[1].send_keys(Keys.RETURN)
            time.sleep(3)
        else:
            raise Exception("Could not find address fields")

        informatie_h2 = driver.find_element(By.XPATH, "//h2[contains(text(), 'Informatie')]")
        card = informatie_h2.find_element(By.XPATH, "./ancestor::div[@role='button'][1]")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", card)
        time.sleep(3)

        afvalkalender_h2 = driver.find_element(By.XPATH, "//h2[contains(text(), 'Afvalkalender')]")
        card = afvalkalender_h2.find_element(By.XPATH, "./ancestor::div[@role='button'][1]")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", card)
        time.sleep(3)
        time.sleep(2)

        for month_num in range(months_ahead):
            time.sleep(1)

            current_month_year = "Unknown"
            try:
                month_spans = driver.find_elements(By.CSS_SELECTOR, "span.mx-name-text195")
                for span in month_spans:
                    if span.is_displayed():
                        text = span.text.strip()
                        if text and ("-" in text or any(m in text.lower() for m in DUTCH_MONTHS.keys())):
                            current_month_year = text
                            break
            except:
                pass

            day_items = driver.find_elements(By.CSS_SELECTOR, "div.mx-templategrid-item")

            for item in day_items:
                try:
                    day_span = item.find_element(By.CSS_SELECTOR, "span.mx-name-text199")
                    day_number = day_span.text.strip()
                    if not day_number or not day_number.isdigit():
                        continue
                    if "agendaitem-box-notmonth" in item.get_attribute("class"):
                        continue

                    images = item.find_elements(By.CSS_SELECTOR, "img.mx-name-imageViewer9")
                    for img in images:
                        try:
                            alt = (img.get_attribute("alt") or "").lower()
                            waste_type = None
                            if "papier" in alt or "pmd" in alt:
                                waste_type = "Papier/PMD"
                            elif "rest" in alt or "gft" in alt:
                                waste_type = "Rest/GFT"
                            if waste_type:
                                date_obj = parse_date(current_month_year, day_number)
                                if date_obj:
                                    collections.append({
                                        "date": date_obj.strftime("%Y-%m-%d"),
                                        "waste_type": waste_type
                                    })
                        except:
                            continue
                except:
                    continue

            if month_num < months_ahead - 1:
                try:
                    button_selectors = [
                        "//button[contains(@class, 'mx-name-actionButton57')]",
                        "//button[contains(text(), 'Volgende') and contains(@class, 'mx-button')]",
                    ]
                    next_btns = []
                    for selector in button_selectors:
                        try:
                            btns = driver.find_elements(By.XPATH, selector)
                            for btn in btns:
                                if btn.is_displayed() and btn not in next_btns:
                                    next_btns.append(btn)
                        except:
                            continue
                    if not next_btns:
                        break
                    btn = next_btns[0]
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                    time.sleep(0.3)
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(1)
                except:
                    break

        collections.sort(key=lambda x: x.get("date", ""))
        return collections

    except Exception as e:
        print(f"Scraper error: {e}", file=sys.stderr)
        return []
    finally:
        driver.quit()
