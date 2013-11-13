from selenium import webdriver
from PIL import Image
import subprocess
import logging

logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)

def get_screenshot(url, filename):
    ff_webdriver = webdriver.Firefox()
    ff_webdriver.get(url)
    ff_webdriver.save_screenshot(filename)
    ff_webdriver.quit()

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

if __name__ == "__main__":
    compare_prod_stage('pone.0080411')
