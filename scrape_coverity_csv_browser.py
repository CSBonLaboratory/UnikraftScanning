#from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.firefox_binary import FirefoxBinary
from seleniumwire import webdriver
from seleniumwire.utils import decode
import os
import time
USER_EMAIL = os.environ["COVERITY_SCRAPER_USER_EMAIL"]
USER_PASS = os.environ["COVERITY_SCRAPER_PASS"]
PROJECT_NAME = os.environ["COVERITY_PROJECT_NAME"]
FIREFOX_PATH = "/usr/bin/firefox"

try:

    options = Options()
    options.add_argument("--headless")
    options.bin = FirefoxBinary("/usr/bin/firefox")
    browser = webdriver.Firefox(options=options)
   
    print("Starting Firefox")
    browser.get('https://scan.coverity.com/users/sign_in')
    user_email_input = browser.find_element(By.ID,"user_email")
    user_email_input.send_keys(USER_EMAIL)
    

    user_password_input = browser.find_element(By.ID,"user_password")
    user_password_input.send_keys(USER_PASS)

    sign_in_button = browser.find_element(By.NAME, "commit")
    sign_in_button.click()

    print("Authentication OK")

    browser.find_element(By.LINK_TEXT, PROJECT_NAME).click()
    print("Entering project overview OK")

    browser.find_element(By.XPATH,"//a[@href='/projects/unikraft-scanning/view_defects']").click()
    print("Entering defects tab OK")
    
    original_window = browser.current_window_handle
    WebDriverWait(browser, 40).until(EC.number_of_windows_to_be(2))
    time.sleep(10)
    if browser.window_handles[1] != original_window:
        browser.switch_to.window(browser.window_handles[1])
    else:
        browser.switch_to.window(browser.window_handles[0])
    print("Switching to second tab in browser where defects are OK")
    
    browser.get("https://scan9.scan.coverity.com/reports/table.json?projectId=15201&viewId=54998")
    for request in browser.requests:
        if request.url == 'https://scan9.scan.coverity.com/reports/table.json?projectId=15201&viewId=54998':
            if request.response:
                body = decode(request.response.body, request.response.headers.get('Content-Encoding', 'identity'))
                print(body)


finally:
    try:
        browser.close()
    except:
        
        pass
