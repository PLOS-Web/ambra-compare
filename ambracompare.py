from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException

from PIL import Image
import subprocess
import logging
import time

from rhyno import Rhyno

logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)

def same_size_erize(image_1, image_2):
    img_1 = Image.open(image_1)
    img_2 = Image.open(image_2)
    img_1_height, img_1_width = img_1.size
    img_2_height, img_2_width = img_2.size

    if img_1_height < img_2_height:
        height = img_2_height
        logging.info("cropping %s height to %s ..." % (image_1, img_2_height))
    elif img_2_height < img_1_height:
        height = img_1_height
        logging.info("cropping %s height to %s ..." % (image_2, img_1_height))
    else:
        height = img_2_height
        logging.debug("Both images have same height, no cropping necessary.")

    if img_1_width < img_2_width:
        width = img_2_width
        logging.info("cropping %s width to %s ..." % (image_1, img_2_width))
    elif img_2_width < img_1_width:
        width = img_1_width
        logging.info("cropping %s width to %s ..." % (image_2, img_1_width))
    else:
        width = img_2_width
        logging.debug("Both images have same width, no cropping necessary.")

    img_1 = img_1.crop((0, 0, height, width))
    img_1.save(image_1)

    img_2 = img_2.crop((0, 0, height, width))
    img_2.save(image_2)

def make_diff(image_1, image_2, diff):
    compare_proc = subprocess.Popen(["compare", image_1, image_2, diff],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    compare_proc.wait()
    logging.debug("imagemagick 'compare' return code: %i", compare_proc.returncode)
    return compare_proc.returncode

def compare_prod_stage(doi):
    stage_url_format = "http://plosone-stage.plos.org/article/info%%3Adoi%%2F10.1371%%2Fjournal.%s"
    prod_url_format = "http://www.plosone.org/article/info%%3Adoi%%2F10.1371%%2Fjournal.%s"

    stage_screenshot = get_screenshot(stage_url_format % doi, "%s-stage.png" % doi)
    prod_screenshot = get_screenshot(prod_url_format % doi, "%s-prod.png" % doi)

    same_size_erize("%s-stage.png" % doi, "%s-prod.png" % doi)
    make_diff("%s-stage.png" % doi, "%s-prod.png" % doi, "%s-diff.png" % doi)

def upload_webprod(filename):
    iad_loc = "iad-webprod-devstack01.int.plos.org:/var/spool/ambra/ingestion-queue/"
    proc = subprocess.Popen(["scp", filename, iad_loc],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    proc.wait()
    logging.debug("scp return code: %i", proc.returncode)

class WebprodDriver(object):
    def __init__(self):
        self.webdriver = webdriver.Firefox()
 #TODO update to webrod

        self.webdriver.get('https://register-webprod.plosjournals.org/cas/login?service=http%3A%2F%2Fwebprod.plosjournals.org%2Fuser%2Fsecure%2FsecureRedirect.action%3FgoTo%3D%252Fhome.action')
        elem_email = self.webdriver.find_element_by_id('username')
        elem_email.send_keys("brakit@gmail.com") #TODO fill in
        elem_password = self.webdriver.find_element_by_id('password')
        elem_password.send_keys("123456") #TODO fill in
        self.webdriver.find_element_by_name('submit').click()
        
    def ingest(self, doi):
        self.webdriver.get('https://webprod.plosjournals.org/admin')
        try:
            self.webdriver.find_element_by_xpath("//input[@value='%s.zip']" % doi).click()
        except NoSuchElementException, e:
            logging.error("Could not find '%s.zip' in admin ingestibles" % doi)
            return
        self.webdriver.find_element_by_id('ingestArchives_force').click()
        self.webdriver.find_element_by_id('ingestArchives_action').click()

    def get_screenshot(self, url, filename):
        self.webdriver.get(url)
        self.webdriver.save_screenshot(filename)
    
    def disable(self, doi):
        self.webdriver.get('https://webprod.plosjournals.org/admin')
        elem_doi_field = self.webdriver.find_element_by_xpath("//form[@id='disableArticle']/input[@name='article']")
        elem_doi_field.send_keys("info:doi/10.1371/journal.%s" % doi)
        self.webdriver.find_element_by_xpath("//form[@id='disableArticle']/input[@type='submit']").click()
        alert = self.webdriver.switch_to_alert()
        alert.accept()

    def close(self):
        self.webdriver.close()
    
if __name__ == "__main__":
    wpd = WebprodDriver()
    upload_webprod('pone.0079998.zip')
    #wpd.ingest('pone.0079998')

    r = Rhyno('https://webprod.plosjournals.org/api/')
    r.ingest('pone.0079998.zip', force_reingest=True)
    wpd.disable('pone.0079998')
    
