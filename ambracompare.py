from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
import os
from glob import glob

from PIL import Image
import subprocess
import logging
import time

from rhyno import Rhyno

logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.DEBUG)

hdlr = logging.FileHandler('ambracompare.log')
base_logger = logging.getLogger('')
base_logger.addHandler(hdlr)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def same_size_erize(image_1, image_2):
    img_1 = Image.open(image_1)
    img_2 = Image.open(image_2)
    img_1_height, img_1_width = img_1.size
    img_2_height, img_2_width = img_2.size

    if img_1_height < img_2_height:
        height = img_2_height
        logger.info("cropping %s height to %s ..." % (image_1, img_2_height))
    elif img_2_height < img_1_height:
        height = img_1_height
        logger.info("cropping %s height to %s ..." % (image_2, img_1_height))
    else:
        height = img_2_height
        logger.debug("Both images have same height, no cropping necessary.")

    if img_1_width < img_2_width:
        width = img_2_width
        logger.info("cropping %s width to %s ..." % (image_1, img_2_width))
    elif img_2_width < img_1_width:
        width = img_1_width
        logger.info("cropping %s width to %s ..." % (image_2, img_1_width))
    else:
        width = img_2_width
        logger.debug("Both images have same width, no cropping necessary.")

    img_1 = img_1.crop((0, 0, height, width))
    img_1.save(image_1)

    img_2 = img_2.crop((0, 0, height, width))
    img_2.save(image_2)

def make_diff(image_1, image_2, diff):
    compare_proc = subprocess.Popen(["compare", image_1, image_2, diff],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    compare_proc.wait()
    logger.debug("imagemagick 'compare' return code: %i", compare_proc.returncode)
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
    logger.debug("scp return code: %i", proc.returncode)

class WebprodDriver(object):
    article_url_format = "https://webprod.plosjournals.org/article/info%%3Adoi%%2F10.1371%%2Fjournal.%s"

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
        logger.info("Web-based ingesting %s ..." % doi)
        self.webdriver.get('https://webprod.plosjournals.org/admin')
        try:
            self.webdriver.find_element_by_xpath("//input[@value='%s.zip']" % doi).click()
        except NoSuchElementException, e:
            logger.error("Could not find '%s.zip' in admin ingestibles" % doi)
            return
        self.webdriver.find_element_by_id('ingestArchives_force').click()
        self.webdriver.find_element_by_id('ingestArchives_action').click()

    def get_screenshot(self, url, filename):
        self.webdriver.get(url)
        self.webdriver.save_screenshot(filename)

    def get_screenshot_doi(self, doi, filename):
        logger.info("Capturing screenshot for %s ..." % doi)
        self.get_screenshot(self.article_url_format % doi, filename)

    def disable(self, doi):
        self.webdriver.get('https://webprod.plosjournals.org/admin')
        elem_doi_field = self.webdriver.find_element_by_xpath("//form[@id='disableArticle']/input[@name='article']")
        elem_doi_field.send_keys("info:doi/10.1371/journal.%s" % doi)
        self.webdriver.find_element_by_xpath("//form[@id='disableArticle']/input[@type='submit']").click()
        alert = self.webdriver.switch_to_alert()
        alert.accept()

    def close(self):
        self.webdriver.close()

def compare_web_rhino(webdriver, rdriver, doi, filename, output_location=""):
    logger.info("Comparing web vs. rhino ingest for %s ..." % doi)
    logger.info("Disabling %s if already exists" % doi)
    webdriver.disable(doi)
    logger.info("Uploading %s ..." % filename)
    upload_webprod('%s.zip' % doi)    
    webdriver.ingest(doi)
    webdriver.get_screenshot_doi(doi, '%s%s-web.png' % (output_location, doi))

    logger.info("Disabling %s if already exists" % doi)
    webdriver.disable(doi)
    logger.info("Uploading %s ..." % filename)
    upload_webprod('%s.zip' % doi)
    logger.info("Rhino ingesting %s ..." % doi) 
    rdriver.ingest('%s.zip' % doi, force_reingest=True)
    webdriver.get_screenshot_doi(doi, '%s%s-rhino.png' % (output_location, doi))
    
    logger.info("Creating visual diff for %s ..." % doi)
    make_diff('%s%s-web.png' % (output_location, doi), '%s%s-rhino.png' % (output_location, doi), '%s%s-diff.png' % (output_location, doi))
    
    logger.info("Finished comparing %s" % doi)


def get_articles_in_dir(dirpath):
    ret = []

    for f in glob(os.path.join(dirpath, "*.zip")):
        directory, filename = os.path.split(f)
        doi = filename[0:-4]
        ret += [(doi, filename)]

    return ret

if __name__ == "__main__":
    wpd = WebprodDriver()
    r = Rhyno('https://webprod.plosjournals.org/api/')

    #compare_web_rhino(wpd, r, doi, doi+'.zip', 'output/')
    articles = get_articles_in_dir('input/')
    for a in articles:
        try:
            compare_web_rhino(wpd, r, a[0], a[1], 'output/')
        except Exception, e:
            logger.error("Comparison for %s broke! See below ..." % a[0])
            logger.exception(e)

    wpd.close()
    
