# sv_vestel/items.py

import scrapy

class ComplaintItem(scrapy.Item):
    ref_url = scrapy.Field()
    title = scrapy.Field()
    full_comment = scrapy.Field()
    date = scrapy.Field()