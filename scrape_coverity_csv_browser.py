from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.firefox_binary import FirefoxBinary
import os
import time
USER_EMAIL = os.environ["COVERITY_SCRAPER_USER_EMAIL"]
USER_PASS = os.environ["COVERITY_SCRAPER_PASS"]
PROJECT_NAME = os.environ["COVERITY_PROJECT_NAME"]
FIREFOX_PATH = "/snap/bin/firefox"

try:

    options = Options()
    options.add_argument("--headless")
    options.set_preference("browser.download.dir","~/Downloads/")
    options.set_preference("browser.download.useDownloadDir", True)
    # options.binary = FirefoxBinary("~/Desktop/firefox/firefox-bin")
    browser = webdriver.Firefox(options=options)
    # profile = FirefoxProfile()
    # profile.set_preference("browser.download.dir","~/Desktop/basic_coverity")
    # browser = FirefoxBinary("~/Desktop/firefox/firefox-bin")

    # browser.launch_browser(profile= profile)
    
    
    
    #print(browser.options.__dict__)

    
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

    WebDriverWait(browser, 40).until(EC.number_of_windows_to_be(2))
    browser.switch_to.window(browser.window_handles[1])
    print("Switching to second tab in browser where defects are OK")

    WebDriverWait(browser, 40).until(EC.element_to_be_clickable((By.XPATH, "//*[@id='views-button']")))
    browser.find_element(By.XPATH, "//*[@id='views-button']").click()
    print("Entering more options menu OK")
    
    action = ActionChains(browser)

    time.sleep(5)

    WebDriverWait(browser,40).until(EC.visibility_of_element_located((By.XPATH, '/html/body/div[2]/nav/div[1]/div/div[1]/ul/li[3]/a')))
    outstanding_issues = browser.find_element(By.XPATH, '/html/body/div[2]/nav/div[1]/div/div[1]/ul/li[3]/a')
    action.move_to_element(outstanding_issues)
    print("Hover mouse over Outstanding Defects tab OK")

    time.sleep(5)

    WebDriverWait(browser,40).until(EC.element_to_be_clickable((By.XPATH,'/html/body/div[2]/nav/div[1]/div/div[1]/ul/li[3]/a/span')))
    browser.find_element(By.XPATH,'/html/body/div[2]/nav/div[1]/div/div[1]/ul/li[3]/a/span').click()
    print("Click on more options in Outstanding Defects OK")

    WebDriverWait(browser,40).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="ui-menu-item-exportcsv"]')))
    browser.find_element(By.XPATH, '//*[@id="ui-menu-item-exportcsv"]').click()
    print("Click on export CSV OK")

    print("Finished")


finally:
    try:
        browser.close()
    except:
        pass
